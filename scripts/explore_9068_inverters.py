"""Post-hoc analysis, NOT part of the pre-registered v0.2 result: plant 9068 with inverter power.

Plant 9068's published 2024 meter series is inconsistent with its own inverters: about half
their total from January to July 2024, then zeros and spikes from August, while both inverters
report normal output (see reports/results_v0.2.md). This re-runs the v0.2 evaluation for plant
9068 with power taken as the sum of its two inverters' AC power, for every year, so training and
test use one consistent series. It answers "does the method work when the power series is
consistent?", not whether the pre-registered criteria were met (they were not, at 9068).

    python scripts/explore_9068_inverters.py --split test

Writes artifacts/v02_<split>_9068_inverters.json and prints the same tables as run_v02.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from solarcast import experiment, probabilistic
from solarcast.data import FREQ, _read_files, clean_power, load_plant, load_plants, outage_days

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_v02 import HORIZONS, render  # noqa: E402

FILES = ["9068_ac_power_data.csv", "9068_ac_power_data_20240101_20250430.csv"]
INVERTERS = ["inverter_1_ac_power_(kw)_inv_150143", "inverter_2_ac_power_(kw)_inv_150144"]


def inverter_frame(raw_dir: Path):
    plant = load_plants(ROOT / "configs" / "plants.yaml")["9068"]
    frame = load_plant(plant, raw_dir)  # irradiance and temperature as pre-registered
    parts = [_read_files(raw_dir / plant.plant_id, FILES, c, plant.timezone) for c in INVERTERS]
    total = clean_power(parts[0] + parts[1], plant.capacity_kw_dc)
    frame["power_kw"] = total.resample(FREQ, label="left", closed="left").mean()
    outages = outage_days(frame, plant)
    local_day = frame.index.tz_convert(plant.timezone).normalize()
    frame.loc[local_day.isin(outages), "power_kw"] = float("nan")
    frame.attrs["outage_days"] = outages
    return plant, frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["validation", "test"], required=True)
    parser.add_argument("--raw-dir", default=ROOT / "data" / "raw")
    parser.add_argument("--out", default=ROOT / "artifacts")
    args = parser.parse_args()

    plant, frame = inverter_frame(Path(args.raw_dir))
    p = experiment.prepare(
        plant,
        frame,
        include_test=args.split == "test",
        splits=probabilistic.SPLITS,
        test_last_month=probabilistic.TEST_LAST_MONTH,
    )
    results = {
        "9068": {
            "counts": experiment.data_counts(p, args.split),
            "probabilistic": {
                str(h): v for h, v in probabilistic.evaluate(p, args.split, HORIZONS).items()
            },
            "point": {str(h): v for h, v in experiment.evaluate(p, args.split, HORIZONS).items()},
        }
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name = f"v02_{args.split}_9068_inverters.json"
    (out / name).write_text(json.dumps(results, indent=2, default=str))
    print("POST-HOC, inverter power for plant 9068 (not the pre-registered result)\n")
    print(render(results, args.split))


if __name__ == "__main__":
    main()
