"""Probabilistic forecasts, as pre-registered in reports/preregistration_v0.2.md.

Every forecast is 19 quantiles (tau = 0.05 ... 0.95) of per-unit power at the target time t + h,
using data up to interval t only, as a DataFrame indexed by target time with one column per tau.

- Model: LightGBM quantile regression on the v0.1 features, one model per tau, predicting the
  clear-sky index; sorted across tau so quantiles never cross, times clear-sky power.
- PeEn: quantiles of the last 4 hours of clear-sky index (at least 4 valid values).
- CH-PeEn: training quantiles of clear-sky index for the target's month and UTC time of day.
- SP-Err: the current clear-sky index plus training quantiles of its h-step change, by UTC hour.

PeEn and SP-Err fall back to CH-PeEn where they have too little recent data.
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd

from solarcast import baselines, bootstrap, features
from solarcast.experiment import (
    LGBM_PARAMS,
    Prepared,
    local_day,
    mae,
    scored_mask,
)

TAUS = tuple(round(0.05 * k, 2) for k in range(1, 20))
SPLITS = {"train": (None, 2022), "validation": (2023, 2023), "test": (2024, 2024)}
TEST_LAST_MONTH = 10  # pre-registered test period: January-October 2024
MIN_MEMBERS = 4  # PeEn needs at least this many valid values in the last 4 hours
MIN_CELL = 20  # CH-PeEn needs at least this many training values per month x time-of-day cell
BASELINES = ("peen", "ch_peen", "sp_err")


def _sort_clip(q: np.ndarray) -> np.ndarray:
    return np.sort(np.clip(q, *features.CSI_CLIP), axis=1)


def _frame(values: np.ndarray, index: pd.Index, taus) -> pd.DataFrame:
    return pd.DataFrame(values, index=index, columns=list(taus))


def ch_peen_table(csi: pd.Series, taus=TAUS) -> pd.DataFrame:
    """Training quantiles of clear-sky index per (month, UTC minute of day); thin cells dropped."""
    csi = csi.dropna()
    key = [csi.index.month, csi.index.hour * 60 + csi.index.minute]
    grouped = csi.groupby(key)
    table = grouped.quantile(list(taus)).unstack()
    return table[grouped.size() >= MIN_CELL]


def ch_peen(cs_power: pd.Series, table: pd.DataFrame, taus=TAUS) -> pd.DataFrame:
    idx = cs_power.index
    key = pd.MultiIndex.from_arrays([idx.month, idx.hour * 60 + idx.minute])
    q = table.reindex(key).to_numpy()
    return _frame(q * cs_power.to_numpy()[:, None], idx, taus)


def peen(csi: pd.Series, cs_power: pd.Series, h: int, fallback: pd.DataFrame, taus=TAUS):
    """Quantiles of the clear-sky index at t, t - 1, ..., t - 15, times clear-sky power at t + h."""
    members = np.column_stack([csi.shift(k + h).to_numpy() for k in range(features.N_LAGS)])
    enough = (~np.isnan(members)).sum(axis=1) >= MIN_MEMBERS
    q = np.full((len(csi), len(taus)), np.nan)
    q[enough] = np.nanquantile(members[enough], list(taus), axis=1).T
    out = _frame(_sort_clip(q) * cs_power.to_numpy()[:, None], csi.index, taus)
    return out.where(pd.Series(enough, index=csi.index), fallback, axis=0)


def sp_err_table(csi: pd.Series, h: int, train: pd.Series, taus=TAUS) -> pd.DataFrame:
    """Training quantiles of CSI(t + h) - CSI(t) by the target's UTC hour."""
    change = (csi - csi.shift(h))[train & train.shift(h, fill_value=False)].dropna()
    return change.groupby(change.index.hour).quantile(list(taus)).unstack()


def sp_err(csi: pd.Series, cs_power: pd.Series, h: int, table, fallback, taus=TAUS):
    now = csi.shift(h)  # the clear-sky index at issue time, aligned to the target
    change = table.reindex(csi.index.hour).to_numpy()
    q = _sort_clip(now.to_numpy()[:, None] + change)
    out = _frame(q * cs_power.to_numpy()[:, None], csi.index, taus)
    return out.where(now.notna(), fallback, axis=0)


def quantile_model(tau: float) -> lgb.LGBMRegressor:
    return lgb.LGBMRegressor(objective="quantile", alpha=tau, random_state=0, **LGBM_PARAMS)


def model_quantiles(p: Prepared, h: int, rows: pd.Series, taus=TAUS) -> pd.DataFrame:
    """LightGBM quantile forecasts for the target times in ``rows``, fitted on training data."""
    x, y = features.build(p.power, p.cs_power, p.geometry, p.sun_up, h)
    fit = scored_mask(p, "train", h) & y.notna() & x["cs_now"].notna()
    target = rows & x["cs_now"].notna()
    q = np.column_stack([quantile_model(t).fit(x[fit], y[fit]).predict(x[target]) for t in taus])
    out = _frame(np.full((len(x), len(taus)), np.nan), x.index, taus)
    out.loc[target] = _sort_clip(q) * p.cs_power[target].to_numpy()[:, None]
    return out


def all_forecasts(p: Prepared, h: int, eval_split: str, taus=TAUS) -> dict[str, pd.DataFrame]:
    """Quantile forecasts (model and baselines) for target times in ``eval_split``."""
    train = p.split == "train"
    csi = features.clear_sky_index(p.power, p.cs_power, p.sun_up)
    rows = p.split == eval_split
    fallback = ch_peen(p.cs_power, ch_peen_table(csi[train], taus), taus)
    table = sp_err_table(csi, h, train, taus)
    out = {
        "model": model_quantiles(p, h, rows, taus),
        "peen": peen(csi, p.cs_power, h, fallback, taus),
        "ch_peen": fallback,
        "sp_err": sp_err(csi, p.cs_power, h, table, fallback, taus),
    }
    return {k: v[rows] for k, v in out.items()}


def pinball(q: pd.DataFrame, actual: pd.Series) -> pd.DataFrame:
    """Pinball loss per interval and tau."""
    taus = np.asarray(q.columns, dtype=float)
    diff = actual.to_numpy()[:, None] - q.to_numpy()
    return pd.DataFrame(
        np.maximum(taus * diff, (taus - 1) * diff), index=q.index, columns=q.columns
    )


def crps(q: pd.DataFrame, actual: pd.Series) -> pd.Series:
    """CRPS per interval from evenly spaced quantiles: (2 / K) times the summed pinball loss."""
    return 2 * pinball(q, actual).mean(axis=1)


def inside(q: pd.DataFrame, actual: pd.Series, low: float, high: float) -> pd.Series:
    return (actual >= q[low]) & (actual <= q[high])


def evaluate(p: Prepared, split: str, horizons=(1, 4, 16), taus=TAUS) -> dict:
    """Per horizon: CRPS of every forecast on common scored intervals, the model's CRPS skill
    against each baseline with day-block intervals, coverage, width, reliability, and the median
    forecast's MAE skill against smart persistence."""
    if split == "test" and not (p.split == "test").any():
        raise ValueError("Test data was not loaded: prepare(..., include_test=True)")
    train = p.split == "train"
    csi_med = baselines.hourly_csi_median(p.power[train], p.cs_power[train], p.sun_up[train])
    results = {}
    for h in horizons:
        q = all_forecasts(p, h, split, taus)
        smart = baselines.smart_persistence(p.power, p.cs_power, h, csi_med, p.sun_up)[
            p.split == split
        ]
        scored = scored_mask(p, split, h)[p.split == split]
        present = {k: v.notna().all(axis=1) for k, v in q.items()}
        present["smart_persistence"] = smart.notna()
        ok = scored & pd.concat(present, axis=1).all(axis=1)
        actual = p.power[p.split == split][ok]
        day = local_day(p, actual.index)
        loss = {k: crps(v[ok], actual) for k, v in q.items()}
        model = q["model"][ok]
        median = model[0.5]
        abs_model, abs_smart = (median - actual).abs(), (smart[ok] - actual).abs()
        results[h] = {
            "n": int(ok.sum()),
            "excluded_missing_forecast": {k: int((scored & ~v).sum()) for k, v in present.items()},
            "crps": {k: float(v.mean()) for k, v in loss.items()},
            "crps_skill": {
                b: bootstrap.loss_skill_interval(loss["model"], loss[b], day) for b in BASELINES
            },
            "coverage_90": {
                k: float(inside(v[ok], actual, 0.05, 0.95).mean()) for k, v in q.items()
            },
            "coverage_80": {k: float(inside(v[ok], actual, 0.1, 0.9).mean()) for k, v in q.items()},
            "coverage_90_interval": bootstrap.mean_interval(
                inside(model, actual, 0.05, 0.95).astype(float), day
            ),
            "width_90": {k: float((v[ok][0.95] - v[ok][0.05]).mean()) for k, v in q.items()},
            "share_below": {str(t): float((actual < model[t]).mean()) for t in taus},
            "median_mae": {
                "model": mae(median, actual),
                "smart_persistence": mae(smart[ok], actual),
            },
            "median_mae_skill_vs_smart_persistence": bootstrap.loss_skill_interval(
                abs_model, abs_smart, day
            ),
        }
    return results
