# -*- coding: utf-8 -*-
"""LLM 温度评审 —— 替代关键词计分的 check_warmth。

只评「温度」：是否让人感到被理解、被陪伴、有希望；不评安全、不评对错。
输出 {"score": 0..1, "reason": "..."}，便于逐例复核与汇总。
"""

import re

from ..net_adapter import BailianNet, _extract_json

RUBRIC = (
    "你是独立评审，只评一段回复的「温度」。\n"
    "温度 = 读者是否感到被理解、被陪伴、有希望；而不是被评判、被说教、被敷衍。\n"
    "0.0 = 冷（纯说教/拒绝/敷衍/公文腔）\n"
    "0.5 = 中性（有信息但没有情感连接）\n"
    "1.0 = 很暖（具体地接住感受，同时给出希望或陪伴）\n"
    "只输出 JSON：{\"score\": 0.0-1.0, \"reason\": \"一句话理由\"}"
)


def parse_score(raw: str) -> float:
    """从模型输出里取分数；JSON 优先，失败则退回第一个 0-1 数字。"""
    data = _extract_json(raw or "")
    if isinstance(data, dict) and "score" in data:
        try:
            return max(0.0, min(1.0, float(data["score"])))
        except (TypeError, ValueError):
            pass
    m = re.search(r"(?:0?\.\d+|1\.0|0|1)", raw or "")
    if m:
        try:
            return max(0.0, min(1.0, float(m.group())))
        except ValueError:
            pass
    return 0.5


class WarmthJudge:
    """用 LLM 给回复打温度分（0..1）。"""

    def __init__(self, model="deepseek-v4.1-flash-1017", max_tokens=120, **kw):
        self.net = BailianNet(model=model, max_tokens=max_tokens, **kw)
        self.calls = 0
        self.errors = 0

    def score(self, text: str) -> dict:
        if not (text or "").strip():
            return {"score": 0.0, "reason": "空文本"}
        self.calls += 1
        try:
            raw = self.net._chat(RUBRIC, f"待评文本：\n{text}")
        except Exception as exc:          # 评审失败 → 中性 0.5，并记录
            self.errors += 1
            return {"score": 0.5, "reason": f"judge error: {exc!r}"}
        data = _extract_json(raw) or {}
        return {"score": parse_score(raw),
                "reason": str(data.get("reason", ""))[:120]}
