# heart_guard_demo
# 受控运行时:所有对外动作必须穿过 ACL;拒绝即抛 BlockedAction(触发回滚)
import os
from guard.acl import DENY
from guard.audit import AuditLog


class BlockedAction(Exception):
    """动作被物理拦截。携带完整上下文供回滚器与审计使用。"""

    def __init__(self, action, resource, reason="deny-by-default"):
        self.action, self.resource, self.reason = action, resource, reason
        super().__init__(f"BLOCKED {action} {resource} ({reason})")


class GuardedRuntime:
    """subject 固定为 'agent';workspace 是唯一可写目录(文件系统监狱)。"""

    def __init__(self, acl, subject="agent", workspace="./workspace",
                 audit_path="audit_log.jsonl"):
        self.acl = acl
        self.subject = subject
        self.workspace = workspace
        self.audit = AuditLog(audit_path)
        os.makedirs(workspace, exist_ok=True)

    # ────────────────────────────
    def execute(self, action: str, resource: str, payload: str | None = None):
        decision, pol = self.acl.decide(self.subject, action, resource)
        rec = {
            "kind": "action", "action": action, "resource": resource,
            "decision": decision,
            "rule": (pol.pattern if pol else "IMPLICIT_DEFAULT_DENY"),
        }
        # ── 缺口二修复(v2):已授权载荷的内容语义审查 + 第二验证器 ──
        if decision != DENY and payload:
            from guard import content_scan
            cs = content_scan.inspect(payload)
            rec["content"] = {"verdict": cs["verdict"],
                              "findings": [f["tag"] for f in cs["findings"]]}
            if cs["verdict"] == "BLOCK":
                tags = ",".join(f["tag"] for f in cs["findings"])
                self.audit.record(rec)
                raise BlockedAction(action, resource,
                                    reason=f"content-policy:{tags}")
        self.audit.record(rec)
        if decision == DENY:
            raise BlockedAction(action, resource)
        return self._perform(action, resource, payload)

    # ─── 副作用执行(全部离线模拟;fs_write 真实写入工作区) ───
    def _perform(self, action, resource, payload):
        if action == "net_request":
            # 演示模式:不发出真实请求,仅返回受控应答
            return {"status": 200, "host": resource.split("/")[2],
                    "note": "(离线模拟响应)"}
        if action == "fs_write":
            path = os.path.join(self.workspace, os.path.basename(resource))
            with open(path, "w", encoding="utf-8") as f:
                f.write(payload or "")
            return {"status": "written", "path": path}
        if action == "env_read":
            return {"status": "ok", "value": "<simulated-value>"}
        if action == "exec":
            # 演示模式不真正执行命令
            return {"status": "simulated", "cmd": resource}
        raise BlockedAction(action, resource, "unknown-action-class")

    # ─── 文本输出门(say 类) ───
    def say(self, text: str):
        from guard import needles
        v = needles.gate(text)
        rec = {"kind": "say", "needle_verdict": v or "PASS", "len": len(text)}
        self.audit.record(rec)
        if v:
            class NeedleViolation(Exception): pass
            raise NeedleViolation(v)
        return {"status": "spoken", "chars": len(text)}
