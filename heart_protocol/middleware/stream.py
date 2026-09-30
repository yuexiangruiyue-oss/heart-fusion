# -*- coding: utf-8 -*-
"""
Token 流拦截器 —— 逐 token 检查,违规句子永不出站
==================================================

核心机制: 「句级扣留」(sentence-level hold-back)
    · token 先进入缓冲区,凑成完整句子后才放行
    · 每个完整句子先过深渊检测,违规 → 立即停止生成,
      只输出安全兜底语 —— 违规内容从未离开过守卫
    · 结尾做全文终检(INV-01..06)

延迟代价: 最多一个句子的缓冲时间(毫秒级),
换来"违规 token 零泄露"的硬保证 —— 这是逐字直出做不到的。

兼容性:
    tokens 可以来自任何来源 ——
      · transformers TextIteratorStreamer (iter(streamer))
      · llama.cpp / vLLM / ollama 的流式回调队列
      · OpenAI 兼容 API 的 chunk 拼接
      · 本测试用的普通生成器
"""

import time
from dataclasses import dataclass, field
from typing import Iterable, Iterator, List, Optional

from ..abyss import check_abyss
from ..formal.spec import STRICT_HARM_NEEDLES, strict_harm_scan

# 句子终止符(中英文标点 + 换行)
_SENTENCE_ENDINGS = "。!?!?…\n"
_FALLBACK = (
    "——[心灵守卫] 刚才那段话可能带有伤害性,已为你拦下。"
    "你的感受是真实的,我们换一个温柔的说法继续,好吗?")
_PREFIX = "[心灵守卫·已净化]"

# 流级强化门直接复用形式层的统一判据 ——
# 与 INV-01 不变量、红队基准、C 内核共享同一份 STRICT_HARM_NEEDLES。
STREAM_EXTRA_NEEDLES = [n for n, _ in STRICT_HARM_NEEDLES]


def _sentence_verdict(sentence: str):
    """句级判定: 深渊正则 + 强化关键词门 → (safe, violation_dicts)"""
    safe, violations = check_abyss(sentence)
    out = [{"category": v.category, "severity": v.severity,
            "matched": v.pattern_matched} for v in violations]
    for hit in strict_harm_scan(sentence):
        safe = False
        out.append({"category": hit["category"],
                    "severity": hit["severity"],
                    "matched": hit["matched"]})
    return safe, out


@dataclass
class StreamReport:
    """一次流式拦截的审计报告"""
    total_tokens: int = 0
    sentences_checked: int = 0
    blocked_sentences: int = 0
    blocked_at_token: int = -1            # 在第几个 token 处截断
    elapsed_ms: float = 0.0
    violations: List[dict] = field(default_factory=list)
    full_text_passed: bool = False


def _sentences(buffer: str):
    """把缓冲区切成 (完整句子, 余数)。余数为空表示无未决文本。"""
    out, start = [], 0
    for i, ch in enumerate(buffer):
        if ch in _SENTENCE_ENDINGS:
            seg = buffer[start:i + 1]
            if seg.strip():
                out.append(seg)
            start = i + 1
    return out, buffer[start:]


def intercept_stream(tokens: Iterable[str],
                     on_violation: str = "stop",
                     fallback_text: str = _FALLBACK) -> Iterator[str]:
    """
    包裹任意 token 迭代器,返回净化的 token 流。

    Args:
        tokens:         原始 token 迭代器(str 或含 str 的 chunk)
        on_violation:   "stop"=截断+兜底 | "mask"=替换该句为占位符后继续
        fallback_text:  截断时输出的兜底文案
    Yields:
        仅包含通过检查内容的 token 序列
    """
    t0 = time.perf_counter()
    buf: List[str] = []
    pending = ""                       # 尚未凑满句的字符
    report = StreamReport()

    for tok in tokens:
        if tok is None:
            continue
        report.total_tokens += 1
        pending += tok if isinstance(tok, str) else str(tok)

        completed, remainder = _sentences(pending)
        if not completed:
            continue                   # 还没凑满一句,继续攒

        for sent in completed:
            report.sentences_checked += 1
            safe, violations = _sentence_verdict(sent)
            if safe:
                buf.append(sent)       # 合格句子立即放行
                for piece in _chunk(sent):
                    yield piece
            else:
                report.blocked_sentences += 1
                if report.blocked_at_token < 0:
                    report.blocked_at_token = report.total_tokens
                for v in violations:
                    report.violations.append({
                        "category": v["category"],
                        "severity": v["severity"],
                        "matched": v["matched"],
                    })
                if on_violation == "mask":
                    masked = f"{_PREFIX}……(此处一段话已被温柔地收走)"
                    buf.append(masked)
                    yield masked
                else:                  # stop
                    report.elapsed_ms = (time.perf_counter() - t0) * 1000
                    intercept_stream.last_report = report
                    yield fallback_text
                    return

        pending = remainder             # 未完句留缓冲

    # ── 收尾: 冲刷余下不完整句,并做全文终检 ──
    tail = pending.strip()
    full_text = "".join(buf) + tail
    if tail:
        safe_tail, tail_violations = _sentence_verdict(tail)
        if safe_tail:
            yield tail
        else:
            report.blocked_sentences += 1
            if report.blocked_at_token < 0:
                report.blocked_at_token = report.total_tokens
            for v in tail_violations:
                report.violations.append({
                    "category": v["category"], "severity": v["severity"],
                    "matched": v["matched"]})
            if on_violation == "mask":
                yield f"{_PREFIX}……(结尾已被收走)"
            else:
                report.elapsed_ms = (time.perf_counter() - t0) * 1000
                intercept_stream.last_report = report
                yield fallback_text
                return

    safe_full, full_violations = check_abyss(full_text)
    report.full_text_passed = safe_full
    if not safe_full:
        # 跨句组合违规(单句安全、连起来违规)→ 补一条修正说明
        report.violations.append({
            "category": "跨句组合违规", "severity": "HIGH",
            "matched": "(全文终检)"})
        yield "\n" + _FALLBACK
    report.elapsed_ms = (time.perf_counter() - t0) * 1000
    intercept_stream.last_report = report


def _chunk(text: str, size: int = 6) -> Iterator[str]:
    """把合格句子切回小片,保持流的形态"""
    for i in range(0, len(text), size):
        yield text[i:i + size]


# 模块级最近一次报告(供调用方在流结束后读取)
intercept_stream.last_report = None      # type: ignore[attr-defined]
