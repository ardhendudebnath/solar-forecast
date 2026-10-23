# Changelog

## 0.2.0 (2026-10-23)

A second pre-registered experiment: probabilistic forecasts and a replication, tested on 2024,
a year published after v0.1.

### Results

- **Only the calibration criterion is met.** At 1 hour the quantile model's 90% intervals cover
  0.897 (plant 2107) and 0.889 (plant 9068) of actual values (P2). At plant 2107 it beats PeEn,
  CH-PeEn and SP-Err on CRPS (+0.390, +0.528, +0.246), the v0.1 point result replicates (+0.125
  RMSE skill vs smart persistence) and the median forecast beats smart persistence by MAE
  (+0.203). At plant 9068 it loses to SP-Err (−0.198), the point model loses to smart persistence
  (−0.108) and the median loses by MAE (−0.279), so P1, S1 and S2 are not met
  (`reports/results_v0.2.md`).
- **Cause, found after the test:** plant 9068's published 2024 meter series reads about half of
  the plant's inverter total from January to July and zero or impossible spikes from August,
  while the inverters run normally. A post-hoc re-run on the inverter total passes all four
  criteria at 9068; it was chosen after the result, so the verdicts stand.
- **Protocol lesson:** the pre-test check of the 2024 files was structural only. Future
  pre-registrations here check new data against an independent signal and pre-register a fallback.
- **Pre-test amendment:** LightGBM's histogram method is fixed (`force_col_wise=True`), because
  its automatic choice depends on machine load and changed one v0.1 number in the sixth decimal.

### Added

- `solarcast.probabilistic`: LightGBM quantile regression (19 levels) and the PeEn, CH-PeEn and
  SP-Err baselines; CRPS, coverage, interval width and reliability, with day-block intervals.
- `scripts/run_v02.py` (the pre-registered run) and `scripts/explore_9068_inverters.py`
  (post-hoc, labelled as such).
- The loader reads one signal from several files; the 2024 files are configured.

## 0.1.0 (2026-10-22)

First release: the pre-registered experiment and its result.

### Results

- **Pre-registered criterion met.** On January–October 2023, never used for fitting or model
  choice, the selected model's 1-hour RMSE skill against smart persistence is +0.142
  (95% day-block interval +0.124 to +0.160) at plant 2107 and +0.107 (+0.090 to +0.123) at plant
  9068. It beats smart persistence at 15 minutes, 1 hour and 4 hours on both plants, and
  climatology at 4 hours (`reports/results.md`).
- The first test run scored all of 2023 instead of the pre-registered January–October; the split
  was corrected and the test re-run, with a negligible difference. Both runs are reported.
- By mean absolute error, the model is worse than smart persistence at plant 9068 at 15 minutes
  (−0.071) and 1 hour (−0.048); it cuts large errors more than typical ones there.
- A code review after the test run fixed four issues (outage-day count, scoring window, MAE skill
  not computed, timestamp column by position). No score changed; each fix and its effect is
  recorded in `reports/results.md`.

### Added

- Data loader for two DOE 2023 Solar Data Prize plants (OEDI PVDAQ): local-time timestamps with
  daylight saving converted to UTC, sentinels and invalid readings removed, dead irradiance
  sensors and outage days detected (`data/README.md` records what the checks found).
- pvlib clear-sky reference for fixed-tilt and single-axis tracker plants.
- Baselines: persistence, smart persistence, climatology.
- Ridge and LightGBM candidates on lagged clear-sky index, clear-sky, solar-position and calendar
  features, selected on 2022; an irradiance-sensor variant reported alongside.
- Day-block bootstrap intervals and a one-command runner (`scripts/run_experiment.py`).
