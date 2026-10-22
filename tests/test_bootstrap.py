import numpy as np
import pandas as pd

from solarcast.bootstrap import skill_interval


def _series(n_days=60, per_day=40, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.RangeIndex(n_days * per_day)
    day = pd.Series(np.repeat(np.arange(n_days), per_day), index=idx)
    actual = pd.Series(rng.random(len(idx)), index=idx)
    return idx, day, actual, rng


def test_better_model_has_interval_above_zero_and_contains_point():
    idx, day, actual, rng = _series()
    reference = actual + rng.normal(0, 0.2, len(idx))
    model = actual + rng.normal(0, 0.1, len(idx))
    r = skill_interval(model, reference, actual, day, n_resamples=300)
    assert r["low"] > 0 and r["low"] <= r["skill"] <= r["high"]
    assert r["days"] == 60


def test_identical_forecasts_have_zero_skill_and_zero_width():
    idx, day, actual, rng = _series()
    f = actual + rng.normal(0, 0.1, len(idx))
    r = skill_interval(f, f, actual, day, n_resamples=100)
    assert r["skill"] == 0 and r["low"] == 0 and r["high"] == 0


def test_day_blocks_widen_the_interval_when_errors_cluster_by_day():
    # Errors that are shared within a day carry less information than independent ones.
    idx, day, actual, rng = _series(n_days=30, per_day=40)
    daily_shift = pd.Series(rng.normal(0, 0.2, 30)[day.to_numpy()], index=idx)
    reference = actual + rng.normal(0, 0.15, len(idx))
    model = actual + daily_shift * 0.5 + rng.normal(0, 0.05, len(idx))
    by_day = skill_interval(model, reference, actual, day, n_resamples=400)
    as_if_independent = skill_interval(
        model, reference, actual, pd.Series(np.arange(len(idx)), index=idx), n_resamples=400
    )
    width = lambda r: r["high"] - r["low"]  # noqa: E731
    assert width(by_day) > 1.5 * width(as_if_independent)


def test_is_reproducible():
    idx, day, actual, rng = _series()
    ref, mod = actual + 0.2, actual + 0.1
    assert skill_interval(mod, ref, actual, day) == skill_interval(mod, ref, actual, day)
