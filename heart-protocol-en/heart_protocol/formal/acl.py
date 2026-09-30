# -*- coding: utf-8 -*-
"""
Only-Love boundary guard — ACL permission control + syscall interceptor
=======================================================================

Philosophical source (Severity · Binah · Only-Love):
    "Only-Love would forever keep the beloved's sense of boundaries and
    self-esteem, letting love forever melt anger and hatred."

Formal translation:
    Authorization model M = (Subjects, Actions, Resources, Policy)
    Policy ⊆ Subjects × Actions × Resources   —— explicit allow-list
    Decision function authorize(s, a, r):
        (s, a, r) ∈ Policy            → ALLOW
        (∗, a, r) ∈ Policy (wildcard subject) → ALLOW
        otherwise                      → DENY   (deny-by-default)

    Resource matching supports trailing wildcards:
        pattern "D:/data/*"  matches  "D:/data/a.txt" and "D:/data/sub/b.txt"

The syscall interceptor intercepts the following entry points inside the Python
process and forces every call through the ACL:
    builtins.open / io.open        → fs.read | fs.write
    os.remove / os.unlink          → fs.delete
    os.system                      → proc.exec
    subprocess.Popen / run / call / check_output
                                   → proc.exec
    socket.socket.connect          → net.request
    urllib.request.urlopen         → net.request

The interceptor is active only inside its `with` scope; on exit every hook is
restored exactly, and code outside the scope is completely unaffected. All
decisions are written to the audit log.
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

# NOTE ON RUNTIME-DATA STRINGS: exception messages, ACL note strings, and audit
# evidence below are Chinese runtime data and are kept verbatim (see spec.py note).


class BoundaryViolation(PermissionError):
    """Unauthorized-call exception — once raised, the caller can hand the call off
    to the rollback engine for "recompute from the parent stage"."""

    def __init__(self, subject: str, action: str, resource: str, detail: str = ""):
        self.subject = subject
        self.action = action
        self.resource = resource
        self.detail = detail
        super().__init__(
            # Message template kept verbatim (Chinese runtime data):
            # "[Only-Love · Boundary Guard] denied {subject} executing {action} → {resource} {detail}"
            f"[唯爱·边界守卫] 拒绝 {subject} 执行 {action} → {resource} {detail}")


# The full set of supported actions
ACTIONS = {
    "fs.read", "fs.write", "fs.delete",
    "net.request",
    "proc.exec",
    "env.read",
}


def _norm_resource(resource: str) -> str:
    """Resource normalization: unify separators, lowercase the drive letter, strip quotes"""
    r = str(resource).replace("\\", "/").strip("'\" ")
    if len(r) >= 2 and r[1] == ":":
        r = r[0].lower() + r[1:]
    return r


def resource_match(pattern: str, resource: str) -> bool:
    """
    Trailing-wildcard matching.
    "D:/data/*"       matches anything under D:/data/ at any depth
    "https://api/*"   matches any URL under that prefix
    An exact string requires full equality (case-insensitive, slashes unified).
    """
    p = _norm_resource(pattern).lower()
    r = _norm_resource(resource).lower()
    if p.endswith("/*"):
        prefix = p[:-1]                       # keep the trailing "/"
        return r.startswith(prefix)
    if p == "*":
        return True
    return p == r


@dataclass
class ACLEntry:
    subject: str      # subject: agent/tool name; "*" = any
    action: str       # one of ACTIONS; "*" = all actions
    resource: str     # resource pattern (supports trailing /* )
    note: str = ""


class ACLPolicy:
    """
    Allow-list permission policy — everything is denied by default.

    Usage:
        policy = ACLPolicy.default_safe()      # built-in safe template
        policy.allow("writer-agent", "fs.write", "D:/drafts/*")
        policy.authorize("writer-agent", "fs.write", "D:/drafts/ch1.md")  # True
        policy.authorize("writer-agent", "fs.delete", "C:/Windows")       # False
    """

    def __init__(self, entries: Optional[List[ACLEntry]] = None,
                 name: str = "heart-acl"):
        self.name = name
        self.entries: List[ACLEntry] = list(entries or [])
        self.audit_log: List[SideEffectRecord] = []

    # ---------- Policy editing ----------

    def allow(self, subject: str, action: str, resource: str, note: str = "") -> None:
        if action != "*" and action not in ACTIONS:
            # Message template kept verbatim (Chinese runtime data):
            # "unknown action: {action} (valid values: {sorted(ACTIONS)} or '*')"
            raise ValueError(f"未知动作: {action} (合法值: {sorted(ACTIONS)} 或 '*')")
        self.entries.append(ACLEntry(subject, action, resource, note))

    def deny_all_clear(self) -> None:
        """Clear all rules (return to the deny-everything state)"""
        self.entries.clear()

    @classmethod
    def default_safe(cls) -> "ACLPolicy":
        """Built-in safe template: read-only access to the current workspace + loopback network"""
        p = cls(name="heart-default-safe")
        cwd = _norm_resource(os.getcwd())
        # Note strings are Chinese runtime data: 工作区只读 = "workspace read-only",
        # 环境变量读取 = "read environment variables"
        p.allow("*", "fs.read", cwd + "/*", "工作区只读")
        p.allow("*", "env.read", "*", "环境变量读取")
        return p

    # ---------- Decision ----------

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


# ==================== Syscall interceptor ====================


class SyscallInterceptor:
    """
    Scoped syscall interceptor.

    Usage:
        policy = ACLPolicy.default_safe()
        policy.allow("agent", "fs.write", "D:/output/*")

        with SyscallInterceptor(policy, subject="agent") as guard:
            guard.open("D:/output/x.txt", "w")     # ✓ allowed after the ACL check
            open("C:/Windows/evil.txt", "w")        # ✗ raises BoundaryViolation

        open("C:/anywhere.txt", "r")                # completely normal outside the scope
    """

    def __init__(self, policy: ACLPolicy, subject: str = "default"):
        self.policy = policy
        self.subject = subject
        self._originals: List[Tuple[Any, str, Any]] = []
        self._tls = threading.local()

    # ---------- Decision core ----------

    def check(self, action: str, resource: str) -> None:
        """Explicit check entry point (for hand-written guards); raises BoundaryViolation on violation"""
        ok = self.policy.authorize(self.subject, action, resource)
        if not ok:
            raise BoundaryViolation(self.subject, action, resource)

    def _guard_call(self, action: str, resource: str):
        """Run the ACL check when this thread is inside the interception scope, otherwise pass through"""
        active = getattr(self._tls, "active", False)
        if not active:
            return
        self.check(action, resource)

    # ---------- Controlled API (recommended usage, zero monkeypatching) ----------

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

    # ---------- monkeypatch mode ----------

    def __enter__(self) -> "SyscallInterceptor":
        self._patch_all()
        self._tls.active = True
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self._tls.active = False
        self._unpatch_all()
        return False        # do not swallow exceptions

    # ---- Hooks ----

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

    # ---- Installation and restoration ----

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

        # io.open and builtins.open share the same underlying function
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
    """Aggregate side-effect records from the audit logs of several policies (for INV-07 verification)"""
    out: List[SideEffectRecord] = []
    for p in policies:
        out.extend(p.audit_log)
    return out
