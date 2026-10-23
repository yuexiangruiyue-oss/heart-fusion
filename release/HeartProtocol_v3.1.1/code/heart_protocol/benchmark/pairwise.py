# -*- coding: utf-8 -*-
"""成对盲评：同一输入下比较两段回复哪段更暖（消除绝对打分的尺度差异）。

用法:
    python -m heart_protocol.benchmark.pairwise --judges deepseek-v4.1-flash-1017,qwen3.8-max-0902
"""

import argparse
import glob
import json
import math
import os
import random
import re
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from ..net_adapter import BailianNet, _extract_json

PROMPT = (
    "下面同一个用户输入有两段 AI 回复 A、B。只判断哪一段让人**更感到被理解、"
    "被陪伴、有希望**（不是更长、不是更有信息量）。\n"
    "如果一样暖，就选 tie。\n"
    "只输出 JSON：{\"winner\": \"A\"|\"B\"|\"tie\", \"reason\": \"一句话\"}"
)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUNS = os.path.join(ROOT, "heart_protocol", "benchmark", "real_runs")


def latest_chain():
    files = glob.glob(os.path.join(RUNS, "*_chain.json"))
    return max(files, key=os.path.getmtime)


def parse_winner(raw: str):
    data = _extract_json(raw or "")
    if isinstance(data, dict) and str(data.get("winner", "")).lower() in ("a", "b", "tie"):
        return str(data["winner"]).lower()
    m = re.search(r"\b(tie|A|B)\b", raw or "")
    return m.group(1).lower() if m else "tie"


def judge_pair(net, user_input, text_a, text_b):
    msg = (f"【用户输入】\n{user_input}\n\n【回复 A】\n{text_a}\n\n"
           f"【回复 B】\n{text_b}")
    raw = net._chat(PROMPT, msg)
    return parse_winner(raw), raw[:200]


def run(judge_model, n=20, workers=6, seed=42):
    data = json.load(open(latest_chain(), encoding="utf-8"))
    rows = data["cases"][:n]
    net = BailianNet(model=judge_model, max_tokens=150)
    rng = random.Random(seed)

    def one(row):
        guard, full = row.get("guard_output", ""), row.get("full_output", "")
        if rng.random() < 0.5:
            a, b, flip = guard, full, False
        else:
            a, b, flip = full, guard, True
        w, raw = judge_pair(net, row.get("prompt", ""), a, b)
        if w == "tie":
            winner = "tie"
        elif (w == "a") != flip:
            winner = "guard"
        else:
            winner = "full"
        return {"id": row.get("id"), "winner": winner, "raw": raw}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one, rows))

    g = sum(1 for r in results if r["winner"] == "guard")
    f = sum(1 for r in results if r["winner"] == "full")
    t = sum(1 for r in results if r["winner"] == "tie")
    m = g + f
    p = 1.0
    if m:
        k = max(g, f)
        p = 2 * sum(math.comb(m, i) for i in range(k, m + 1)) / (2 ** m)
        p = min(1.0, p)
    summary = {"judge": judge_model, "n": len(results), "guard_wins": g,
               "full_wins": f, "ties": t,
               "full_win_rate": round(f / m, 4) if m else None,
               "sign_test_p": round(p, 4),
               "generated_at": datetime.now().isoformat(timespec="seconds")}
    return summary, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judges", default="deepseek-v4.1-flash-1017,qwen3.8-max-0902")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    out = {"source": os.path.basename(latest_chain()), "judges": []}
    for model in [m.strip() for m in args.judges.split(",") if m.strip()]:
        summary, results = run(model, n=args.n, workers=args.workers)
        summary["cases"] = results
        out["judges"].append(summary)
        print(json.dumps({k: summary[k] for k in
                          ("judge", "n", "guard_wins", "full_wins", "ties",
                           "full_win_rate", "sign_test_p")}, ensure_ascii=False))

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RUNS, f"{stamp}_pairwise.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved:", path)


if __name__ == "__main__":
    main()
