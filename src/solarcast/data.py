"""Load one plant's raw PVDAQ files into a clean, regular 15-minute UTC frame.

Output columns: ``power_kw`` (AC, plant meter), ``poa`` (plane-of-array irradiance, W/m²) and
``ambient_c`` (°C), indexed by the UTC start of each 15-minute interval.

Cleaning rules, applied per signal before resampling:

- Timestamps are local clock time with daylight saving. They are localised to the plant's time
  zone (the repeated autumn hour is resolved by order, the missing spring hour cannot occur) and
  converted to UTC.
- Logger sentinels and physically impossible readings become missing: values outside each
  signal's valid range (e.g. 3276.7, a common 16-bit error code).
- Small negative power (the plant drawing standby power at night) is set to zero; large negative
  readings are invalid and become missing.
- Duplicate timestamps keep their first reading.
- Dead-sensor days: a day on which an irradiance sensor never exceeds ``DEAD_POA_MAX`` W/m² is
  missing for that sensor (a producing plant never sees a whole day without sunlight). With
  several plane-of-array sensors, ``poa`` is the mean of the live ones.
- Outage days: a day with strong measured sunlight but power that never exceeds
  ``OUTAGE_POWER_FRACTION`` of capacity is missing for power (plant or meter down). They are
  counted, not hidden: see :func:`outage_days`.

Missing values are left missing: models and metrics decide how to treat them, never the loader.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

FREQ = "15min"
# Valid ranges per signal; power is checked against the plant's capacity instead.
POA_RANGE = (-10.0, 1600.0)
AMBIENT_RANGE_C = (-45.0, 55.0)
STANDBY_FRACTION = 0.02  # negative power down to 2% of capacity counts as night-time standby
DEAD_POA_MAX = 50.0  # W/m²: a sensor whose daily maximum stays below this is dead that day
OUTAGE_POA_MAX = 500.0  # W/m²: a day this sunny...
OUTAGE_POWER_FRACTION = 0.02  # ...whose power never exceeds 2% of capacity is an outage day


@dataclass(frozen=True)
class Plant:
    plant_id: str
    name: str
    location: str
    timezone: str
    latitude: float
    longitude: float
    elevation_m: float
    capacity_kw_dc: float
    tracking: bool
    tilt: float
    azimuth: float
    files: dict


def load_plants(path: str | Path) -> dict[str, Plant]:
    with open(path) as fh:
        raw = yaml.safe_load(fh)["plants"]
    return {str(pid): Plant(plant_id=str(pid), **cfg) for pid, cfg in raw.items()}


def to_utc(local: pd.Series, timezone: str) -> pd.DatetimeIndex:
    """Local clock times (with daylight saving) to UTC.

    In the autumn repeated hour, readings are assumed to arrive in time order, so the first
    01:xx is daylight time and the second standard time. A spring-forward gap holds no readings;
    a reading timestamped inside it is invalid and is dropped (NaT).
    """
    idx = pd.DatetimeIndex(pd.to_datetime(local, errors="coerce"))
    first = ~pd.Series(idx).duplicated(keep="first").to_numpy()
    # A repeated wall-clock time is daylight time on its first appearance, standard on its second.
    localized = idx.tz_localize(timezone, ambiguous=first, nonexistent="NaT")
    return localized.tz_convert("UTC")


def _read_signal(path: Path, column: str, timezone: str) -> pd.Series:
    df = pd.read_csv(path, usecols=lambda c: c == column or c == "measured_on", low_memory=False)
    values = pd.to_numeric(df[column], errors="coerce")
    utc = to_utc(df.iloc[:, 0], timezone)
    s = pd.Series(values.to_numpy(), index=utc).dropna()
    s = s[s.index.notna()]
    return s[~s.index.duplicated(keep="first")].sort_index()


def clean_power(s: pd.Series, capacity_kw: float) -> pd.Series:
    standby = -STANDBY_FRACTION * capacity_kw
    s = s.where((s >= standby) & (s <= 1.5 * capacity_kw))
    return s.clip(lower=0.0)


def clean_range(s: pd.Series, low: float, high: float) -> pd.Series:
    return s.where((s >= low) & (s <= high))


def load_plant(plant: Plant, raw_dir: str | Path) -> pd.DataFrame:
    """Clean 15-minute UTC frame for one plant (see module docstring)."""
    raw_dir = Path(raw_dir) / plant.plant_id
    out = {}
    spec = plant.files
    power = _read_signal(raw_dir / spec["power"]["file"], spec["power"]["column"], plant.timezone)
    out["power_kw"] = clean_power(power, plant.capacity_kw_dc)
    columns = spec["poa"].get("columns") or [spec["poa"]["column"]]
    sensors = [
        drop_dead_days(
            clean_range(_read_signal(raw_dir / spec["poa"]["file"], c, plant.timezone), *POA_RANGE)
            .clip(lower=0.0)
            .resample(FREQ, label="left", closed="left")
            .mean(),
            plant.timezone,
        )
        for c in columns
    ]
    out["poa"] = pd.concat(sensors, axis=1).mean(axis=1)  # mean of the live sensors
    amb = _read_signal(raw_dir / spec["ambient"]["file"], spec["ambient"]["column"], plant.timezone)
    if spec["ambient"].get("unit", "degC") == "degF":
        amb = (amb - 32.0) * 5.0 / 9.0
    out["ambient_c"] = clean_range(amb, *AMBIENT_RANGE_C)
    # Mean over each 15-minute interval, labelled by its start; empty intervals stay missing.
    frame = pd.DataFrame(
        {k: v.resample(FREQ, label="left", closed="left").mean() for k, v in out.items()}
    ).asfreq(FREQ)
    frame.index.name = "timestamp_utc"
    outages = outage_days(frame, plant)
    local_day = frame.index.tz_convert(plant.timezone).normalize()
    frame.loc[local_day.isin(outages), "power_kw"] = float("nan")
    return frame


def _local_day(index: pd.DatetimeIndex, timezone: str) -> pd.DatetimeIndex:
    return index.tz_convert(timezone).normalize()


def drop_dead_days(s: pd.Series, timezone: str) -> pd.Series:
    """Blank whole local days on which an irradiance sensor never rose above DEAD_POA_MAX."""
    day = _local_day(s.index, timezone)
    daily_max = s.groupby(day).transform("max")
    return s.where(daily_max >= DEAD_POA_MAX)


def outage_days(frame: pd.DataFrame, plant: Plant) -> pd.DatetimeIndex:
    """Local days that were sunny (POA above OUTAGE_POA_MAX) while power stayed near zero."""
    day = _local_day(frame.index, plant.timezone)
    daily = frame[["power_kw", "poa"]].groupby(day).max()
    sunny = daily["poa"] >= OUTAGE_POA_MAX
    dark = daily["power_kw"] <= OUTAGE_POWER_FRACTION * plant.capacity_kw_dc
    return daily.index[sunny & dark]


def coverage(frame: pd.DataFrame) -> pd.Series:
    """Share of 15-minute intervals with a value, per column."""
    return frame.notna().mean().round(4)
