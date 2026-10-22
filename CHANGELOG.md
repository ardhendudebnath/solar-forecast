# Changelog

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

### Added

- Data loader for two DOE 2023 Solar Data Prize plants (OEDI PVDAQ): local-time timestamps with
  daylight saving converted to UTC, sentinels and invalid readings removed, dead irradiance
  sensors and outage days detected (`data/README.md` records what the checks found).
- pvlib clear-sky reference for fixed-tilt and single-axis tracker plants.
- Baselines: persistence, smart persistence, climatology.
- Ridge and LightGBM candidates on lagged clear-sky index, clear-sky, solar-position and calendar
  features, selected on 2022; an irradiance-sensor variant reported alongside.
- Day-block bootstrap intervals and a one-command runner (`scripts/run_experiment.py`).
