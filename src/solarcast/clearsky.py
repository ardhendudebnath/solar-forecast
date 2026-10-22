"""Clear-sky irradiance and power for a plant: the physics reference every forecast is judged by.

For each 15-minute interval (evaluated at its midpoint), pvlib's Ineichen model with
climatological Linke turbidity gives clear-sky GHI, DNI and DHI. These are transposed to the
array plane: fixed tilt and azimuth, or a single-axis tracker (north-south axis, backtracking).
Clear-sky *power* is the plane-of-array value times one scale factor per plant, capped at the
plant's observed maximum (inverter clipping). Both the factor and the cap are fitted on training
data only.
"""

from __future__ import annotations

import pandas as pd
import pvlib

from solarcast.data import FREQ, Plant

HALF_INTERVAL = pd.Timedelta(FREQ) / 2
TRACKER_MAX_ANGLE = 60.0
TRACKER_GCR = 0.35  # typical ground coverage ratio; only affects backtracking near sunrise/sunset
SCORED_ZENITH = 85.0  # daytime intervals that are scored and modelled
FIT_ZENITH = 70.0  # intervals used to fit the clear-sky scale factor
SCALE_QUANTILE = 0.90  # clear periods dominate the upper tail of power / clear-sky irradiance


def solar_geometry(plant: Plant, index: pd.DatetimeIndex) -> pd.DataFrame:
    """Solar position and clear-sky plane-of-array irradiance at each interval's midpoint."""
    mid = index + HALF_INTERVAL
    loc = pvlib.location.Location(
        plant.latitude, plant.longitude, tz="UTC", altitude=plant.elevation_m
    )
    sun = loc.get_solarposition(mid)
    sky = loc.get_clearsky(mid, model="ineichen", solar_position=sun)
    if plant.tracking:
        track = pvlib.tracking.singleaxis(
            sun["apparent_zenith"],
            sun["azimuth"],
            axis_tilt=plant.tilt,
            axis_azimuth=plant.azimuth,
            max_angle=TRACKER_MAX_ANGLE,
            backtrack=True,
            gcr=TRACKER_GCR,
        )
        tilt = track["surface_tilt"].fillna(0.0)
        azimuth = track["surface_azimuth"].fillna(plant.azimuth)
    else:
        tilt, azimuth = plant.tilt, plant.azimuth
    poa = pvlib.irradiance.get_total_irradiance(
        tilt, azimuth, sun["apparent_zenith"], sun["azimuth"], sky["dni"], sky["ghi"], sky["dhi"]
    )["poa_global"]
    out = pd.DataFrame(
        {
            "zenith": sun["apparent_zenith"].to_numpy(),
            "azimuth": sun["azimuth"].to_numpy(),
            "cs_poa": poa.clip(lower=0.0).fillna(0.0).to_numpy(),
        },
        index=index,
    )
    out.loc[out["zenith"] >= 90.0, "cs_poa"] = 0.0
    return out


def fit_scale(power_kw: pd.Series, geometry: pd.DataFrame) -> tuple[float, float]:
    """(kW per W/m² of clear-sky POA, power cap in kW), from training data only."""
    day = (geometry["zenith"] < FIT_ZENITH) & (geometry["cs_poa"] > 0) & power_kw.notna()
    ratio = power_kw[day] / geometry.loc[day, "cs_poa"]
    if ratio.empty:
        raise ValueError("No daytime training data to fit the clear-sky scale")
    return float(ratio.quantile(SCALE_QUANTILE)), float(power_kw.max())


def clearsky_power(geometry: pd.DataFrame, scale: float, cap_kw: float) -> pd.Series:
    return (geometry["cs_poa"] * scale).clip(upper=cap_kw).rename("cs_power_kw")


def is_scored(geometry: pd.DataFrame) -> pd.Series:
    """Daytime intervals that are modelled and scored (zenith below SCORED_ZENITH)."""
    return (geometry["zenith"] < SCORED_ZENITH).rename("scored")


__all__ = [
    "SCORED_ZENITH",
    "clearsky_power",
    "fit_scale",
    "is_scored",
    "solar_geometry",
]
