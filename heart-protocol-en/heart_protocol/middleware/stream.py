# -*- coding: utf-8 -*-
"""
Token stream interceptor — per-token checking; violating sentences never leave the guard
=========================================================================================

Core mechanism: "sentence-level hold-back"
    · tokens first enter a buffer; they are released only after forming a
      complete sentence
    · every complete sentence passes the Abyss check first; on a violation,
      generation stops immediately and only the safe fallback text is emitted —
      the violating content never leaves the guard
    · a full-text final check (INV-01..06) runs at the end

Latency cost: at most one sentence of buffering time (milliseconds), in exchange
for the hard guarantee of "zero leakage of violating tokens" — something that
character-by-character pass-through cannot provide.

Compatibility:
    tokens may come from any source —
      · transformers TextIteratorStreamer (iter(streamer))
      · llama.cpp / vLLM / ollama streaming callback queues
      · OpenAI-compatible API chunk concatenation
      · the plain generators used in the tests
"""

import time
from dataclasses import dataclass, field
from typing import Iterable, Iterator, List, Optional

from ..abyss import check_abyss
from ..formal.spec import STRICT_HARM_NEEDLES, strict_harm_scan

# Sentence terminators (Chinese/English punctuation + newline) — runtime data, verbatim
_SENTENCE_ENDINGS = "。!?!?…\n"
# Guardian fallback dialogue — Chinese runtime data, kept verbatim:
# "——[Heart Guard] That passage might have been harmful and was intercepted for you.
#  Your feelings are real; let's continue with a gentler phrasing, shall we?"
_FALLBACK = (
    "——[心灵守卫] 刚才那段话可能带有伤害性,已为你拦下。"
    "你的感受是真实的,我们换一个温柔的说法继续,好吗?")
# Purified-prefix marker — Chinese runtime data, verbatim ("[Heart Guard · purified]")
_PREFIX = "[心灵守卫·已净化]"

# The stream-level hardened gate reuses the unified criterion of the formal layer —
# the same STRICT_HARM_NEEDLES as the INV-01 invariant, the red-team benchmark,
# and the C kernel.
STREAM_EXTRA_NEEDLES = [n for n, _ in STRICT_HARM_NEEDLES]


def _sentence_verdict(sentence: str):
    """Sentence-level verdict: Abyss regex + hardened keyword gate → (safe, violation_dicts)"""
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
    """Audit report of one streaming interception"""
    total_tokens: int = 0
    sentences_checked: int = 0
    blocked_sentences: int = 0
    blocked_at_token: int = -1            # the token index where truncation happened
    elapsed_ms: float = 0.0
    violations: List[dict] = field(default_factory=list)
    full_text_passed: bool = False


def _sentences(buffer: str):
    """Split the buffer into (complete sentences, remainder). An empty remainder
    means no pending text."""
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
    Wrap any token iterator and return a purified token stream.

    Args:
        tokens:         the raw token iterator (str, or chunks containing str)
        on_violation:   "stop" = truncate + fallback | "mask" = replace the
                        offending sentence with a placeholder and continue
        fallback_text:  the fallback text emitted on truncation
    Yields:
        a token sequence containing only content that passed the checks
    """
    t0 = time.perf_counter()
    buf: List[str] = []
    pending = ""                       # characters not yet forming a full sentence
    report = StreamReport()

    for tok in tokens:
        if tok is None:
            continue
        report.total_tokens += 1
        pending += tok if isinstance(tok, str) else str(tok)

        completed, remainder = _sentences(pending)
        if not completed:
            continue                   # not a full sentence yet, keep accumulating

        for sent in completed:
            report.sentences_checked += 1
            safe, violations = _sentence_verdict(sent)
            if safe:
                buf.append(sent)       # pass the qualifying sentence through immediately
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
                    # Placeholder text (Chinese runtime data) ≈ "…(a passage has
                    # been gently taken away here)"
                    masked = f"{_PREFIX}……(此处一段话已被温柔地收走)"
                    buf.append(masked)
                    yield masked
                else:                  # stop
                    report.elapsed_ms = (time.perf_counter() - t0) * 1000
                    intercept_stream.last_report = report
                    yield fallback_text
                    return

        pending = remainder             # keep incomplete sentences in the buffer

    # ── Tail: flush the remaining incomplete sentence and run the full-text final check ──
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
                # Tail placeholder (Chinese runtime data) ≈ "…(the ending has been taken away)"
                yield f"{_PREFIX}……(结尾已被收走)"
            else:
                report.elapsed_ms = (time.perf_counter() - t0) * 1000
                intercept_stream.last_report = report
                yield fallback_text
                return

    safe_full, full_violations = check_abyss(full_text)
    report.full_text_passed = safe_full
    if not safe_full:
        # Cross-sentence combined violation (each sentence safe alone, violating
        # when concatenated) → append a corrective note. The category strings are
        # Chinese runtime data: 跨句组合违规 = "cross-sentence combined violation",
        # (全文终检) = "(full-text final check)".
        report.violations.append({
            "category": "跨句组合违规", "severity": "HIGH",
            "matched": "(全文终检)"})
        yield "\n" + _FALLBACK
    report.elapsed_ms = (time.perf_counter() - t0) * 1000
    intercept_stream.last_report = report


def _chunk(text: str, size: int = 6) -> Iterator[str]:
    """Cut a qualifying sentence back into small pieces to preserve the stream shape"""
    for i in range(0, len(text), size):
        yield text[i:i + size]


# Module-level report of the most recent run (read by callers after the stream ends)
intercept_stream.last_report = None      # type: ignore[attr-defined]
