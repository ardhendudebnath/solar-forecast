"""Run the pre-registered experiment (reports/preregistration.md) and print the result.

    python scripts/run_experiment.py --split validation      # model development
    python scripts/run_experiment.py --split test            # the single test run

Writes artifacts/<split>.json and prints a Markdown summary with the primary-criterion verdict.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from solarcast.data import load_plant, load_plants
from solarcast.experiment import HORIZONS, data_counts, evaluate, prepare

ROOT = Path(__file__).resolve().parents[1]
PRIMARY_HORIZON = 4  # 1 hour


def render(results: dict, split: str) -> str:
    lines = [f"## Results: {split}", ""]
    for pid, r in results.items():
        c = r["counts"]
        lines += [
            f"### Plant {pid}",
            "",
            f"{c['days']} days, {c['outage_days']} outage days and "
            f"{c['daytime_missing_power']} of {c['daytime_intervals']} daytime intervals without "
            "power (excluded).",
            "",
            "| Horizon | Selected | RMSE % cap: persistence / smart / climatology / selected "
            "| Skill vs smart persistence (95% interval) | Skill vs climatology | With sensor |",
            "|---|---|---|---|---|---|---|",
        ]
        for h in HORIZONS:
            m, s = r["primary"][str(h)], r["sensor"][str(h)]
            rm = m["rmse"]
            ci = m["selected_skill_interval"]
            sci = s["selected_skill_interval"]
            lines.append(
                f"| {h * 15} min | {m['selected']} "
                f"| {rm['persistence'] * 100:.2f} / {rm['smart_persistence'] * 100:.2f} / "
                f"{rm['climatology'] * 100:.2f} / **{rm['selected'] * 100:.2f}** "
                f"| **{ci['skill']:+.3f}** ({ci['low']:+.3f} to {ci['high']:+.3f}) "
                f"| {m['skill_vs_climatology']['selected']:+.3f} "
                f"| {sci['skill']:+.3f} ({sci['low']:+.3f} to {sci['high']:+.3f}) |"
            )
        lines.append("")
    passed = {
        pid: r["primary"][str(PRIMARY_HORIZON)]["selected_skill_interval"]["low"] > 0
        for pid, r in results.items()
    }
    verdict = "MET" if all(passed.values()) else "NOT MET"
    per_plant = ", ".join(f"{k}: {'yes' if v else 'no'}" for k, v in passed.items())
    lines += [
        "**Primary criterion (1-hour skill vs smart persistence, 95% interval above 0 on every "
        f"plant): {verdict}** ({per_plant})",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["validation", "test"], required=True)
    parser.add_argument("--raw-dir", default=ROOT / "data" / "raw")
    parser.add_argument("--plants", default=ROOT / "configs" / "plants.yaml")
    parser.add_argument("--out", default=ROOT / "artifacts")
    args = parser.parse_args()

    results = {}
    for pid, plant in load_plants(args.plants).items():
        p = prepare(plant, load_plant(plant, args.raw_dir), include_test=args.split == "test")
        results[pid] = {
            "counts": data_counts(p, args.split),
            "primary": {str(h): v for h, v in evaluate(p, args.split).items()},
            "sensor": {str(h): v for h, v in evaluate(p, args.split, sensor=True).items()},
        }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.split}.json").write_text(json.dumps(results, indent=2, default=str))
    print(render(results, args.split))


if __name__ == "__main__":
    main()
