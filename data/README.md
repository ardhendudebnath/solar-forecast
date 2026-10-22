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

## The 2024 files (v0.2): structural check only

Published after v0.1 (2107 in June 2025, 9068 in June 2025). Checked before the v0.2
pre-registration for structure only; no forecast was made and no score computed.

- **Same sensors:** every column used has the same name and sensor id as in the earlier files.
  Plant 9068's meter power (`meter_ac_power_(kw)_meter_150150`) moved from the `ac_power` file
  to `9068_meter_data_20240101_20250430.csv`.
- **Same timestamps:** local clock time with daylight saving. The spring gap falls at 02:00 on
  2024-03-10 (2107) and 2025-03-09 (9068); 2024-11-03 has exactly one day's rows, so the repeated
  autumn hour is absent, as in the earlier files. No duplicated timestamps, all files sorted.
- **Coverage:** 2107 meter data runs to 2024-11-30 but its irradiance ends 2024-11-01, so the
  v0.2 test period is January–October 2024. Plant 9068 runs to 2025-04-30 (2025 is not used) and
  has gaps: no meter data from 2024-02-29 to 2024-04-08 (39 days), and about 20 shorter gaps of
  up to 2.5 days. Intervals without measured power are excluded from scoring and counted.
- Between the old files (ending November 2023) and the 2024 files there is no data.

## Download

```bash
B=https://oedi-data-lake.s3.amazonaws.com/pvdaq/2023-solar-data-prize
for f in 2107_meter_15m_data 2107_irradiance_data 2107_environment_data; do
  curl -o data/raw/2107/$f.csv --create-dirs $B/2107_OEDI/data/$f.csv; done
for f in 9068_ac_power_data 9068_irradiance_data 9068_environment_data; do
  curl -o data/raw/9068/$f.csv --create-dirs $B/9068_OEDI/data/$f.csv; done
```

For v0.2 (2024 test year), also:

```bash
for f in 2107_meter_15m_data_2024 2107_irradiance_data_2024 2107_environment_data_2024; do
  curl -o data/raw/2107/$f.csv --create-dirs $B/2107_OEDI/data/$f.csv; done
for f in 9068_meter_data 9068_irradiance_data 9068_environment_data; do
  curl -o data/raw/9068/${f}_20240101_20250430.csv --create-dirs \
    $B/9068_OEDI/data/${f}_20240101_20250430.csv; done
```
