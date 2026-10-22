import numpy as np
import pandas as pd
import pytest

from solarcast.data import (
    Plant,
    clean_power,
    drop_dead_days,
    load_plant,
    outage_days,
    to_utc,
)

TZ = "America/Denver"


def plant(**files) -> Plant:
    return Plant(
        plant_id="1",
        name="test",
        location="Somewhere, CO",
        timezone=TZ,
        latitude=40.0,
        longitude=-105.0,
        elevation_m=1500.0,
        capacity_kw_dc=1000.0,
        tracking=False,
        tilt=25.0,
        azimuth=180.0,
        files=files,
    )


def test_to_utc_handles_daylight_saving_both_ways():
    # 2021-11-07 01:30 happens twice in Denver: first as MDT (07:30 UTC), then MST (08:30 UTC).
    local = pd.Series(
        ["2021-11-07 00:30", "2021-11-07 01:30", "2021-11-07 01:30", "2021-11-07 02:30"]
    )
    utc = to_utc(local, TZ)
    assert [t.strftime("%H:%M") for t in utc] == ["06:30", "07:30", "08:30", "09:30"]
    # 2021-03-14 02:30 does not exist in Denver: dropped rather than guessed.
    gap = to_utc(pd.Series(["2021-03-14 01:30", "2021-03-14 02:30", "2021-03-14 03:30"]), TZ)
    assert gap.isna().tolist() == [False, True, False]
    # Summer is UTC-6, winter UTC-7.
    assert to_utc(pd.Series(["2021-07-01 12:00"]), TZ)[0].hour == 18
    assert to_utc(pd.Series(["2021-01-01 12:00"]), TZ)[0].hour == 19


def test_clean_power_keeps_standby_as_zero_and_drops_invalid():
    s = pd.Series([-5.0, -100.0, 500.0, 3276.7])
    out = clean_power(s, capacity_kw=1000.0)
    assert out.iloc[0] == 0.0  # small night-time draw
    assert np.isnan(out.iloc[1])  # beyond standby: invalid
    assert out.iloc[2] == 500.0
    assert np.isnan(out.iloc[3])  # above 1.5 x capacity: a sentinel, not power


def _day(day: str, values) -> pd.Series:
    idx = pd.date_range(f"{day} 00:00", periods=len(values), freq="1h", tz=TZ).tz_convert("UTC")
    return pd.Series(values, index=idx, dtype=float)


def test_dead_sensor_days_are_blanked_whole_day_only():
    live = _day("2021-06-01", [0] * 6 + [200, 600, 900, 600, 200] + [0] * 13)
    dead = _day("2021-06-02", [0.0] * 24)
    out = drop_dead_days(pd.concat([live, dead]), TZ)
    assert out.loc[live.index].notna().all()  # night zeros on a live day are real
    assert out.loc[dead.index].isna().all()


def test_outage_days_need_sun_and_no_power():
    idx = pd.date_range("2021-06-01", periods=3 * 24, freq="1h", tz=TZ).tz_convert("UTC")
    poa = np.tile([0] * 6 + [300, 700, 900, 700, 300] + [0] * 13, 3).astype(float)
    power = poa * 0.8
    power[24:48] = 0.0  # day 2: sunny, no power -> outage
    poa[48:72] = 10.0  # day 3: dark, little power -> just cloudy, not an outage
    power[48:72] = 5.0
    frame = pd.DataFrame({"power_kw": power, "poa": poa}, index=idx)
    days = outage_days(frame, plant())
    assert [d.strftime("%Y-%m-%d") for d in days] == ["2021-06-02"]


@pytest.fixture
def raw_dir(tmp_path):
    d = tmp_path / "1"
    d.mkdir()
    local = pd.date_range("2021-06-01", periods=4 * 24 * 2, freq="15min")  # two days, local time
    hours = local.hour + local.minute / 60
    sun = np.clip(np.sin((hours - 5) / 14 * np.pi), 0, None)  # peaks at local noon
    stamp = local.strftime("%Y-%m-%d %H:%M:%S")
    pd.DataFrame({"measured_on": stamp, "p": 800 * sun}).to_csv(d / "power.csv", index=False)
    pd.DataFrame({"measured_on": stamp, "a": 1000 * sun, "b": 3276.7}).to_csv(
        d / "poa.csv", index=False
    )
    pd.DataFrame({"measured_on": stamp, "t": 68.0}).to_csv(d / "amb.csv", index=False)
    return tmp_path


def test_load_plant_end_to_end(raw_dir):
    p = plant(
        power={"file": "power.csv", "column": "p"},
        poa={"file": "poa.csv", "columns": ["a", "b"]},
        ambient={"file": "amb.csv", "column": "t", "unit": "degF"},
    )
    f = load_plant(p, raw_dir)
    assert list(f.columns) == ["power_kw", "poa", "ambient_c"]
    assert str(f.index.tz) == "UTC" and f.index.freqstr == "15min"
    assert f["ambient_c"].dropna().round(6).eq(20.0).all()  # 68 degF
    # Sensor "b" is pure sentinel: poa comes from "a" alone, not averaged with garbage.
    assert f["poa"].max() == pytest.approx(1000.0, rel=0.01)
    # Local 12:00 in June (MDT) is 18:00 UTC: the peak lands there.
    assert f["power_kw"].idxmax().hour == 18
