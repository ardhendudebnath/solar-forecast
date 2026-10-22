"""Forecast features, as pre-registered: built at issue time t, describing target time t + h.

- Clear-sky index (power / clear-sky power) at t and the 15 intervals before it (last 4 hours),
  missing where the sun is below 5° or power is missing.
- Clear-sky power at t and at t + h.
- Solar position at t + h (cosine of zenith, sine and cosine of azimuth).
- Day of year and UTC time of day of the target, as sine and cosine pairs.

Models predict the clear-sky index at t + h; the forecast is that index times clear-sky power at
t + h, and is scored as per-unit power.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

N_LAGS = 16  # last 4 hours at 15-minute resolution
CSI_CLIP = (0.0, 1.5)


def clear_sky_index(power: pd.Series, cs_power: pd.Series, sun_up: pd.Series) -> pd.Series:
    usable = sun_up & (cs_power > 0)
    return (power / cs_power).where(usable).clip(*CSI_CLIP)


def build(
    power: pd.Series,
    cs_power: pd.Series,
    geometry: pd.DataFrame,
    sun_up: pd.Series,
    h: int,
) -> tuple[pd.DataFrame, pd.Series]:
    """(features, target clear-sky index), both indexed by the *target* time t + h."""
    csi = clear_sky_index(power, cs_power, sun_up)
    issue = pd.DataFrame({f"csi_lag{k}": csi.shift(k) for k in range(N_LAGS)})
    issue["cs_now"] = cs_power
    # Move issue-time columns to the target time.
    x = issue.shift(h)
    x["cs_target"] = cs_power
    zen = np.radians(geometry["zenith"])
    azi = np.radians(geometry["azimuth"])
    x["cos_zenith"] = np.cos(zen)
    x["sin_azimuth"] = np.sin(azi)
    x["cos_azimuth"] = np.cos(azi)
    idx = x.index
    doy = 2 * np.pi * (idx.dayofyear - 1) / 365.25
    tod = 2 * np.pi * (idx.hour * 60 + idx.minute) / 1440
    x["sin_doy"], x["cos_doy"] = np.sin(doy), np.cos(doy)
    x["sin_tod"], x["cos_tod"] = np.sin(tod), np.cos(tod)
    return x, csi.rename("target_csi")
