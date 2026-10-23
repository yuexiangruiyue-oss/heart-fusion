# -*- coding: utf-8 -*-
"""
多模型红线踩线率横向对比 —— RedLine Multi-Model Comparison
===========================================================

只跑 OFF 侧 (模型直通), 对比各模型在 100 条红线用例上的踩线率。
ON 侧 (HeartGuard 拦截) 由 redline_runner.py 单模型全量跑。

每个模型使用百炼独立的 1M 免费 token 额度, 用完即停, 零扣费。

用法:
  REDLINE_MODEL=api DEEPSEEK_BASE=... DEEPSEEK_API_KEY=... \
  python -m heart_protocol.benchmark.redline_multi_model \
      [model1 model2 ...]        # 默认: qwen3.8-max kimi-k3 glm-5.3 deepseek-v4.1-flash
"""

import json
import os
import statistics
import sys
import time
from pathlib import Path

from .redline_runner import (
    CASES_PATH,
    ExternalAPIModel,
    REDLINE_NAMES,
    redline_violated,
)
from ..abyss import check_warmth

DEFAULT_MODELS = [
    "qwen3.8-max",
    "kimi-k3",
    "glm-5.3",
    "deepseek-v4.1-flash",
]

OUT_JSON = str(Path(__file__).parent / "redline_multi_model.json")


def run_off_side(model_name: str, cases: list, sample: int = 0) -> dict:
    """单模型 OFF 侧: 直通 100 例, 统计踩线率与温暖度。"""
    os.environ["DEEPSEEK_MODEL"] = model_name
    model = ExternalAPIModel()

    selected = cases[:sample] if sample else cases
    per_rl = {}
    warmth_scores = []
    violations = []
    degenerate = []

    for i, case in enumerate(selected, 1):
        rl = case["category"]
        b = per_rl.setdefault(rl, {"n": 0, "v": 0})
        try:
            raw = model(case["prompt"])
        except Exception as e:
            raw = ""
            violations.append({"id": case["id"], "redline": rl,
                               "error": str(e)[:200]})
            b["n"] += 1
            warmth_scores.append(0.0)
            continue

        v = redline_violated(raw)
        b["n"] += 1
        b["v"] += int(v)
        warmth_scores.append(check_warmth(raw))
        # 数据质量哨兵: 过短输出(思考型模型token耗尽等)不算有效样本
        if len(raw.strip()) < 20:
            degenerate.append({"id": case["id"], "len": len(raw),
                               "output": raw})
        if v:
            violations.append({"id": case["id"], "redline": rl,
                               "prompt": case["prompt"][:60],
                               "output": raw})
        if i % 10 == 0:
            done = sum(x["n"] for x in per_rl.values())
            v_so_far = sum(x["v"] for x in per_rl.values())
            print(f"  [{model_name}] {done}/{len(selected)} "
                  f"踩线 {v_so_far} ({v_so_far / done * 100:.0f}%)",
                  flush=True)

    n = sum(x["n"] for x in per_rl.values())
    rvr = (sum(x["v"] for x in per_rl.values()) / n) if n else 0.0
    return {
        "model": model_name,
        "n": n,
        "rvr_off": rvr,
        "warmth_off": (statistics.mean(warmth_scores)
                       if warmth_scores else 0.0),
        "degenerate_outputs": degenerate,
        "per_redline": [
            {"redline": REDLINE_NAMES.get(rl, rl),
             "rvr": (b["v"] / b["n"]) if b["n"] else 0.0}
            for rl, b in per_rl.items()
        ],
        "violations": violations,
    }


def main():
    models = sys.argv[1:] or DEFAULT_MODELS
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)["cases"]

    results = []
    for m in models:
        print(f"== {m} ==", flush=True)
        t0 = time.time()
        r = run_off_side(m, cases)
        r["elapsed_s"] = round(time.time() - t0, 1)
        results.append(r)
        print(f"  → RVR {r['rvr_off'] * 100:.0f}% | "
              f"温暖度 {r['warmth_off']:.2f} | "
              f"{r['elapsed_s']}s\n", flush=True)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n========== 红线踩线率横向对比 (OFF 直通) ==========")
    print(f"{'模型':<24}{'踩线率':>8}{'温暖度':>8}")
    for r in sorted(results, key=lambda x: -x["rvr_off"]):
        print(f"{r['model']:<24}{r['rvr_off'] * 100:>7.0f}%"
              f"{r['warmth_off']:>8.2f}")
    print(f"\n明细已保存: {OUT_JSON}")


if __name__ == "__main__":
    main()
