# Pre-registration v0.2: probabilistic forecasts, tested on 2024

*Written and committed before any v0.2 code exists, and before the 2024 data is used for anything
except the structural checks in `data/README.md` (column names, timestamps, date ranges, gaps).
No forecast has been made for 2024.*

The v0.1 experiment ([`preregistration.md`](preregistration.md), [`results.md`](results.md)) is
finished and stays as published. This is a new experiment on data published after it: the DOE
data lake added 2024 files for both plants, so 2024 is a test year that no model or decision in
this repository has seen.

## Questions

1. **Probabilistic forecasts (primary).** Can quantile forecasts built from a plant's own recent
   power, a clear-sky model and the calendar beat the standard probabilistic baselines, and are
   their intervals calibrated?
2. **Replication.** Does the v0.1 point-forecast result (beating smart persistence at 1 hour)
   hold on a new year?
3. **The MAE gap.** In v0.1, plant 9068's point forecast was worse than smart persistence by mean
   absolute error at 1 hour. Does a median forecast, trained on absolute error, fix that?

## Data and splits

Same plants, loader, cleaning rules and scored intervals as v0.1 (see `data/README.md`). The 2024
files are appended to the earlier ones per signal; plant 9068's meter column (same sensor id,
150150) is in `9068_meter_data_20240101_20250430.csv` from 2024.

| Plant | Train | Validation | Test |
|---|---|---|---|
| 2107 Arbuckle, CA (fixed tilt) | 2017-01 – 2022-12 | 2023 (data ends 2023-11) | **2024-01 – 2024-10** |
| 9068 Kersey, CO (tracker) | 2017-08 – 2022-12 | 2023 (data ends 2023-11) | **2024-01 – 2024-10** |

- Splits are calendar years in local time. The test period ends in October because plant 2107's
  irradiance file, which outage detection needs, ends on 2024-11-01. Data from 2025 is not used.
- Scoring as v0.1: daytime (zenith below 85°), measured power, not an outage day, and the whole
  feature window inside the partition. Every forecast is scored on the same intervals; intervals
  any forecast cannot cover are excluded for all and counted.
- Horizons h = 1, 4 and 16 intervals (15 minutes, 1 hour, 4 hours). All are reported; the
  criteria use 1 hour.

## Probabilistic forecasts

Every probabilistic forecast is a set of **19 quantiles, τ = 0.05, 0.10, …, 0.95**, of per-unit
power at t + h, using data up to interval t only. CSI below is the clear-sky index (power over
clear-sky power, clipped to [0, 1.5]); c is clear-sky power, fitted on training data as in v0.1.

**Model: LightGBM quantile regression.** One model per τ, plant and horizon, objective
`quantile` with alpha = τ, on the v0.1 features (`solarcast.features.build`) and the v0.1 fixed
settings (400 trees, learning rate 0.05, 31 leaves, at least 100 rows per leaf, random_state 0).
Each predicts CSI(t + h); predictions are clipped to [0, 1.5], sorted across τ for each interval
(so quantiles never cross), and multiplied by c(t + h). Nothing is tuned and there is no model
choice.

**Baselines** (from Doubleday, Van Scyoc Hernandez and Hodge, *Benchmark probabilistic solar
forecasts*, Solar Energy 2020, plus a persistence-error baseline):

1. **PeEn (persistence ensemble).** Members are the CSI values at t, t − 1, …, t − 15 (last
   4 hours) that are valid (sun above 5°, power measured). Quantile τ of the members (linear
   interpolation) times c(t + h). With fewer than 4 valid members, CH-PeEn is used instead.
2. **CH-PeEn (complete-history persistence ensemble).** Training-period empirical quantiles of
   CSI for the target's month and 15-minute UTC time of day, times c(t + h). A month × time cell
   with fewer than 20 training values gives no forecast (excluded and counted, as above).
3. **SP-Err (smart persistence plus its training errors).** CSI(t) plus the training-period
   quantile τ of CSI(t + h) − CSI(t) for the target's UTC hour, clipped to [0, 1.5], times
   c(t + h). Where CSI(t) is not valid, CH-PeEn is used instead.

## Metrics

- **CRPS**, approximated from the quantiles: CRPS ≈ (2 / 19) Σ_τ pinball_τ, with
  pinball_τ(q, y) = max(τ (y − q), (τ − 1)(y − q)), in per-unit power, averaged over scored
  intervals. **CRPS skill** = 1 − CRPS(model) / CRPS(baseline).
- **Coverage** of the central 90% interval [q0.05, q0.95] and the central 80% interval
  [q0.10, q0.90]: the share of scored intervals whose actual value lies inside (ends included).
- Also reported: mean width of the central 90% interval (sharpness) and the share of actual
  values below each quantile (a reliability table).
- **Uncertainty:** day-block bootstrap, 1,000 resamples of whole test days, seed 0, as in v0.1.

## Criteria

**Primary criterion (P1).** At 1 hour, the quantile model's CRPS skill has a 95% interval entirely
above 0 against **each** of PeEn, CH-PeEn and SP-Err, on **both** plants.

**Calibration criterion (P2).** At 1 hour, the central 90% interval's coverage lies between 0.85
and 0.95 on both plants.

**Secondary (S1, replication).** The v0.1 point pipeline, unchanged except for the splits above
(Ridge and LightGBM fitted on training data, the one with lower 2023 RMSE selected), has 1-hour
RMSE skill against smart persistence with a 95% interval entirely above 0 on both plants.

**Secondary (S2, the MAE gap).** At plant 9068, the quantile model's median (τ = 0.5) has 1-hour
MAE skill against smart persistence with a 95% interval entirely above 0. The same number is
reported for plant 2107.

Each criterion gets its own verdict; meeting one does not excuse failing another. Everything
else (all horizons, every baseline, coverage, width, reliability, exclusion counts) is reported
whatever the outcome.

## What validation (2023) is for

Checking the code runs and the forecasts are sane, and the S1 model choice. The quantile model has
no settings chosen on validation. If validation shows a defect in a definition above (a bug, not
a disappointing number), the fix is recorded in a dated amendment below, with its reason, before
the test run.

## Commitments

- The 2024 test period is evaluated once, after this file, any amendments and the code that
  produces the result are committed and pushed. If a criterion fails, it is reported as failed.
- Changes after the test run are limited to fixing demonstrable bugs, each recorded with its
  effect on the result.

## Amendments

**2026-10-22, before the test run: LightGBM's histogram method is fixed.** Re-running v0.1 to check
that the v0.2 loader changes left it untouched reproduced every number except one in the
irradiance-sensor variant (plant 9068, 4 hours, LightGBM), which differed in the sixth decimal
(RMSE 0.217441 against 0.217442). The data was identical; the cause is that LightGBM chooses
between col-wise and row-wise histogram construction by timing both, so under different machine
load it can choose differently and round differently (forcing each reproduces the two values
exactly). All LightGBM models, v0.1 and v0.2, now use `force_col_wise=True`, the choice that
reproduces the published v0.1 results. This changes no model setting, only removes a source of
run-to-run variation. Found while checking the code on validation data; no 2024 forecast had
been made.
