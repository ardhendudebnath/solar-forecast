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
    # Per-day sums and counts make each resample a cheap weighted sum.
    per_day = pd.DataFrame({"m": err_m, "r": err_r, "n": 1.0}).groupby(day.to_numpy()).sum()
    m, r, n = (per_day[c].to_numpy() for c in ("m", "r", "n"))

    def skill(weights: np.ndarray) -> float:
        total_n = weights @ n
        return 1.0 - np.sqrt((weights @ m) / total_n) / np.sqrt((weights @ r) / total_n)

    point = skill(np.ones(len(per_day)))
    rng = np.random.default_rng(seed)
    days = len(per_day)
    draws = np.empty(n_resamples)
    for i in range(n_resamples):
        counts = np.bincount(rng.integers(0, days, days), minlength=days).astype(float)
        draws[i] = skill(counts)
    tail = (1.0 - level) / 2
    low, high = np.quantile(draws, [tail, 1.0 - tail])
    return {"skill": float(point), "low": float(low), "high": float(high), "days": int(days)}
