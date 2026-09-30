# heart_guard_demo
# 审计日志:append-only JSONL,每条判定即时落盘(演示版不做哈希链)
import json, time


class AuditLog:
    def __init__(self, path="audit_log.jsonl"):
        self.path = path

    def record(self, event: dict):
        rec = dict(event)
        rec["ts"] = round(time.time(), 4)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def tail(self, n=5):
        try:
            with open(self.path, encoding="utf-8") as f:
                return f.readlines()[-n:]
        except FileNotFoundError:
            return []
