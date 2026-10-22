# Results: short-term solar power forecasts on two real plants

**Headline:** on real plants in a year the model never saw (January–October 2023), the forecast
beats smart persistence, the standard hard-to-beat baseline, at every horizon on both plants. At
the pre-registered 1-hour horizon its RMSE is **14% lower at plant 2107** and **11% lower at plant
9068**, with 95% intervals well above zero. **The pre-registered criterion is met.**

The criterion, splits, baselines and scoring rules were committed in
[`preregistration.md`](preregistration.md) and pushed before the test year was used; the code that
produced this result was committed before the run.

## The result

Test period January–October 2023 (304 days per plant), daytime intervals (sun more than 5° above
the horizon). RMSE in % of DC capacity; skill = 1 − RMSE(model) / RMSE(reference). Intervals are
95% day-block bootstrap intervals (1,000 resamples of whole days).

### Plant 2107: Arbuckle, California (893 kW, fixed tilt)

| Horizon | Selected model | RMSE: smart persistence → model | **Skill vs smart persistence** | Skill vs persistence | Skill vs climatology |
|---|---|---|---|---|---|
| 15 min | LightGBM | 5.57 → 5.25 | **+0.057** (+0.046 to +0.066) | +0.176 | +0.651 |
| **1 hour** | LightGBM | 9.27 → 7.95 | **+0.142** (+0.124 to +0.160) | +0.471 | +0.472 |
| 4 hours | LightGBM | 15.78 → 12.21 | **+0.226** (+0.188 to +0.263) | +0.683 | +0.189 |

### Plant 9068: Kersey, Colorado (4,738 kW, single-axis tracker)

| Horizon | Selected model | RMSE: smart persistence → model | **Skill vs smart persistence** | Skill vs persistence | Skill vs climatology |
|---|---|---|---|---|---|
| 15 min | LightGBM | 8.49 → 8.06 | **+0.050** (+0.042 to +0.058) | +0.111 | +0.672 |
| **1 hour** | LightGBM | 15.79 → 14.10 | **+0.107** (+0.090 to +0.123) | +0.253 | +0.426 |
| 4 hours | Ridge | 26.62 → 21.77 | **+0.182** (+0.161 to +0.202) | +0.387 | +0.114 |

**Primary criterion** (1-hour skill vs smart persistence, 95% interval entirely above zero on both
plants): **met** (2107: +0.124 to +0.160; 9068: +0.090 to +0.123).

### What it shows

- **The gain grows with horizon.** At 15 minutes, the recent past is hard to improve on (about
  5%). At 4 hours, smart persistence degrades and the model's clear-sky, solar-position and
  seasonal features carry more of the forecast (18–23%).
- **It beats both baselines where each is strongest.** Smart persistence is the strongest
  baseline at 15 minutes and 1 hour; climatology is stronger than smart persistence at 4 hours
  on both plants (15.05 against 15.78, 24.57 against 26.62). The model beats both.
- **Test skill is a little lower than validation skill everywhere** (e.g. 9068 at 1 hour: +0.145
  on 2022, +0.107 on 2023). That is expected: the model was chosen on 2022, and 2023 weather
  differs. The test number is the one to quote.
- **The irradiance-sensor variant** (adding the on-site pyranometer's last 4 hours) helps
  slightly: +0.146 against +0.142 at 1 hour on 2107, +0.120 against +0.107 on 9068. It is not part
  of the criterion, because plant 9068 had no working pyranometer in its 2022 validation year.

## One correction, reported

The first test run scored **all of 2023**, which includes 10–16 days of November that the
pre-registered test period excludes (313 and 320 days instead of 304). That was the code not
matching the pre-registration. The split was corrected, committed and pushed
([`15fbee5`](https://github.com/ardhendudebnath/solar-forecast/commit/15fbee5e3ae7c82ae89f58f9027a15d6d39f3b8a)),
and the test re-run. The difference is negligible:

| 1-hour skill vs smart persistence | First run (all of 2023) | Corrected (Jan–Oct 2023) |
|---|---|---|
| Plant 2107 | +0.143 (+0.127 to +0.159) | **+0.142 (+0.124 to +0.160)** |
| Plant 9068 | +0.105 (+0.088 to +0.121) | **+0.107 (+0.090 to +0.123)** |

## Data exclusions

| | Plant 2107 | Plant 9068 |
|---|---|---|
| Test days | 304 | 304 |
| Outage days (excluded) | 0 | 0 |
| Daytime intervals without measured power (excluded) | 97 of 14,173 | 83 of 14,183 |
| Intervals any forecast could not cover | 0 | 0 |

The raw data needed real cleaning before any of this was possible: see
[`data/README.md`](../data/README.md). Highlights: timestamps in local time with daylight saving,
one plant's published meter file being a copy of its wind-speed file (excluded), and years of
failed pyranometers at plant 9068.

## Limitations

- **Two plants, one test year.** Both are in the western US. The result shows the method works on
  these plants in 2023, not everywhere.
- **No weather forecasts.** Inputs are on-site history, a clear-sky model and the calendar.
  Numerical weather predictions would likely help at 4 hours and beyond, and are the obvious next
  step; they are not available from this environment.
- **Generic tracker settings.** Plant 9068's clear-sky model assumes a 60° tracker limit and a
  typical ground coverage ratio, which leaves some error at sunrise and sunset. The models learn
  around it, but plant-specific values would sharpen the reference.
- **Fixed model settings.** LightGBM and Ridge use one fixed configuration each, chosen before the
  run; only the choice between them was made on validation data. Tuning on validation could add
  skill, but was not part of this experiment.

## Reproduce

```bash
pip install -e ".[dev]"
# download the raw files listed in data/README.md into data/raw/<plant>/
python scripts/run_experiment.py --split validation   # model development (2022)
python scripts/run_experiment.py --split test         # the single test run (Jan-Oct 2023)
```
