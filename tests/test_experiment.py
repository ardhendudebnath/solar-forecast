import dataclasses

import numpy as np
import pandas as pd
import pytest

from solarcast import experiment
from solarcast.clearsky import solar_geometry
from solarcast.data import Plant

PLANT = Plant(
    plant_id="t",
    name="test",
    location="Arbuckle, CA",
    timezone="America/Los_Angeles",
    latitude=38.996306,
    longitude=-122.134111,
    elevation_m=10.0,
    capacity_kw_dc=1000.0,
    tracking=False,
    tilt=25.0,
    azimuth=180.0,
    files={},
)


@pytest.fixture(scope="module")
def frame():
    # Two months per year across the split boundaries: Nov-Dec 2021 / Jan 2022 / Jan 2023.
    idx = pd.date_range("2021-11-01", "2023-01-31 23:45", freq="15min", tz="UTC")
    g = solar_geometry(PLANT, idx)
    rng = np.random.default_rng(0)
    # Cloudiness as an AR(1) clear-sky index: forecastable, but not trivially.
    csi = np.empty(len(idx))
    csi[0] = 0.8
    for i in range(1, len(idx)):
        csi[i] = 0.8 + 0.95 * (csi[i - 1] - 0.8) + rng.normal(0, 0.05)
    power = (0.7 * g["cs_poa"] * np.clip(csi, 0, 1.2)).clip(upper=800.0)
    return pd.DataFrame({"power_kw": power, "poa": g["cs_poa"], "ambient_c": 15.0}, index=idx)


def test_prepare_splits_by_local_year_and_hides_test_by_default(frame):
    p = experiment.prepare(PLANT, frame)
    assert set(p.split.unique()) == {"train", "validation"}
    # 2022-01-01 00:00 local is 08:00 UTC: earlier UTC hours of Jan 1 are still 2021 (train).
    assert p.split[pd.Timestamp("2022-01-01 07:45", tz="UTC")] == "train"
    assert p.split[pd.Timestamp("2022-01-01 08:00", tz="UTC")] == "validation"
    with pytest.raises(ValueError, match="Test data was not loaded"):
        experiment.evaluate(p, "test", horizons=(1,))


def test_warmup_covers_the_first_four_hours_of_each_partition(frame):
    p = experiment.prepare(PLANT, frame, include_test=True)
    first_val = p.split.index[p.split == "validation"][0]
    window = p.warmup[first_val : first_val + pd.Timedelta(hours=4)]
    assert window.iloc[:16].all() and not window.iloc[16]


def test_training_never_sees_a_later_target(frame, monkeypatch):
    p = experiment.prepare(PLANT, frame, include_test=True)
    seen = []

    class Spy:
        def fit(self, x, y):
            seen.append(x.index)
            return self

        def predict(self, x):
            return np.full(len(x), 0.8)

    monkeypatch.setattr(experiment, "make_candidates", lambda: {"a": Spy(), "b": Spy()})
    experiment.forecasts(p, 16, "validation")
    for index in seen:
        assert (p.split[index] == "train").all()
        # Issue times (t = T - h) are also in training: no feature from a later split.
        issue = index - pd.Timedelta(minutes=15 * 16)
        assert (p.split.reindex(issue) == "train").all()


def test_models_beat_smart_persistence_on_forecastable_clouds(frame):
    p = experiment.prepare(PLANT, frame)
    res = experiment.evaluate(p, "validation", horizons=(4,))[4]
    assert res["n"] > 0 and res["selected"] in {"ridge", "lightgbm"}
    assert res["skill_vs_smart_persistence"]["selected"] > 0


def test_selection_is_made_on_validation_even_for_the_test_split(frame):
    p = experiment.prepare(PLANT, frame, include_test=True)
    _, on_val = experiment.forecasts(p, 4, "validation")
    _, on_test = experiment.forecasts(p, 4, "test")
    assert on_val["selected"] == on_test["selected"]
    assert on_val["validation_rmse"] == on_test["validation_rmse"]


def test_tracker_plants_run_too(frame):
    p = experiment.prepare(dataclasses.replace(PLANT, tracking=True, tilt=0.0), frame)
    assert experiment.evaluate(p, "validation", horizons=(1,))[1]["n"] > 0


def test_selection_and_scoring_use_the_same_rows(frame):
    # Climatology has no value for months absent from training (this fixture trains on Nov-Dec
    # only), so those intervals drop out. They must drop out of selection too.
    p = experiment.prepare(PLANT, frame)
    res = experiment.evaluate(p, "validation", horizons=(4,))[4]
    for name in ("ridge", "lightgbm"):
        assert res["validation_rmse"][name] == pytest.approx(res["rmse"][name])
    assert res["excluded_missing_forecast"]["climatology"] > 0  # counted, not hidden
    assert res["rmse"]["selected"] == min(res["rmse"]["ridge"], res["rmse"]["lightgbm"])


def test_test_split_ends_with_october_2023():
    idx = pd.date_range("2023-10-31 12:00", "2023-11-02", freq="15min", tz="UTC")
    g = solar_geometry(PLANT, idx)
    early = pd.date_range("2021-06-01", "2021-06-03", freq="15min", tz="UTC")
    ge = solar_geometry(PLANT, early)
    frame = pd.concat(
        [
            pd.DataFrame({"power_kw": 0.7 * ge["cs_poa"], "poa": ge["cs_poa"], "ambient_c": 15.0}),
            pd.DataFrame({"power_kw": 0.7 * g["cs_poa"], "poa": g["cs_poa"], "ambient_c": 15.0}),
        ]
    )
    p = experiment.prepare(PLANT, frame, include_test=True)
    local = p.split.index.tz_convert(PLANT.timezone)
    assert (p.split[local.month == 10] == "test").all()
    assert (p.split[local.month == 11] == "").all()
