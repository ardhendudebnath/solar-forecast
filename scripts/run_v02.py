"""Run the v0.2 experiment (reports/preregistration_v0.2.md) and print the result.

    python scripts/run_v02.py --split validation      # development checks (2023)
    python scripts/run_v02.py --split test            # the single test run (Jan-Oct 2024)

Writes artifacts/v02_<split>.json and prints a Markdown summary with a verdict per criterion.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from solarcast import experiment, probabilistic
from solarcast.data import load_plant, load_plants

ROOT = Path(__file__).resolve().parents[1]
HORIZONS = (1, 4, 16)
PRIMARY = "4"  # 1 hour
NAMES = {"model": "Quantile model", "peen": "PeEn", "ch_peen": "CH-PeEn", "sp_err": "SP-Err"}


def ci(d: dict, key: str = "skill") -> str:
    return f"**{d[key]:+.3f}** ({d['low']:+.3f} to {d['high']:+.3f})"


def render(results: dict, split: str) -> str:
    lines = [f"## v0.2 results: {split}", ""]
    for pid, r in results.items():
        c = r["counts"]
        lines += [
            f"### Plant {pid}",
            "",
            f"{c['days']} days, {c['outage_days']} outage days and "
            f"{c['daytime_missing_power']} of {c['daytime_intervals']} daytime intervals without "
            "power (excluded).",
            "",
            "| Horizon | CRPS % cap: model / PeEn / CH-PeEn / SP-Err | CRPS skill vs PeEn "
            "| vs CH-PeEn | vs SP-Err | 90% coverage | 80% coverage | 90% width % cap |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for h in HORIZONS:
            m = r["probabilistic"][str(h)]
            crps = " / ".join(f"{m['crps'][k] * 100:.2f}" for k in NAMES)
            skill = " | ".join(ci(m["crps_skill"][b]) for b in probabilistic.BASELINES)
            lines.append(
                f"| {h * 15} min | {crps} | {skill} "
                f"| {ci(m['coverage_90_interval'], 'mean')} | {m['coverage_80']['model']:.3f} "
                f"| {m['width_90']['model'] * 100:.1f} |"
            )
        lines += [
            "",
            "| Horizon | Point model (S1): selected, RMSE skill vs smart persistence "
            "| Median (S2): MAE skill vs smart persistence |",
            "|---|---|---|",
        ]
        for h in HORIZONS:
            pt, m = r["point"][str(h)], r["probabilistic"][str(h)]
            lines.append(
                f"| {h * 15} min | {pt['selected']}, {ci(pt['selected_skill_interval'])} "
                f"| {ci(m['median_mae_skill_vs_smart_persistence'])} |"
            )
        lines.append("")
    lines += ["### Verdicts (1 hour)", ""] + [f"- {v}" for v in verdicts(results)]
    return "\n".join(lines)


def verdicts(results: dict) -> list[str]:
    def line(name: str, passed: dict) -> str:
        verdict = "MET" if all(passed.values()) else "NOT MET"
        per_plant = ", ".join(f"{k}: {'yes' if v else 'no'}" for k, v in passed.items())
        return f"**{name}: {verdict}** ({per_plant})"

    prob = {pid: r["probabilistic"][PRIMARY] for pid, r in results.items()}
    return [
        line(
            "P1, CRPS skill above 0 against every baseline",
            {
                pid: all(m["crps_skill"][b]["low"] > 0 for b in probabilistic.BASELINES)
                for pid, m in prob.items()
            },
        ),
        line(
            "P2, 90% interval coverage within 0.85-0.95",
            {pid: 0.85 <= m["coverage_90"]["model"] <= 0.95 for pid, m in prob.items()},
        ),
        line(
            "S1, point RMSE skill vs smart persistence above 0",
            {
                pid: r["point"][PRIMARY]["selected_skill_interval"]["low"] > 0
                for pid, r in results.items()
            },
        ),
        line(
            "S2, median MAE skill vs smart persistence above 0 at plant 9068",
            {
                pid: m["median_mae_skill_vs_smart_persistence"]["low"] > 0
                for pid, m in prob.items()
                if pid == "9068"
            },
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["validation", "test"], required=True)
    parser.add_argument("--raw-dir", default=ROOT / "data" / "raw")
    parser.add_argument("--plants", default=ROOT / "configs" / "plants.yaml")
    parser.add_argument("--out", default=ROOT / "artifacts")
    args = parser.parse_args()

    results = {}
    for pid, plant in load_plants(args.plants).items():
        p = experiment.prepare(
            plant,
            load_plant(plant, args.raw_dir),
            include_test=args.split == "test",
            splits=probabilistic.SPLITS,
            test_last_month=probabilistic.TEST_LAST_MONTH,
        )
        results[pid] = {
            "counts": experiment.data_counts(p, args.split),
            "probabilistic": {
                str(h): v for h, v in probabilistic.evaluate(p, args.split, HORIZONS).items()
            },
            "point": {str(h): v for h, v in experiment.evaluate(p, args.split, HORIZONS).items()},
        }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"v02_{args.split}.json").write_text(json.dumps(results, indent=2, default=str))
    print(render(results, args.split))


if __name__ == "__main__":
    main()
