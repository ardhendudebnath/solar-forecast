# Results v0.2: probabilistic forecasts, tested on 2024

**Headline:** on the pre-registered 2024 test, **only the calibration criterion is met**. The
quantile forecasts beat every probabilistic baseline at plant 2107 and their 90% intervals are
well calibrated on both plants. At plant 9068 the model loses to the persistence-based baselines
and three of the four criteria fail.

The cause, found after the test, is plant 9068's 2024 meter data: from January to July it reads
about half of what the plant's own inverters report, and from August it reads zero or impossible
spikes while the inverters run normally. A post-hoc re-run on the inverter total passes all four
criteria at 9068, but it was chosen after seeing the result, so it **does not change the
verdicts**. The lesson is in the pre-registration: the 2024 files were checked for structure
only, and a check against an independent signal would have caught this before the test.

The criteria, splits, models and baselines were committed in
[`preregistration_v0.2.md`](preregistration_v0.2.md) before any v0.2 code existed; one amendment
(fixing LightGBM's histogram method, which changes no setting) was pushed before the test run.

## The pre-registered result

Test period January–October 2024 (305 days per plant), daytime intervals, 19 quantiles per
forecast. CRPS in % of DC capacity; skill = 1 − CRPS(model) / CRPS(baseline). Brackets are 95%
day-block bootstrap intervals (1,000 resamples).

### Plant 2107: Arbuckle, California (fixed tilt)

| Horizon | CRPS: model / PeEn / CH-PeEn / SP-Err | Skill vs PeEn | vs CH-PeEn | vs SP-Err | 90% coverage | 90% width |
|---|---|---|---|---|---|---|
| 15 min | 1.66 / 3.75 / 6.34 / 2.05 | +0.558 | +0.739 | +0.192 (+0.178 to +0.207) | 0.901 | 8.9 |
| **1 hour** | 2.99 / 4.91 / 6.34 / 3.97 | **+0.390** (+0.361 to +0.423) | **+0.528** (+0.487 to +0.568) | **+0.246** (+0.227 to +0.265) | **0.897** | 17.0 |
| 4 hours | 5.10 / 7.07 / 6.34 / 6.76 | +0.278 | +0.195 | +0.245 (+0.220 to +0.270) | 0.904 | 29.6 |

Point model (S1), RMSE skill vs smart persistence: +0.053, **+0.125** (+0.106 to +0.143), +0.162.
Median (S2), MAE skill vs smart persistence: +0.101, **+0.203** (+0.179 to +0.227), +0.191.

### Plant 9068: Kersey, Colorado (single-axis tracker)

71 outage days and 5,986 of 14,218 daytime intervals without power were excluded (see below).

| Horizon | CRPS: model / PeEn / CH-PeEn / SP-Err | Skill vs PeEn | vs CH-PeEn | vs SP-Err | 90% coverage | 90% width |
|---|---|---|---|---|---|---|
| 15 min | 3.67 / 5.94 / 17.82 / 3.43 | +0.382 | +0.794 | −0.071 (−0.092 to −0.049) | 0.886 | 28.0 |
| **1 hour** | 6.98 / 7.68 / 17.69 / 5.83 | **+0.091** (+0.042 to +0.137) | **+0.605** (+0.576 to +0.633) | **−0.198** (−0.239 to −0.158) | **0.889** | 46.3 |
| 4 hours | 13.79 / 12.64 / 17.68 / 11.24 | −0.090 | +0.220 | −0.227 (−0.279 to −0.173) | 0.816 | 53.0 |

Point model (S1), RMSE skill vs smart persistence: −0.066, **−0.108** (−0.152 to −0.070), +0.136.
Median (S2), MAE skill vs smart persistence: −0.082, **−0.279** (−0.346 to −0.220), −0.195.

### Verdicts (1 hour)

| Criterion | Plant 2107 | Plant 9068 | Verdict |
|---|---|---|---|
| **P1**: CRPS skill above 0 against PeEn, CH-PeEn and SP-Err | yes | no (SP-Err −0.198) | **NOT MET** |
| **P2**: 90% interval coverage within 0.85–0.95 | 0.897 | 0.889 | **MET** |
| **S1**: point-model RMSE skill vs smart persistence above 0 (replication) | +0.125 | −0.108 | **NOT MET** |
| **S2**: median MAE skill vs smart persistence above 0 at 9068 | (+0.203) | −0.279 | **NOT MET** |

## What went wrong at plant 9068

The plant's 2024 **meter** series, the pre-registered power signal, is inconsistent with the
plant's two **inverters**, which are published in the same release and run normally all year.
Median daily maximum AC power (kW):

| Month | Inverter 1 + 2, 2023 | Meter, 2023 | Inverter 1 + 2, 2024 | Meter, 2024 |
|---|---|---|---|---|
| January | 2,611 | 2,535 | 2,594 | 1,812 |
| April | 3,676 | 3,510 | 3,720 | 1,959 |
| June | 3,680 | 3,503 | 3,788 | 1,944 |
| August | 3,685 | 3,510 | 3,760 | 0 |
| October | 2,997 | 2,927 | 2,912 | 0 |

- **2017–2023:** the meter's daily peak is 0.95–1.01 times the inverter total's (April–August
  medians by year), capped at the 3,500 kW export limit, as expected.
- **January–July 2024:** 0.52 times the inverter total, as if the meter saw one inverter.
- **August–October 2024:** the daily peak is near zero on 67 of 92 days, and above the export
  limit on 23 days in August and September, up to 16,595 kW in the raw 5-minute data. The loader
  removed readings above 1.5 × DC capacity (7,107 kW); those below it, up to about 7,000 kW,
  passed. Sunny days near zero were flagged as outage days (71 in the test period), which is why
  so much of 9068's test was excluded. By April 2025 the meter agrees with the inverters again.
- Plant 2107 is consistent: its daily peak power relative to peak irradiance is 0.64 in 2024
  against 0.67 in 2021–2023.

**Why this breaks the model and not the baselines.** The model learned the plant's usual level
of clear-sky index; a meter reading half the real output looks like permanent heavy cloud, so the
model forecasts too high: actual power fell below its median forecast 65% of the time at 1 hour,
against 50% for a calibrated median. Smart persistence and SP-Err persist the *current* ratio to
clear-sky power, so a constant scale error largely cancels out of them.

## Post-hoc: plant 9068 with inverter power (not part of the verdicts)

To see whether the method works at 9068 when the power series is consistent,
[`scripts/explore_9068_inverters.py`](../scripts/explore_9068_inverters.py) re-runs the whole v0.2
evaluation with power taken as the inverter total, for every year (so training and test use one
series). Everything else is unchanged.

| 1 hour, 2024 | Pre-registered (meter) | Post-hoc (inverters) |
|---|---|---|
| CRPS skill vs PeEn / CH-PeEn / SP-Err | +0.091 / +0.605 / −0.198 | +0.351 / +0.396 / **+0.132** (+0.115 to +0.148) |
| 90% coverage | 0.889 | 0.858 |
| Point RMSE skill vs smart persistence | −0.108 | **+0.128** (+0.113 to +0.143) |
| Median MAE skill vs smart persistence | −0.279 | **+0.079** (+0.060 to +0.097) |
| Daytime intervals excluded | 5,986 of 14,218 | 616 of 14,218 |

On the inverter series all four criteria would be met at 9068, and the 2023 validation numbers
are close to the meter-based ones (1-hour CRPS skill vs SP-Err +0.150 against +0.137), as
expected in a year when meter and inverters agree. This is evidence for the diagnosis, not a pass:
the series was chosen after the test showed a problem, it is measured at a different point (the
inverters, not the revenue meter), and with a free choice of signal after the fact almost any
failure can be explained away. The pre-registered verdicts stand.

## Other findings

- **Calibration held on new data.** On 2024 the 90% intervals covered 0.897 and 0.889 at 1 hour,
  and 2107's reliability is close to ideal (actual below the 5%, 50% and 95% quantiles in 4.5%,
  47.5% and 94.6% of intervals at 15 minutes). On 2023 the 4-hour intervals were too narrow
  (0.82 coverage at both plants); on 2024 at 2107 they were not (0.904).
- **The model beats SP-Err where the data is sound,** by 19–25% at 2107 and 11–15% at 9068 on the
  inverter series, so the gain over the strongest baseline is not only an ensemble artefact.
- **The v0.1 result replicates at 2107** (1-hour RMSE skill +0.125 on 2024, +0.142 on 2023),
  and the median forecast fixes the MAE gap there too (+0.203).
- **PeEn is badly under-dispersed** (90% coverage 0.54–0.64): the last 4 hours of clear-sky index
  vary less than the next hour does.

## What the protocol missed, and what changes

The pre-registration limited the pre-test look at the 2024 files to structure (columns,
timestamps, coverage), to avoid seeing the test data. That was too strict in the wrong place: a
data check can compare one signal with another (meter against inverters, power against
irradiance) without computing any forecast or score. Future pre-registrations here will:

1. check a new period's power against an independent signal, month by month, before the test,
   and say in advance what happens to a plant that fails the check;
2. tighten the power validity bound from 1.5 × DC capacity to the plant's AC export limit;
3. pre-register a fallback signal (here, the inverter total) for when the primary one fails that
   check, so a failure like this is handled by a rule written before the result.

## Data exclusions

| | Plant 2107 | Plant 9068 |
|---|---|---|
| Test days | 305 | 305 |
| Outage days (excluded) | 0 | 71 |
| Daytime intervals without measured power (excluded) | 0 of 14,204 | 5,986 of 14,218 |
| Intervals a forecast could not cover (1 hour) | 8 (CH-PeEn) | 61 (smart persistence) |

## Reproducibility

Every LightGBM model now uses `force_col_wise=True` (the pre-test amendment). With it the
published v0.1 test results reproduce exactly; see the amendment for the one sensor-variant
model whose published validation numbers differ by at most 0.000016.

```bash
pip install -e ".[dev]"
# download the raw files listed in data/README.md, including the 2024 files
python scripts/run_v02.py --split validation
python scripts/run_v02.py --split test                 # the single pre-registered test run
python scripts/explore_9068_inverters.py --split test  # post-hoc, not part of the verdicts
```
