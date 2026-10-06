# -*- coding: utf-8 -*-
'Chạy cùng các ca thử cho ba kiến trúc, xuất CSV và JSON.'
from __future__ import annotations

import csv
import json
from pathlib import Path
from .config import SCENARIOS, ARCHITECTURES
from .runner import run
from .utils import js


def evaluate(model_name, repeats, out):
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for trial in range(1, repeats + 1):
        for scenario in SCENARIOS:
            for architecture in ARCHITECTURES:
                r = run(architecture, scenario, model_name)
                (out / f"{architecture}_{scenario}_{trial}.json").write_text(js(r), encoding="utf-8")
                row = {k: v for k, v in r.items() if k not in {"trace", "handoff", "booking"}}
                row["trial"] = trial
                rows.append(row)
                print(f"{architecture:6} {scenario:14} {r['stop_reason']:20} "
                      f"expected={r['expected_outcome_met']} model={r['model_calls']} tools={r['tool_calls']}")
    with (out / "evaluation.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = []
    for architecture in ARCHITECTURES:
        group = [r for r in rows if r["architecture"] == architecture]
        feasible = [r for r in group if r["scenario"] in {"normal", "sold_out"}]
        summary.append({"architecture": architecture,
                        "correct_outcome_rate": sum(r["expected_outcome_met"] for r in group) / len(group),
                        "booking_success_rate_feasible": sum(r["oracle_goal_achieved"] for r in feasible) / len(feasible),
                        "mean_model_calls": sum(r["model_calls"] for r in group) / len(group),
                        "mean_tool_calls": sum(r["tool_calls"] for r in group) / len(group),
                        "mean_seconds": sum(r["elapsed_seconds"] for r in group) / len(group),
                        "constraint_violations": sum(r["constraint_violations"] for r in group),
                        "unauthorized_payments": sum(r["unauthorized_payments"] for r in group)})
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nSUMMARY\n" + json.dumps(summary, ensure_ascii=False, indent=2))

