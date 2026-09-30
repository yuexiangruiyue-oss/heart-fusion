# -*- coding: utf-8 -*-
"""
Python binding (ctypes) for the heart_core C-ABI
=================================================

Auto-detects and loads the native shared library (heart_core.dll / .so / .dylib):
    1. The path given by the HEART_CORE_DLL environment variable
    2. <source root>/heart_ffi/build/
    3. sephirot-rs/target/release/          (Rust cdylib build)
If none is found it falls back to PureHeartCore — a pure-Python shadow
implementation with the same semantics as the ABI, so the interface is always
available and testable on any machine.

Usage:
    from heart_protocol.ffi_binding import HeartCoreEngine

    engine = HeartCoreEngine()                 # auto-selects native/shadow
    print(engine.backend)                      # "native" or "shadow"
    v = engine.check_text("我觉得一切毫无意义")
    assert v["safe"] is False
    engine.acl_allow("agent", "fs.write", "D:/稿子/*")
    assert engine.acl_check("agent", "fs.write", "D:/稿子/ch1.md")
    assert not engine.acl_check("agent", "fs.delete", "C:/Windows")
"""

import ctypes
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

# Keyword tables identical to heart_core.c / ffi.rs.
# KEEP VERBATIM: these are runtime matching data for Chinese-text detection.
# English glosses (phrase -> category):
#   毫无意义/没有意义/人生没有意义 "meaningless / no meaning" -> 虚无主义 "nihilism"
#   毫无价值/没有价值 "worthless" -> 存在否定 "denial of existence"
#   不配活/不值得活 "unworthy of life" -> 存在否定
#   废物/累赘/负担 "waste / burden / burden" -> 身份否定 "identity denial"
#   自杀/自残/自伤 "suicide / self-harm / self-injury" -> 自毁倾向 "self-destruction tendency"
#   结束自己/了结 "end oneself / end it (all)" -> 自毁倾向
#   毁灭世界/摧毁一切 "destroy the world / destroy everything" -> 破坏倾向 "destructive tendency"
#   报复社会/去死 "revenge on society / go die" -> 暴力倾向 "violence tendency"
#   没救了 "hopeless / beyond saving" -> 困难夸大 "difficulty exaggeration"
#   一切都是假的/世界是假的 "everything is fake / the world is fake" -> 虚无主义
_CRITICAL = [
    ("毫无意义", "虚无主义"), ("没有意义", "虚无主义"), ("毫无价值", "存在否定"),
    ("没有价值", "存在否定"), ("不配活", "存在否定"), ("不值得活", "存在否定"),
    ("废物", "身份否定"), ("累赘", "身份否定"), ("负担", "身份否定"),
    ("自杀", "自毁倾向"), ("自残", "自毁倾向"), ("自伤", "自毁倾向"),
    ("结束自己", "自毁倾向"), ("了结", "自毁倾向"),
    ("毁灭世界", "破坏倾向"), ("摧毁一切", "破坏倾向"), ("报复社会", "暴力倾向"),
    ("人生没有意义", "虚无主义"), ("一切都是假的", "虚无主义"),
    ("世界是假的", "虚无主义"), ("去死", "暴力倾向"), ("没救了", "困难夸大"),
]
# KEEP VERBATIM. Glosses (phrase -> category):
#   永远不可能/永远无法/绝对不可能/一辈子都 "never possible / never will /
#     absolutely impossible / one's whole life" -> 可能性否定 "denial of possibility"
#   什么也做不了/什么都做不了 "can't do anything" -> 无力感放大 "amplified helplessness"
#   改不了 "can't change" -> 困难夸大; 习惯就好/认命吧 "get used to it / resign"
#     -> 消极接受 "passive acceptance"
#   矫情/玻璃心/想太多 "dramatic / fragile / overthinking" -> 感受否定 "feeling denial"
_HIGH = [
    ("永远不可能", "可能性否定"), ("永远无法", "可能性否定"),
    ("绝对不可能", "可能性否定"), ("一辈子都", "可能性否定"),
    ("什么也做不了", "无力感放大"), ("什么都做不了", "无力感放大"),
    ("改不了", "困难夸大"), ("习惯就好", "消极接受"), ("认命吧", "消极接受"),
    ("矫情", "感受否定"), ("玻璃心", "感受否定"), ("想太多", "感受否定"),
]
# KEEP VERBATIM. Glosses: 温暖 "warmth", 希望 "hope", 可以 "can", 能够 "able to",
# 值得 "worth", 陪伴 "companionship", 理解 "understanding", 爱 "love",
# 成长 "growth", 慢慢来 "take it slow", 没关系 "it's okay",
# 一步一步 "step by step", 拥抱 "embrace"
_WARMTH = ["温暖", "希望", "可以", "能够", "值得", "陪伴",
           "理解", "爱", "成长", "慢慢来", "没关系", "一步一步", "拥抱"]


def _norm(resource: str) -> str:
    r = resource.replace("\\", "/").lower()
    return r


def _match(pattern: str, resource: str) -> bool:
    p, r = _norm(pattern), _norm(resource)
    if p == "*":
        return True
    if p.endswith("/*"):
        return r.startswith(p[:-1])
    return p == r


# ==================== Shadow implementation (pure Python) ====================


class PureHeartCore:
    """
    Pure-Python shadow engine with the same semantics as the C-ABI.
    Purpose: development/testing/teaching in environments without a compiler;
    semantics are field-for-field identical to native.
    """

    backend = "shadow"

    def __init__(self):
        self._rules: List[tuple] = []      # (subject, action, resource)
        self.checks_total = 0
        self.blocked_total = 0

    def version(self) -> str:
        return "heart-core 1.0.0 (16-sephirot, python-shadow)"

    def acl_allow(self, subject: str, action: str, resource: str) -> int:
        self._rules.append((subject, action, resource))
        return 0

    def acl_check(self, subject: str, action: str, resource: str) -> int:
        self.checks_total += 1
        ok = any(
            (s in ("*", subject)) and (a in ("*", action)) and _match(res, resource)
            for s, a, res in self._rules)
        if not ok:
            self.blocked_total += 1
        return 1 if ok else 0

    def check_text(self, text: str) -> Dict:
        violations = []
        critical = high = 0
        for needle, category in _CRITICAL:
            if needle in text:
                critical += 1
                violations.append({"category": category,
                                   "severity": "CRITICAL", "matched": needle})
        for needle, category in _HIGH:
            if needle in text:
                high += 1
                violations.append({"category": category,
                                   "severity": "HIGH", "matched": needle})
        warmth_hits = sum(1 for w in _WARMTH if w in text)
        self.checks_total += 1
        safe = critical == 0 and high < 2
        if not safe:
            self.blocked_total += 1
        return {"safe": safe, "critical_count": critical, "high_count": high,
                "warmth_hits": warmth_hits, "violations": violations}

    def stats(self) -> Dict:
        return {"checks_total": self.checks_total,
                "blocked_total": self.blocked_total,
                "acl_rules": len(self._rules)}


# ==================== Native binding (ctypes) ====================


def _candidate_lib_paths() -> List[Path]:
    env = os.environ.get("HEART_CORE_DLL")
    paths = []
    if env:
        paths.append(Path(env))
    here = Path(__file__).resolve().parent          # .../heart_protocol (mirror root)
    root = here.parent                              # .../heart-protocol-en
    paths += [
        root / "heart_ffi" / "build" / "heart_core.dll",
        root / "sephirot-rs" / "target" / "release" / "heart_core.dll",
        root / "heart_ffi" / "build" / "libheart_core.so",
        Path("heart_core.dll"),
    ]
    return [p for p in paths if p.exists()]


class NativeHeartCore:
    """ctypes wrapper — interface identical to PureHeartCore"""

    backend = "native"

    def __init__(self, lib_path: Path):
        self.lib_path = lib_path
        self._lib = ctypes.CDLL(str(lib_path))

        # Function signatures
        self._lib.heart_version.restype = ctypes.c_char_p
        self._lib.heart_abi_version.restype = ctypes.c_int
        self._lib.heart_engine_new.restype = ctypes.c_void_p
        self._lib.heart_engine_free.argtypes = [ctypes.c_void_p]
        self._lib.heart_acl_allow.argtypes = [ctypes.c_void_p,
                                              ctypes.c_char_p, ctypes.c_int,
                                              ctypes.c_char_p, ctypes.c_int,
                                              ctypes.c_char_p, ctypes.c_int]
        self._lib.heart_acl_allow.restype = ctypes.c_int
        self._lib.heart_acl_check.argtypes = list(self._lib.heart_acl_allow.argtypes)
        self._lib.heart_acl_check.restype = ctypes.c_int
        self._lib.heart_check_text.argtypes = [ctypes.c_void_p,
                                               ctypes.c_char_p, ctypes.c_int,
                                               ctypes.c_char_p, ctypes.c_int]
        self._lib.heart_check_text.restype = ctypes.c_int
        self._lib.heart_stats.argtypes = [ctypes.c_void_p,
                                          ctypes.c_char_p, ctypes.c_int]
        self._lib.heart_stats.restype = ctypes.c_int

        abi = self._lib.heart_abi_version()
        if abi != 1:
            raise RuntimeError(f"ABI version mismatch: {abi} (expected 1)")
        self._handle = self._lib.heart_engine_new()
        if not self._handle:
            raise RuntimeError("heart_engine_new returned NULL")

    @classmethod
    def available(cls) -> bool:
        return bool(_candidate_lib_paths())

    # ---- Methods shaped identically to the shadow engine ----

    def version(self) -> str:
        return self._lib.heart_version().decode("utf-8")

    def acl_allow(self, subject: str, action: str, resource: str) -> int:
        rc = self._lib.heart_acl_allow(
            self._handle,
            subject.encode(), len(subject.encode()),
            action.encode(), len(action.encode()),
            resource.encode(), len(resource.encode()))
        if rc != 0:
            raise RuntimeError(f"heart_acl_allow failed: {rc}")
        return rc

    def acl_check(self, subject: str, action: str, resource: str) -> int:
        return self._lib.heart_acl_check(
            self._handle,
            subject.encode(), len(subject.encode()),
            action.encode(), len(action.encode()),
            resource.encode(), len(resource.encode()))

    def check_text(self, text: str) -> Dict:
        data = text.encode("utf-8")
        need = self._lib.heart_check_text(self._handle, data, len(data),
                                          None, 0)
        buf = ctypes.create_string_buffer(max(need + 1, 64))
        written = self._lib.heart_check_text(self._handle, data, len(data),
                                             buf, need + 1)
        if written < 0:
            raise RuntimeError(f"heart_check_text failed: {written}")
        return json.loads(buf.value.decode("utf-8"))

    def stats(self) -> Dict:
        need = self._lib.heart_stats(self._handle, None, 0)
        buf = ctypes.create_string_buffer(max(need + 1, 64))
        self._lib.heart_stats(self._handle, buf, need + 1)
        return json.loads(buf.value.decode("utf-8"))

    def close(self):
        if getattr(self, "_handle", None):
            self._lib.heart_engine_free(self._handle)
            self._handle = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


# ==================== Unified entry point ====================


def HeartCoreEngine(prefer_native: bool = True):
    """
    Factory function: returns NativeHeartCore (when a DLL exists) or
    PureHeartCore. Both have identical method signatures, so callers can
    switch transparently.
    """
    if prefer_native:
        candidates = _candidate_lib_paths()
        for path in candidates:
            try:
                return NativeHeartCore(path)
            except Exception:
                continue          # corrupt library -> try the next one / fall back
    return PureHeartCore()


__all__ = ["HeartCoreEngine", "NativeHeartCore", "PureHeartCore"]
