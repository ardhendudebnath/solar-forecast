import dataclasses

import numpy as np
import pandas as pd
import pytest

from solarcast.baselines import (
    climatology,
    climatology_table,
    hourly_csi_median,
    persistence,
    smart_persistence,
)
from solarcast.clearsky import clearsky_power, fit_scale, is_scored, solar_geometry
from solarcast.data import Plant

FIXED = Plant(
    plant_id="2107",
    name="fixed",
    location="Arbuckle, CA",
    timezone="America/Los_Angeles",
    latitude=38.996306,
    longitude=-122.134111,
    elevation_m=10.0,
    capacity_kw_dc=893.0,
    tracking=False,
    tilt=25.0,
    azimuth=180.0,
    files={},
)
TRACKER = dataclasses.replace(FIXED, tracking=True, tilt=0.0)
JUNE = pd.date_range("2022-06-21", periods=96, freq="15min", tz="UTC")


def test_geometry_is_zero_at_night_and_peaks_near_solar_noon():
    g = solar_geometry(FIXED, JUNE)
    assert (g.loc[g["zenith"] >= 90, "cs_poa"] == 0).all()
    # Solar noon at -122.13° is about 20:10 UTC in late June.
    peak = g["cs_poa"].idxmax()
    assert 19 <= peak.hour <= 21
    assert 800 < g["cs_poa"].max() < 1200


def test_tracker_collects_more_early_morning_light_than_fixed_tilt():
    fixed, tracker = solar_geometry(FIXED, JUNE), solar_geometry(TRACKER, JUNE)
    morning = (fixed["zenith"] > 60) & (fixed["zenith"] < 80) & (fixed["azimuth"] < 180)
    assert (tracker.loc[morning, "cs_poa"] > fixed.loc[morning, "cs_poa"]).all()
    assert tracker["cs_poa"].sum() > fixed["cs_poa"].sum()


def test_fit_scale_recovers_the_factor_and_cap():
    g = solar_geometry(FIXED, JUNE)
    power = (0.7 * g["cs_poa"]).clip(upper=600.0)
    scale, cap = fit_scale(power, g)
    assert scale == pytest.approx(0.7, rel=0.02)
    assert cap == pytest.approx(600.0)
    cs = clearsky_power(g, scale, cap)
    assert cs.max() <= cap and is_scored(g).sum() > 0


def _clear_day():
    g = solar_geometry(FIXED, JUNE)
    cs = clearsky_power(g, 0.7, 10_000.0)
    return g, cs


def test_smart_persistence_is_exact_on_a_clear_day():
    g, cs = _clear_day()
    sun_up = g["zenith"] < 85
    csi_by_hour = hourly_csi_median(cs, cs, sun_up)
    for h in (1, 4, 16):
        f = smart_persistence(cs, cs, h, csi_by_hour, sun_up)
        both = f.notna() & sun_up & sun_up.shift(h, fill_value=False)
        np.testing.assert_allclose(f[both], cs[both], rtol=1e-9)


def test_smart_persistence_uses_only_the_past():
    g, cs = _clear_day()
    sun_up = g["zenith"] < 85
    power = cs * 0.5
    power.iloc[80:] = cs.iloc[80:]  # clouds clear at interval 80 (20:00 UTC, near solar noon)
    f = smart_persistence(power, cs, 4, hourly_csi_median(cs, cs, sun_up), sun_up)
    assert sun_up.iloc[70:80].all()  # issue times well after sunrise
    # Targets up to 83 were issued at or before interval 79: they still see the index of 0.5.
    np.testing.assert_allclose(f.iloc[74:84], 0.5 * cs.iloc[74:84], rtol=1e-9)
    # The first target issued after the change sees it.
    assert f.iloc[84] == pytest.approx(cs.iloc[84])


def test_persistence_and_climatology():
    s = pd.Series(np.arange(8.0), index=pd.date_range("2022-01-01", periods=8, freq="15min"))
    assert persistence(s, 2).tolist()[2:] == s.tolist()[:-2]
    table = climatology_table(s)
    c = climatology(s.index, table)
    assert c.equals(s.astype(float).rename(None))  # one value per (month, time of day)
