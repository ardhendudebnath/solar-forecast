# solar-forecast

Short-term solar power forecasting on **real PV plants**, judged against honest baselines with a
**pre-registered** evaluation.

On two US plants, in a year the model never saw, the forecast beats **smart persistence**, the
standard hard-to-beat baseline, at every horizon from 15 minutes to 4 hours. At 1 hour ahead its
error is **14% and 11% lower**, with 95% intervals well clear of zero.

## Results (test period January–October 2023)

| Plant | Mount | 15 min | **1 hour** | 4 hours |
|---|---|---|---|---|
| 2107 Arbuckle, CA (893 kW) | fixed tilt | +0.057 | **+0.142** (+0.124 to +0.160) | +0.226 |
| 9068 Kersey, CO (4.7 MW) | single-axis tracker | +0.050 | **+0.107** (+0.090 to +0.123) | +0.182 |

RMSE skill against smart persistence (1 − RMSE ratio). Intervals: 95% day-block bootstrap. At 4
hours the model also beats climatology (+0.19 and +0.11), the stronger baseline there.

**The pre-registered criterion is met**: 1-hour skill against smart persistence with a 95%
interval above zero on both plants. One caveat: by mean absolute error rather than RMSE, the model
is slightly worse than smart persistence at plant 9068 at 15 minutes and 1 hour. Full results, a
correction made during the test run, review fixes and limitations are in
[`reports/results.md`](reports/results.md).

## v0.2: probabilistic forecasts, tested on 2024

A second pre-registered experiment ([`reports/preregistration_v0.2.md`](reports/preregistration_v0.2.md))
added quantile forecasts and tested them, plus a replication of the result above, on 2024 data
published after v0.1. **Only the calibration criterion was met**:

| 1 hour, January–October 2024 | Plant 2107 | Plant 9068 | Verdict |
|---|---|---|---|
| CRPS skill vs the strongest baseline (SP-Err) | +0.246 | −0.198 | not met |
| 90% interval coverage (target 0.85–0.95) | 0.897 | 0.889 | **met** |
| Point model replication, RMSE skill vs smart persistence | +0.125 | −0.108 | not met |
| Median forecast, MAE skill vs smart persistence | +0.203 | −0.279 | not met |

Plant 2107 passes everything. At plant 9068, the published 2024 meter series turned out to read
about half of the plant's own inverter total for seven months and zero or impossible spikes after
that. A post-hoc re-run on the inverter total passes at 9068, but it was chosen after the result,
so the verdicts stand. The pre-test check of the 2024 files was structural only; comparing the
meter with the inverters would have caught this. Full write-up:
[`reports/results_v0.2.md`](reports/results_v0.2.md).

## How it was evaluated

1. **Data checks first.** The raw DOE data needed real work: local timestamps with daylight
   saving, one plant's meter file published as a copy of its wind-speed file, and years of failed
   pyranometers. Every finding is in [`data/README.md`](data/README.md).
2. **Pre-registration.** Splits, baselines, scoring rules and the success criterion were written
   and pushed in [`reports/preregistration.md`](reports/preregistration.md) before the test year
   was used.
3. **Chronological splits.** Train 2017–2021, choose between models on 2022, test once on
   January–October 2023. Training never sees a later target, and a test checks it.
4. **Strong baselines.** Smart persistence (persist how cloudy it is relative to clear sky),
   plain persistence and climatology, all scored on exactly the same intervals as the model.
5. **Honest uncertainty.** Intervals resample whole days, because errors within a day are
   correlated.

## How it works

- **Clear-sky reference** ([`clearsky.py`](src/solarcast/clearsky.py)): pvlib's Ineichen model
  transposed to the array plane (fixed tilt or single-axis tracking), scaled to each plant's power
  on training data.
- **Forecast** ([`features.py`](src/solarcast/features.py),
  [`experiment.py`](src/solarcast/experiment.py)): Ridge and LightGBM predict the clear-sky index at
  t + h from the last 4 hours of the plant's own clear-sky index, clear-sky power, solar position
  and calendar terms; the forecast is that index times clear-sky power.

## Quick start

```bash
pip install -e ".[dev]"
pytest -q
# download the raw files listed in data/README.md into data/raw/<plant>/, then
python scripts/run_experiment.py --split validation
python scripts/run_experiment.py --split test
python scripts/run_v02.py --split test   # v0.2 (needs the 2024 files)
```

## Repository layout

```
configs/plants.yaml        plant metadata and which raw columns to use
src/solarcast/             data loading, clear-sky model, baselines, features, experiment
scripts/run_experiment.py  v0.1: point forecasts, result table and verdict
scripts/run_v02.py         v0.2: probabilistic forecasts, a verdict per criterion
reports/                   pre-registration and results
data/README.md             data source, download and what the checks found
tests/                     unit tests, including leakage and selection checks
```

## Data

DOE 2023 Solar Data Prize datasets in NREL's PVDAQ collection on the Open Energy Data Initiative
data lake (`s3://oedi-data-lake/pvdaq/2023-solar-data-prize/`), licensed CC BY 4.0
(doi:[10.25984/1846021](https://dx.doi.org/10.25984/1846021)). No data is redistributed here.

## Licence

MIT, for the code. See [`LICENSE`](LICENSE).
