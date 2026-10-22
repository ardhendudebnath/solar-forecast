# Data

Raw data is **not** committed. Download it into `data/raw/<plant id>/`.

## Source

DOE **2023 Solar Data Prize** datasets in NREL's PV Data Acquisition (PVDAQ) collection on the
Open Energy Data Initiative data lake: `s3://oedi-data-lake/pvdaq/2023-solar-data-prize/`
(public, no account needed; HTTPS at `https://oedi-data-lake.s3.amazonaws.com/`).

Licence: the PVDAQ public datasets, which include the prize data, are listed under
[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/) in the
[data.gov catalog](https://catalog.data.gov/dataset/photovoltaic-data-acquisition-pvdaq-public-datasets).
That listing is for the parent collection; no separate licence is published for the prize folder.
Cite the dataset as NREL, *Photovoltaic Data Acquisition (PVDAQ) Public Datasets*,
doi:[10.25984/1846021](https://dx.doi.org/10.25984/1846021). This repository redistributes no
data, only code that downloads and reads it.

| Plant | Location | DC capacity | Mount | Files used | Period |
|---|---|---|---|---|---|
| 2107 Farm Solar Array | Arbuckle, CA | 893 kW | fixed, 25° tilt, south | `2107_meter_15m_data.csv`, `2107_irradiance_data.csv`, `2107_environment_data.csv` | 2017-01 – 2023-11 |
| 9068 SR_CO | Kersey, CO | 4,738 kW | single-axis tracker | `9068_ac_power_data.csv`, `9068_irradiance_data.csv`, `9068_environment_data.csv` | 2017-08 – 2023-11 |

## What the data check found (before any model)

- **Timestamps are local clock time with daylight saving**, not UTC: plant 9068 produces from
  about 05:50 to 20:05 in June and 07:35 to 16:15 in December, matching Mountain Daylight and
  Standard Time. The loader localises each plant to its IANA time zone and converts to UTC.
- **Plant 2105 (Maui Ocean Center) is excluded.** Its published meter file is a copy of its
  wind-speed file: all 171,648 values are identical, and uncorrelated with irradiance.
- **Plant 9068's pyranometers fail for years.** Pad 1 reads zero at midday in 2019–2022, pad 2
  in 2022. Before the fix, power and irradiance correlated at 0.01–0.36 in those years; using
  the live sensor(s) per day brings every year to 0.85–0.98. 2022 has no live irradiance.
- **Sentinel values** (e.g. 3276.7, a 16-bit error code) and night-time negative power are in
  the raw files; the loader blanks invalid readings and treats small negatives as standby (0).
- **Plant 2107 reports ambient temperature in °F.**
- **Meter and irradiance align at zero lag** on plant 2107 (correlation 0.976, against 0.974
  and 0.954 at ±1 interval), so no interval-label shift is applied.

## Download

```bash
B=https://oedi-data-lake.s3.amazonaws.com/pvdaq/2023-solar-data-prize
for f in 2107_meter_15m_data 2107_irradiance_data 2107_environment_data; do
  curl -o data/raw/2107/$f.csv --create-dirs $B/2107_OEDI/data/$f.csv; done
for f in 9068_ac_power_data 9068_irradiance_data 9068_environment_data; do
  curl -o data/raw/9068/$f.csv --create-dirs $B/9068_OEDI/data/$f.csv; done
```
