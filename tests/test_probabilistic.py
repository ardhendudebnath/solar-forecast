import numpy as np
import pandas as pd
import pytest

from solarcast import bootstrap, experiment, probabilistic
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

TAUS = (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95)


@pytest.fixture(scope="module")
def frame():
    # AR(1) cloudiness across the v0.2 boundaries: train to 2022, validate 2023, test 2024.
    idx = pd.date_range("2022-09-01", "2024-01-31 23:45", freq="15min", tz="UTC")
    g = solar_geometry(PLANT, idx)
    rng = np.random.default_rng(1)
    csi = np.empty(len(idx))
    csi[0] = 0.8
    for i in range(1, len(idx)):
        csi[i] = 0.8 + 0.95 * (csi[i - 1] - 0.8) + rng.normal(0, 0.05)
    power = (0.7 * g["cs_poa"] * np.clip(csi, 0, 1.2)).clip(upper=800.0)
    return pd.DataFrame({"power_kw": power, "poa": g["cs_poa"], "ambient_c": 15.0}, index=idx)


@pytest.fixture(scope="module")
def prepared(frame):
    return experiment.prepare(
        PLANT,
        frame,
        include_test=True,
        splits=probabilistic.SPLITS,
        test_last_month=probabilistic.TEST_LAST_MONTH,
    )


def test_v02_splits():
    idx = pd.date_range("2022-12-31 20:00", "2024-11-02 20:00", freq="1D", tz="UTC")
    g = solar_geometry(PLANT, idx)
    f = pd.DataFrame({"power_kw": 0.7 * g["cs_poa"], "poa": g["cs_poa"]}, index=idx)
    p = experiment.prepare(PLANT, f, include_test=True, splits=probabilistic.SPLITS)
    local = p.split.index.tz_convert(PLANT.timezone)
    assert (p.split[local.year == 2022] == "train").all()
    assert (p.split[local.year == 2023] == "validation").all()
    assert (p.split[(local.year == 2024) & (local.month <= 10)] == "test").all()
    assert (p.split[(local.year == 2024) & (local.month == 11)] == "").all()
    hidden = experiment.prepare(PLANT, f, splits=probabilistic.SPLITS)
    assert hidden.split.index.tz_convert(PLANT.timezone).year.max() == 2023


def test_taus_are_19_even_levels():
    assert len(probabilistic.TAUS) == 19
    assert probabilistic.TAUS[0] == 0.05 and probabilistic.TAUS[-1] == 0.95
    assert 0.5 in probabilistic.TAUS and 0.1 in probabilistic.TAUS and 0.9 in probabilistic.TAUS


def test_crps_of_a_point_forecast_is_its_absolute_error():
    # All quantiles at one value: (2/K) sum of pinball = |y - q| when the levels average 0.5.
    q = pd.DataFrame(np.full((3, 19), 0.4), columns=list(probabilistic.TAUS))
    y = pd.Series([0.4, 0.7, 0.1])
    assert probabilistic.crps(q, y).to_numpy() == pytest.approx([0.0, 0.3, 0.3])


def test_crps_rewards_a_correct_spread():
    rng = np.random.default_rng(0)
    y = pd.Series(rng.normal(0.5, 0.1, 20_000))
    from scipy.stats import norm

    def normal_q(sd):
        return pd.DataFrame(
            np.tile(norm.ppf(probabilistic.TAUS, 0.5, sd), (len(y), 1)),
            columns=list(probabilistic.TAUS),
        )

    right, narrow, wide = (probabilistic.crps(normal_q(s), y).mean() for s in (0.1, 0.02, 0.3))
    assert right < narrow and right < wide


def _series(values, start="2023-06-01 16:00"):
    idx = pd.date_range(start, periods=len(values), freq="15min", tz="UTC")
    return pd.Series(values, index=idx, dtype=float)


def test_peen_uses_only_the_last_four_hours_and_falls_back():
    csi = _series(np.r_[np.full(16, 0.5), np.full(16, 0.9), np.full(8, np.nan)])
    cs = _series(np.full(40, 1.0))
    fallback = pd.DataFrame(-1.0, index=csi.index, columns=list(TAUS))
    q = probabilistic.peen(csi, cs, 4, fallback, TAUS)
    # Target 35 is issued at 31: its members are positions 16-31, all 0.9.
    assert q.iloc[35].to_numpy() == pytest.approx(np.full(len(TAUS), 0.9))
    # Target 27 is issued at 23: members 8-23, half 0.5 and half 0.9.
    assert q.iloc[27][0.05] == pytest.approx(0.5) and q.iloc[27][0.95] == pytest.approx(0.9)
    # Target 2 has fewer than 4 past values: fallback.
    assert (q.iloc[2] == -1.0).all()
    # Changing values after the issue time does not change the forecast.
    later = csi.copy()
    later.iloc[32:] = 0.1
    assert probabilistic.peen(later, cs, 4, fallback, TAUS).iloc[35].equals(q.iloc[35])


def test_ch_peen_table_quantiles_and_thin_cells():
    idx = pd.DatetimeIndex(
        [pd.Timestamp("2021-06-01 18:00", tz="UTC") + pd.Timedelta(days=d) for d in range(25)]
        + [pd.Timestamp("2021-06-01 19:00", tz="UTC") + pd.Timedelta(days=d) for d in range(5)]
    )
    csi = pd.Series(np.r_[np.linspace(0, 1, 25), np.full(5, 0.5)], index=idx)
    table = probabilistic.ch_peen_table(csi, TAUS)
    assert list(table.index) == [(6, 18 * 60)]  # the 5-value cell is dropped
    assert table.loc[(6, 1080), 0.5] == pytest.approx(0.5)
    cs = pd.Series([2.0, 2.0], index=[idx[0], idx[-1]])
    q = probabilistic.ch_peen(cs, table, TAUS)
    assert q.iloc[0][0.5] == pytest.approx(1.0) and q.iloc[1].isna().all()


def test_sp_err_adds_training_changes_to_the_current_index():
    csi = _series(np.full(48, 0.6))
    train = pd.Series(True, index=csi.index)
    table = probabilistic.sp_err_table(csi, 4, train, TAUS)
    assert np.allclose(table.to_numpy(), 0.0)  # constant index: no change
    cs = _series(np.full(48, 2.0))
    fallback = pd.DataFrame(-1.0, index=csi.index, columns=list(TAUS))
    q = probabilistic.sp_err(csi, cs, 4, table, fallback, TAUS)
    assert q.iloc[10].to_numpy() == pytest.approx(np.full(len(TAUS), 1.2))
    assert (q.iloc[2] == -1.0).all()  # no issue-time index yet


def test_model_quantiles_are_sorted_and_fitted_on_training_only(prepared, monkeypatch):
    seen = []
    real = probabilistic.quantile_model

    def spy(tau):
        model = real(tau)
        fit = model.fit

        def recording_fit(x, y):
            seen.append(x.index)
            return fit(x, y)

        model.fit = recording_fit
        return model

    monkeypatch.setattr(probabilistic, "quantile_model", spy)
    rows = prepared.split == "validation"
    q = probabilistic.model_quantiles(prepared, 4, rows, TAUS)
    got = q[rows].dropna()
    assert len(got) > 0 and (np.diff(got.to_numpy(), axis=1) >= 0).all()
    for index in seen:
        assert (prepared.split[index] == "train").all()


def test_model_beats_ensembles_and_matches_sp_err_on_ar1_clouds(prepared):
    res = probabilistic.evaluate(prepared, "validation", horizons=(4,))[4]
    assert res["n"] > 0
    assert res["crps_skill"]["peen"]["skill"] > 0.1
    assert res["crps_skill"]["ch_peen"]["skill"] > 0.1
    # The fixture's clouds are AR(1), for which SP-Err (current index plus its typical change) is
    # close to the true distribution: the model, trained on four months, can only come near it.
    assert res["crps_skill"]["sp_err"]["skill"] > -0.1
    assert 0.6 < res["coverage_90"]["model"] < 0.98
    # Every forecast is scored on the same intervals.
    assert set(res["excluded_missing_forecast"]) == {
        "model",
        "peen",
        "ch_peen",
        "sp_err",
        "smart_persistence",
    }


def test_test_split_is_refused_unless_loaded(frame):
    p = experiment.prepare(PLANT, frame, splits=probabilistic.SPLITS)
    with pytest.raises(ValueError, match="Test data was not loaded"):
        probabilistic.evaluate(p, "test", horizons=(1,))


def test_loss_skill_and_mean_intervals():
    day = pd.Series(np.repeat(np.arange(50), 10))
    rng = np.random.default_rng(0)
    m = pd.Series(rng.uniform(0, 1, 500))
    r = m * 2
    s = bootstrap.loss_skill_interval(m, r, day)
    assert s["skill"] == pytest.approx(0.5) and s["low"] == pytest.approx(0.5)
    c = bootstrap.mean_interval(pd.Series((rng.uniform(size=500) < 0.9).astype(float)), day)
    assert c["low"] <= c["mean"] <= c["high"] and 0.85 < c["mean"] < 0.95
