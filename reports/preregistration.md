# Pre-registration: short-term power forecasts against smart persistence

*Written and committed before any forecasting model is trained, and before the 2023 test data is
used for anything except the data checks in `data/README.md`.*

## Question

Can a model built on a plant's own recent power, a clear-sky physics model and the calendar
forecast its output 15 minutes to 4 hours ahead better than **smart persistence**, the standard
hard-to-beat baseline, on real plants in a year it has never seen?

## Data

Two DOE 2023 Solar Data Prize plants, loaded by `solarcast.data.load_plant` (15-minute UTC means):

| Plant | Location | Mount | Train | Validation | Test |
|---|---|---|---|---|---|
| 2107 | Arbuckle, CA | fixed tilt | 2017-01 – 2021-12 | 2022 | 2023-01 – 2023-10 |
| 9068 | Kersey, CO | single-axis tracker | 2017-09 – 2021-12 | 2022 | 2023-01 – 2023-10 |

- Splits are by calendar year in each plant's local time. Lagged features never reach across a
  split boundary: the first 4 hours of each partition are not scored.
- **Outage days** (`solarcast.data.outage_days`) and intervals with missing actual power are
  excluded from scoring; their counts per plant and split are reported.
- **Scored intervals:** daytime only, solar zenith angle below 85° at the interval midpoint.
  Night-time forecasts are trivially zero and would inflate every score.

## Target and horizons

- Target: AC power normalised by DC capacity (per-unit), at horizons **h = 1, 4 and 16
  intervals** (15 minutes, 1 hour and 4 hours ahead).
- A forecast for time t + h may use only data up to and including interval t.

## Baselines

1. **Persistence:** p̂(t + h) = p(t).
2. **Smart persistence (the reference):** the clear-sky index is persisted:
   p̂(t + h) = p(t) · c(t + h) / c(t), where c is the plant's clear-sky power. Where c(t) is too
   small to divide by (sun below 5°), the forecast is c(t + h) times the training-period median
   clear-sky index for that hour.
3. **Climatology:** the training-period mean per-unit power for the same month and 15-minute
   time of day.

Clear-sky power: pvlib Ineichen clear-sky irradiance (climatological Linke turbidity) transposed
to the array plane (fixed tilt or single-axis tracking per `configs/plants.yaml`), scaled to
power by one factor per plant fitted on training data only.

## Models

Candidates, each fitted per plant and per horizon on training data only:

- **Ridge regression** on lagged clear-sky index (last 4 hours), clear-sky power at t and t + h,
  solar position at t + h, and day-of-year and time-of-day terms.
- **LightGBM** on the same features.

The candidate with the lower validation RMSE (2022) is selected per plant and horizon; nothing is
tuned on 2023. A variant that adds the on-site irradiance sensor is reported separately and is
not part of the primary criterion (plant 9068 has no live irradiance sensor in 2022).

## Metric and criterion

- **Skill** = 1 − RMSE(model) / RMSE(smart persistence), on scored test intervals. Also reported:
  MAE skill, and skill against persistence and climatology.
- **Uncertainty:** 95% interval from a day-block bootstrap (1,000 resamples of whole test days,
  seed 0), so correlated intervals within a day are not counted as independent.

**Primary criterion:** at the **1-hour horizon**, the selected model's RMSE skill against smart
persistence has a 95% interval **entirely above 0 on both plants**. Anything else is reported as
not meeting the criterion.

**Also reported, whatever the outcome:** every plant × horizon × baseline combination, the
irradiance-sensor variant, and the outage and missing-data counts.

## Commitments

- The 2023 test period is evaluated once, after this file and the code that produces the result
  are committed. If the criterion fails, the result is reported as it stands; any later change is
  a new, separately pre-registered experiment.
- Changes to the evaluation code after the test run are limited to fixing demonstrable bugs, each
  recorded with its effect on the result.
