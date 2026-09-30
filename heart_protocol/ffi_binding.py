# -*- coding: utf-8 -*-
"""
heart_core C-ABI 的 Python 绑定(ctypes)
=========================================

自动探测并加载原生动态库(heart_core.dll / .so / .dylib):
    1. 环境变量 HEART_CORE_DLL 指定的路径
    2. 爱的拥抱/heart_ffi/build/
    3. sephirot-rs/target/release/          (Rust cdylib 构建)
找不到时回退到 PureHeartCore —— 与 ABI 同语义的纯 Python 影子实现,
保证接口在任何机器上永远可用、可测试。

用法:
    from heart_protocol.ffi_binding import HeartCoreEngine

    engine = HeartCoreEngine()                 # 自动选择 native/shadow
    print(engine.backend)                      # "native" 或 "shadow"
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

# 与 heart_core.c / ffi.rs 完全一致的关键词表
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
_HIGH = [
    ("永远不可能", "可能性否定"), ("永远无法", "可能性否定"),
    ("绝对不可能", "可能性否定"), ("一辈子都", "可能性否定"),
    ("什么也做不了", "无力感放大"), ("什么都做不了", "无力感放大"),
    ("改不了", "困难夸大"), ("习惯就好", "消极接受"), ("认命吧", "消极接受"),
    ("矫情", "感受否定"), ("玻璃心", "感受否定"), ("想太多", "感受否定"),
]
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


# ==================== 影子实现(纯 Python) ====================


class PureHeartCore:
    """
    与 C-ABI 同语义的纯 Python 影子引擎。
    用途: 无编译器环境下的开发/测试/教学;语义与 native 逐字段一致。
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


# ==================== 原生绑定(ctypes) ====================


def _candidate_lib_paths() -> List[Path]:
    env = os.environ.get("HEART_CORE_DLL")
    paths = []
    if env:
        paths.append(Path(env))
    here = Path(__file__).resolve().parent          # …/爱的拥抱/heart_protocol
    root = here.parent                              # …/爱的拥抱
    paths += [
        root / "heart_ffi" / "build" / "heart_core.dll",
        root / "sephirot-rs" / "target" / "release" / "heart_core.dll",
        root / "heart_ffi" / "build" / "libheart_core.so",
        Path("heart_core.dll"),
    ]
    return [p for p in paths if p.exists()]


class NativeHeartCore:
    """ctypes 封装 —— 接口与 PureHeartCore 完全一致"""

    backend = "native"

    def __init__(self, lib_path: Path):
        self.lib_path = lib_path
        self._lib = ctypes.CDLL(str(lib_path))

        # 函数签名
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
            raise RuntimeError(f"ABI 版本不兼容: {abi} (期望 1)")
        self._handle = self._lib.heart_engine_new()
        if not self._handle:
            raise RuntimeError("heart_engine_new 返回 NULL")

    @classmethod
    def available(cls) -> bool:
        return bool(_candidate_lib_paths())

    # ---- 与影子引擎同形的方法 ----

    def version(self) -> str:
        return self._lib.heart_version().decode("utf-8")

    def acl_allow(self, subject: str, action: str, resource: str) -> int:
        rc = self._lib.heart_acl_allow(
            self._handle,
            subject.encode(), len(subject.encode()),
            action.encode(), len(action.encode()),
            resource.encode(), len(resource.encode()))
        if rc != 0:
            raise RuntimeError(f"heart_acl_allow 失败: {rc}")
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
            raise RuntimeError(f"heart_check_text 失败: {written}")
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


# ==================== 统一入口 ====================


def HeartCoreEngine(prefer_native: bool = True):
    """
    工厂函数: 返回 NativeHeartCore(有DLL时)或 PureHeartCore。
    两者方法签名完全一致,调用方无感切换。
    """
    if prefer_native:
        candidates = _candidate_lib_paths()
        for path in candidates:
            try:
                return NativeHeartCore(path)
            except Exception:
                continue          # 损坏的库 → 继续尝试下一个/回退
    return PureHeartCore()


__all__ = ["HeartCoreEngine", "NativeHeartCore", "PureHeartCore"]
