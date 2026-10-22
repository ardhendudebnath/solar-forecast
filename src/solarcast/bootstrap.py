"""Day-block bootstrap for skill scores, as pre-registered.

Forecast errors within a day are strongly correlated (one cloudy afternoon affects many
intervals), so intervals are not independent. Whole local days are resampled with replacement,
and skill is recomputed on each resample.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

N_RESAMPLES = 1000
SEED = 0


def _interval(per_day: pd.DataFrame, statistic, n_resamples: int, seed: int, level: float) -> dict:
    """Point value and percentile interval of ``statistic(weights)`` over resampled days.

    ``per_day`` holds per-day sums; a resample is a vector of how often each day was drawn, which
    makes each statistic a cheap weighted sum.
    """
    days = len(per_day)
    point = statistic(np.ones(days))
    rng = np.random.default_rng(seed)
    draws = np.empty(n_resamples)
    for i in range(n_resamples):
        counts = np.bincount(rng.integers(0, days, days), minlength=days).astype(float)
        draws[i] = statistic(counts)
    tail = (1.0 - level) / 2
    low, high = np.quantile(draws, [tail, 1.0 - tail])
    return {"skill": float(point), "low": float(low), "high": float(high), "days": int(days)}


def skill_interval(
    model: pd.Series,
    reference: pd.Series,
    actual: pd.Series,
    day: pd.Series,
    n_resamples: int = N_RESAMPLES,
    seed: int = SEED,
    level: float = 0.95,
) -> dict:
    """RMSE skill of ``model`` against ``reference`` with a day-block bootstrap interval.

    All inputs share one index (the scored intervals); ``day`` labels each interval's local day.
    """
    err_m = (model - actual) ** 2
    err_r = (reference - actual) ** 2
    per_day = pd.DataFrame({"m": err_m, "r": err_r, "n": 1.0}).groupby(day.to_numpy()).sum()
    m, r, n = (per_day[c].to_numpy() for c in ("m", "r", "n"))

    def skill(weights: np.ndarray) -> float:
        total_n = weights @ n
        return 1.0 - np.sqrt((weights @ m) / total_n) / np.sqrt((weights @ r) / total_n)

    return _interval(per_day, skill, n_resamples, seed, level)


def loss_skill_interval(
    model_loss: pd.Series,
    reference_loss: pd.Series,
    day: pd.Series,
    n_resamples: int = N_RESAMPLES,
    seed: int = SEED,
    level: float = 0.95,
) -> dict:
    """Skill 1 - mean(model loss) / mean(reference loss), e.g. CRPS or MAE, with a day-block
    bootstrap interval. Losses are per scored interval; ``day`` labels each interval's day."""
    per_day = pd.DataFrame({"m": model_loss, "r": reference_loss}).groupby(day.to_numpy()).sum()
    m, r = per_day["m"].to_numpy(), per_day["r"].to_numpy()
    return _interval(per_day, lambda w: 1.0 - (w @ m) / (w @ r), n_resamples, seed, level)


def mean_interval(
    values: pd.Series,
    day: pd.Series,
    n_resamples: int = N_RESAMPLES,
    seed: int = SEED,
    level: float = 0.95,
) -> dict:
    """Mean of per-interval ``values`` (e.g. 1 where an interval covers the actual value) with a
    day-block bootstrap interval."""
    per_day = pd.DataFrame({"v": values, "n": 1.0}).groupby(day.to_numpy()).sum()
    v, n = per_day["v"].to_numpy(), per_day["n"].to_numpy()
    out = _interval(per_day, lambda w: (w @ v) / (w @ n), n_resamples, seed, level)
    return {"mean": out.pop("skill"), **out}
