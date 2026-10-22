"""Reference forecasts. A forecast for t + h uses only data up to and including interval t.

Every function returns a Series aligned to the *target* time t + h, so it can be compared with
the actual value at the same index.
"""

from __future__ import annotations

import pandas as pd


def persistence(power: pd.Series, h: int) -> pd.Series:
    """p̂(t + h) = p(t)."""
    return power.shift(h)


def hourly_csi_median(power: pd.Series, cs_power: pd.Series, scored: pd.Series) -> pd.Series:
    """Training-period median clear-sky index by UTC hour of day (fallback for low sun)."""
    usable = scored & (cs_power > 0) & power.notna()
    csi = (power[usable] / cs_power[usable]).clip(0.0, 1.5)
    return csi.groupby(csi.index.hour).median()


def smart_persistence(
    power: pd.Series, cs_power: pd.Series, h: int, csi_by_hour: pd.Series, sun_up: pd.Series
) -> pd.Series:
    """Persist the clear-sky index: p̂(t + h) = p(t) · c(t + h) / c(t).

    ``sun_up`` marks intervals with the sun more than 5° above the horizon (zenith below 85°).
    When the issue time t is not one of them, c(t) is too small to divide by, and the forecast
    is c(t + h) times the training median clear-sky index for the target's hour.
    """
    stable = sun_up & (cs_power > 0)
    csi_now = (power / cs_power).where(stable).clip(0.0, 1.5)
    forecast = (csi_now * cs_power.shift(-h)).shift(h)  # issue time t -> target time t + h
    fallback_csi = pd.Series(cs_power.index.hour, index=cs_power.index).map(csi_by_hour)
    fallback = cs_power * fallback_csi.fillna(0.0)
    unstable_issue = (~stable).shift(h, fill_value=True).astype(bool)
    return forecast.where(~unstable_issue, fallback).where(power.shift(h).notna())


def climatology_table(power: pd.Series) -> pd.Series:
    """Training-period mean power by (month, UTC time of day)."""
    key = [power.index.month, power.index.hour * 60 + power.index.minute]
    return power.groupby(key).mean()


def climatology(index: pd.DatetimeIndex, table: pd.Series) -> pd.Series:
    """Climatology forecast for each target time in ``index`` (needs no recent data)."""
    key = pd.MultiIndex.from_arrays([index.month, index.hour * 60 + index.minute])
    return pd.Series(table.reindex(key).to_numpy(), index=index)
