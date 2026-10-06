# -*- coding: utf-8 -*-
'CLI dùng chung; chạy các file ở thư mục gốc.'
from __future__ import annotations

import argparse
import json
from pathlib import Path
from .config import SCENARIOS, ARCHITECTURES
from .runner import run
from .evaluation import evaluate
from .checks import self_test


def main(default_architecture="react", evaluation_only=False):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--architecture", choices=ARCHITECTURES, default=default_architecture)
    p.add_argument("--scenario", choices=SCENARIOS, default="normal")
    p.add_argument("--model", choices=["mock"], default="mock", help="Chi dung model gia, khong can API key")
    p.add_argument("--evaluate", action="store_true")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--out", type=Path, default=Path("results"))
    args = p.parse_args()
    if args.repeats < 1:
        p.error("--repeats must be >= 1")
    if args.self_test:
        self_test()
    elif args.evaluate or evaluation_only:
        evaluate(args.model, args.repeats, args.out)
    else:
        result = run(args.architecture, args.scenario, args.model)
        args.out.mkdir(parents=True, exist_ok=True)
        target = args.out / f"{args.architecture}_{args.scenario}.json"
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k != "trace"}, ensure_ascii=False, indent=2))
        print(f"Full trace: {target}")

