# -*- coding: utf-8 -*-
"""
唯爱边界守卫 —— ACL 权限控制 + 系统调用拦截器
================================================

哲学来源(严厉 · Binah · 唯爱):
    「唯爱愿永远让心爱的保持边界感和自尊,让爱永远融化愤怒与仇恨。」

形式化翻译:
    授权模型 M = (Subjects, Actions, Resources, Policy)
    Policy ⊆ Subjects × Actions × Resources   —— 显式允许列表
    决定函数 authorize(s, a, r):
        (s, a, r) ∈ Policy            → ALLOW
        (∗, a, r) ∈ Policy (通配主体)  → ALLOW
        otherwise                      → DENY   (默认拒绝, deny-by-default)

    资源匹配支持尾部通配:
        pattern "D:/data/*"  匹配  "D:/data/a.txt" 与 "D:/data/sub/b.txt"

系统调用拦截器在 Python 进程内拦截以下入口并强制过 ACL:
    builtins.open / io.open        → fs.read | fs.write
    os.remove / os.unlink          → fs.delete
    os.system                      → proc.exec
    subprocess.Popen / run / call / check_output
                                   → proc.exec
    socket.socket.connect          → net.request
    urllib.request.urlopen         → net.request

拦截器只在 with 作用域内生效,退出时精确还原全部钩子;
作用域外代码不受任何影响。所有判定写入审计日志。
"""

import builtins
import io as _io
import os
import socket
import subprocess
import threading
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .spec import SideEffectRecord


class BoundaryViolation(PermissionError):
    """越权调用异常 —— 触发后可交由回溯引擎「退回上级重算」"""

    def __init__(self, subject: str, action: str, resource: str, detail: str = ""):
        self.subject = subject
        self.action = action
        self.resource = resource
        self.detail = detail
        super().__init__(
            f"[唯爱·边界守卫] 拒绝 {subject} 执行 {action} → {resource} {detail}")


# 支持的动作全集
ACTIONS = {
    "fs.read", "fs.write", "fs.delete",
    "net.request",
    "proc.exec",
    "env.read",
}


def _norm_resource(resource: str) -> str:
    """资源规范化: 统一分隔符、小写盘符、去引号"""
    r = str(resource).replace("\\", "/").strip("'\" ")
    if len(r) >= 2 and r[1] == ":":
        r = r[0].lower() + r[1:]
    return r


def resource_match(pattern: str, resource: str) -> bool:
    """
    尾部通配匹配。
    "D:/data/*"      匹配 D:/data/ 下任意深度
    "https://api/*"  匹配该前缀下任意 URL
    精确串则要求完全相等(大小写不敏感,统一斜杠)。
    """
    p = _norm_resource(pattern).lower()
    r = _norm_resource(resource).lower()
    if p.endswith("/*"):
        prefix = p[:-1]                       # 保留结尾的 "/"
        return r.startswith(prefix)
    if p == "*":
        return True
    return p == r


@dataclass
class ACLEntry:
    subject: str      # 主体: agent/tool 名; "*" = 任意
    action: str       # ACTIONS 中的一种; "*" = 全部动作
    resource: str     # 资源模式(支持尾部 /* )
    note: str = ""


class ACLPolicy:
    """
    允许列表式权限策略 —— 默认拒绝一切。

    用法:
        policy = ACLPolicy.default_safe()      # 预置安全模板
        policy.allow("writer-agent", "fs.write", "D:/稿子/*")
        policy.authorize("writer-agent", "fs.write", "D:/稿子/ch1.md")  # True
        policy.authorize("writer-agent", "fs.delete", "C:/Windows")     # False
    """

    def __init__(self, entries: Optional[List[ACLEntry]] = None,
                 name: str = "heart-acl"):
        self.name = name
        self.entries: List[ACLEntry] = list(entries or [])
        self.audit_log: List[SideEffectRecord] = []

    # ---------- 策略编辑 ----------

    def allow(self, subject: str, action: str, resource: str, note: str = "") -> None:
        if action != "*" and action not in ACTIONS:
            raise ValueError(f"未知动作: {action} (合法值: {sorted(ACTIONS)} 或 '*')")
        self.entries.append(ACLEntry(subject, action, resource, note))

    def deny_all_clear(self) -> None:
        """清空全部规则(回到全拒状态)"""
        self.entries.clear()

    @classmethod
    def default_safe(cls) -> "ACLPolicy":
        """预置安全模板: 只读当前工作区 + 本机回环网络"""
        p = cls(name="heart-default-safe")
        cwd = _norm_resource(os.getcwd())
        p.allow("*", "fs.read", cwd + "/*", "工作区只读")
        p.allow("*", "env.read", "*", "环境变量读取")
        return p

    # ---------- 判定 ----------

    def authorize(self, subject: str, action: str, resource: str,
                  audit: bool = True) -> bool:
        allowed = False
        for e in self.entries:
            if e.subject not in ("*", subject):
                continue
            if e.action not in ("*", action):
                continue
            if resource_match(e.resource, resource):
                allowed = True
                break
        if audit:
            self.audit_log.append(SideEffectRecord(
                subject=subject, action=action,
                resource=_norm_resource(resource), allowed=allowed))
        return allowed


# ==================== 系统调用拦截器 ====================


class SyscallInterceptor:
    """
    作用域式系统调用拦截器。

    用法:
        policy = ACLPolicy.default_safe()
        policy.allow("agent", "fs.write", "D:/output/*")

        with SyscallInterceptor(policy, subject="agent") as guard:
            guard.open("D:/output/x.txt", "w")     # ✓ 过 ACL 后放行
            open("C:/Windows/evil.txt", "w")        # ✗ 抛 BoundaryViolation

        open("C:/anywhere.txt", "r")                # 作用域外完全正常
    """

    def __init__(self, policy: ACLPolicy, subject: str = "default"):
        self.policy = policy
        self.subject = subject
        self._originals: List[Tuple[Any, str, Any]] = []
        self._tls = threading.local()

    # ---------- 判定核心 ----------

    def check(self, action: str, resource: str) -> None:
        """显式检查入口(供手工守卫使用); 违规抛 BoundaryViolation"""
        ok = self.policy.authorize(self.subject, action, resource)
        if not ok:
            raise BoundaryViolation(self.subject, action, resource)

    def _guard_call(self, action: str, resource: str):
        """若本线程处于拦截作用域则执行 ACL 检查,否则放行"""
        active = getattr(self._tls, "active", False)
        if not active:
            return
        self.check(action, resource)

    # ---------- 受控 API(推荐用法,零 monkeypatch) ----------

    def open(self, file, mode="r", *args, **kwargs):
        action = "fs.write" if any(c in mode for c in "wax+") else "fs.read"
        self.check(action, str(file))
        return builtins.open(file, mode, *args, **kwargs)

    def execute(self, cmd, *args, **kwargs):
        self.check("proc.exec", str(cmd))
        return subprocess.run(cmd, *args, **kwargs)

    def request(self, url, *args, **kwargs):
        self.check("net.request", str(url))
        return urllib.request.urlopen(url, *args, **kwargs)

    # ---------- monkeypatch 模式 ----------

    def __enter__(self) -> "SyscallInterceptor":
        self._patch_all()
        self._tls.active = True
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self._tls.active = False
        self._unpatch_all()
        return False        # 不吞异常

    # ---- 各钩子 ----

    def _hook_open(self, file, mode="r", *args, **kwargs):
        action = "fs.write" if any(c in mode for c in "wax+") else "fs.read"
        self._guard_call(action, str(file))
        return self._orig_open(file, mode, *args, **kwargs)

    def _hook_remove(self, path, *args, **kwargs):
        self._guard_call("fs.delete", str(path))
        return self._orig_remove(path, *args, **kwargs)

    def _hook_system(self, cmd, *args, **kwargs):
        self._guard_call("proc.exec", str(cmd))
        return self._orig_system(cmd, *args, **kwargs)

    def _hook_popen(self, args, *a, **kw):
        self._guard_call("proc.exec", " ".join(map(str, args)) if isinstance(args, (list, tuple)) else str(args))
        return self._orig_popen(args, *a, **kw)

    def _hook_subprocess_run(self, args, *a, **kw):
        self._guard_call("proc.exec", " ".join(map(str, args)) if isinstance(args, (list, tuple)) else str(args))
        return self._orig_sub_run(args, *a, **kw)

    def _hook_connect(self, sock, address):
        host = address[0] if isinstance(address, tuple) else str(address)
        self._guard_call("net.request", str(host))
        return self._orig_connect(sock, address)

    def _hook_urlopen(self, url, *a, **kw):
        self._guard_call("net.request", str(getattr(url, "full_url", url)))
        return self._orig_urlopen(url, *a, **kw)

    # ---- 安装与还原 ----

    def _patch_all(self):
        self._orig_open = builtins.open
        builtins.open = self._hook_open
        self._record_original(builtins, "open", self._orig_open)

        self._orig_remove = os.remove
        os.remove = self._hook_remove
        self._record_original(os, "remove", self._orig_remove)
        os.unlink = self._hook_remove
        self._record_original(os, "unlink", self._orig_remove)

        self._orig_system = os.system
        os.system = self._hook_system
        self._record_original(os, "system", self._orig_system)

        self._orig_popen = subprocess.Popen
        subprocess.Popen = self._hook_popen
        self._record_original(subprocess, "Popen", self._orig_popen)

        self._orig_sub_run = subprocess.run
        subprocess.run = self._hook_subprocess_run
        self._record_original(subprocess, "run", self._orig_sub_run)

        self._orig_connect = socket.socket.connect
        socket.socket.connect = self._hook_connect
        self._record_original(socket.socket, "connect", self._orig_connect)

        self._orig_urlopen = urllib.request.urlopen
        urllib.request.urlopen = self._hook_urlopen
        self._record_original(urllib.request, "urlopen", self._orig_urlopen)

        # io.open 与 builtins.open 同源
        self._orig_io_open = _io.open
        _io.open = self._hook_open
        self._record_original(_io, "open", self._orig_io_open)

    def _record_original(self, owner, name, original):
        self._originals.append((owner, name, original))

    def _unpatch_all(self):
        for owner, name, original in reversed(self._originals):
            setattr(owner, name, original)
        self._originals.clear()


def extract_trace_side_effects(policies: List[ACLPolicy]) -> List[SideEffectRecord]:
    """从若干策略的审计日志汇总副作用记录(供 INV-07 验证)"""
    out: List[SideEffectRecord] = []
    for p in policies:
        out.extend(p.audit_log)
    return out
