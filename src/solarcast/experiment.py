"""The pre-registered experiment for one plant (see reports/preregistration.md).

Splits are calendar years in the plant's local time: train up to 2021, validate on 2022, test on
2023. Per horizon, Ridge and LightGBM are fitted on training targets only, and the candidate with
the lower validation RMSE is selected. ``evaluate(..., split="test")`` is the single test run.
"""

from __future__ import annotations

from dataclasses import dataclass

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from solarcast import baselines, bootstrap, features
from solarcast.clearsky import SCORED_ZENITH, clearsky_power, fit_scale, solar_geometry
from solarcast.data import Plant, outage_days

HORIZONS = (1, 4, 16)
SPLITS = {"train": (None, 2021), "validation": (2022, 2022), "test": (2023, 2023)}
TEST_LAST_MONTH = 10  # pre-registered test period: January-October 2023
# A target is scored only once its whole feature window (the issue time and the N_LAGS - 1
# intervals before it) lies inside its own partition: N_LAGS - 1 + h intervals after the start.
LGBM_PARAMS = dict(
    n_estimators=400, learning_rate=0.05, num_leaves=31, min_child_samples=100, verbose=-1
)


def make_candidates() -> dict:
    return {
        "ridge": make_pipeline(
            SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=1.0)
        ),
        "lightgbm": lgb.LGBMRegressor(random_state=0, **LGBM_PARAMS),
    }


@dataclass
class Prepared:
    plant: Plant
    power: pd.Series  # per-unit
    cs_power: pd.Series
    geometry: pd.DataFrame
    sun_up: pd.Series
    split: pd.Series  # "train" / "validation" / "test" / "" per interval
    position: pd.Series  # intervals since the start of the interval's partition
    outages: pd.DatetimeIndex
    poa_index: pd.Series  # measured POA / clear-sky POA (the irradiance-sensor variant only)


def prepare(plant: Plant, frame: pd.DataFrame, include_test: bool = False) -> Prepared:
    """Per-unit power, clear-sky reference fitted on training data, split labels.

    Outage days are taken from ``frame.attrs["outage_days"]`` (set by ``load_plant``, which has
    already blanked their power); frames built elsewhere have them detected here.
    """
    outages = frame.attrs.get("outage_days")
    if outages is None:
        outages = outage_days(frame, plant)
    local = frame.index.tz_convert(plant.timezone)
    year = pd.Series(local.year, index=frame.index)
    month = pd.Series(local.month, index=frame.index)
    if not include_test:
        frame, year, month = frame[year <= 2022], year[year <= 2022], month[year <= 2022]
    split = pd.Series("", index=frame.index)
    for name, (lo, hi) in SPLITS.items():
        split[(year >= (lo or 0)) & (year <= hi)] = name
    split[(split == "test") & (month > TEST_LAST_MONTH)] = ""  # outside the test period
    power = frame["power_kw"] / plant.capacity_kw_dc
    geometry = solar_geometry(plant, frame.index)
    train = split == "train"
    scale, cap = fit_scale(power[train], geometry[train])
    cs = clearsky_power(geometry, scale, cap)
    sun_up = geometry["zenith"] < SCORED_ZENITH
    start = split.ne(split.shift())
    position = split.groupby(start.cumsum()).cumcount()
    poa_index = (frame["poa"] / geometry["cs_poa"]).where(sun_up & (geometry["cs_poa"] > 0))
    return Prepared(
        plant,
        power,
        cs,
        geometry,
        sun_up,
        split,
        position,
        outages,
        poa_index.clip(*features.CSI_CLIP),
    )


def scored_mask(p: Prepared, split: str, h: int) -> pd.Series:
    """Daytime intervals of ``split`` with measured power whose horizon-h feature window lies
    entirely inside the partition."""
    window_inside = p.position >= features.N_LAGS - 1 + h
    return (p.split == split) & p.sun_up & p.power.notna() & window_inside


def common_rows(p: Prepared, table: pd.DataFrame, split: str, h: int) -> pd.Series:
    """Scored intervals of ``split`` where every forecast in ``table`` exists.

    Selection and scoring use the same rows, so a baseline that cannot forecast an interval
    removes it for every forecast; how many intervals that removes is reported, never hidden.
    """
    return scored_mask(p, split, h) & table.notna().all(axis=1)


def rmse(forecast: pd.Series, actual: pd.Series) -> float:
    return float(np.sqrt(((forecast - actual) ** 2).mean()))


def mae(forecast: pd.Series, actual: pd.Series) -> float:
    return float((forecast - actual).abs().mean())


def forecasts(
    p: Prepared, h: int, eval_split: str, sensor: bool = False
) -> tuple[pd.DataFrame, dict]:
    """All forecasts for target times in ``eval_split`` at horizon h, plus the selection record.

    Candidates are fitted on training targets; the one with the lower validation RMSE is
    selected regardless of ``eval_split``. ``sensor=True`` is the irradiance-sensor variant: the
    on-site POA sensor's clear-sky index over the last 4 hours is added to the features.
    """
    train = p.split == "train"
    csi_med = baselines.hourly_csi_median(p.power[train], p.cs_power[train], p.sun_up[train])
    clim = baselines.climatology_table(p.power[train])
    x, y = features.build(p.power, p.cs_power, p.geometry, p.sun_up, h)
    if sensor:
        for k in range(features.N_LAGS):
            x[f"poa_lag{k}"] = p.poa_index.shift(k + h)
    fit_rows = scored_mask(p, "train", h) & y.notna() & x["cs_now"].notna()
    out = {
        "persistence": baselines.persistence(p.power, h),
        "smart_persistence": baselines.smart_persistence(p.power, p.cs_power, h, csi_med, p.sun_up),
        "climatology": baselines.climatology(p.power.index, clim),
    }
    candidates = make_candidates()
    for name, model in candidates.items():
        model.fit(x[fit_rows], y[fit_rows])
        csi_hat = pd.Series(model.predict(x), index=x.index).clip(*features.CSI_CLIP)
        out[name] = (csi_hat * p.cs_power).where(x["cs_now"].notna())
    table = pd.DataFrame(out)
    # Selection uses exactly the rows that are scored: every forecast present (see common_rows).
    val_rows = common_rows(p, table, "validation", h)
    val_rmse = {name: rmse(table.loc[val_rows, name], p.power[val_rows]) for name in candidates}
    selected = min(val_rmse, key=val_rmse.get)
    table["selected"] = table[selected]
    record = {"selected": selected, "validation_rmse": val_rmse, "train_rows": int(fit_rows.sum())}
    return table[p.split == eval_split], record


def local_day(p: Prepared, index: pd.DatetimeIndex) -> pd.Series:
    return pd.Series(index.tz_convert(p.plant.timezone).normalize(), index=index)


def evaluate(
    p: Prepared, split: str = "validation", horizons=HORIZONS, sensor: bool = False
) -> dict:
    """Per horizon: RMSE (per-unit) of every forecast on the scored intervals of ``split``,
    skill against smart persistence, and a day-block bootstrap interval for the selected model."""
    if split == "test" and not (p.split == "test").any():
        raise ValueError("Test data was not loaded: prepare(..., include_test=True)")
    results = {}
    for h in horizons:
        table, record = forecasts(p, h, split, sensor=sensor)
        scored = scored_mask(p, split, h).reindex(table.index)
        ok = scored & table.notna().all(axis=1)
        actual = p.power.reindex(table.index)[ok]
        scores = {k: rmse(table.loc[ok, k], actual) for k in table.columns}
        mae_scores = {k: mae(table.loc[ok, k], actual) for k in table.columns}
        ref = scores["smart_persistence"]
        interval = bootstrap.skill_interval(
            table.loc[ok, "selected"],
            table.loc[ok, "smart_persistence"],
            actual,
            local_day(p, actual.index),
        )
        results[h] = {
            "n": int(ok.sum()),
            "excluded_missing_forecast": {
                k: int((scored & table[k].isna()).sum()) for k in table.columns
            },
            "rmse": scores,
            "skill_vs_smart_persistence": {k: 1 - v / ref for k, v in scores.items()},
            "mae": mae_scores,
            "mae_skill_vs_smart_persistence": {
                k: 1 - v / mae_scores["smart_persistence"] for k, v in mae_scores.items()
            },
            "skill_vs_persistence": {k: 1 - v / scores["persistence"] for k, v in scores.items()},
            "skill_vs_climatology": {k: 1 - v / scores["climatology"] for k, v in scores.items()},
            "selected_skill_interval": interval,
            **record,
        }
    return results


def data_counts(p: Prepared, split: str) -> dict:
    """Outage days and missing actual power in ``split`` (both excluded from scoring)."""
    in_split = p.split == split
    days = local_day(p, p.split.index)[in_split].unique()
    daytime = in_split & p.sun_up
    return {
        "outage_days": int(pd.DatetimeIndex(days).isin(p.outages).sum()),
        "days": int(len(days)),
        "daytime_intervals": int(daytime.sum()),
        "daytime_missing_power": int((daytime & p.power.isna()).sum()),
    }
