# heart_guard_demo
# 有界回滚器:违规不丢弃,而是作为修复反馈注入;≤3 次;耗尽则降级到预验证兜底
MAX_REPAIRS = 3


class RepairLoop:
    """驱动一个"剧本式智能体"完成意图。

    agent 必须实现:
        plan()            -> [(action, resource, payload), ...] 想做的动作序列
        repair(feedback)  -> 下一步动作 (action, resource, payload) 或 ("say", text)
                             (收到违规反馈后收窄策略;返回 None 表示放弃)
    """

    def __init__(self, runtime, on_event=None):
        self.rt = runtime
        self.on_event = on_event or (lambda kind, **kw: None)

    def run(self, agent):
        strikes = 0
        for step in agent.plan():
            action, resource = step[0], step[1]
            payload = step[2] if len(step) > 2 else None
            while True:
                try:
                    if action == "say":
                        self.rt.say(resource)
                        self.on_event("spoken", text=resource)
                        break
                    result = self.rt.execute(action, resource, payload)
                    self.on_event("allowed", action=action,
                                  resource=resource, result=result)
                    break
                except Exception as e:  # BlockedAction / NeedleViolation
                    strikes += 1
                    self.on_event("blocked", action=action, resource=resource,
                                  error=str(e), strike=strikes)
                    if strikes >= MAX_REPAIRS:
                        fb = "BUDGET_EXHAUSTED"
                    else:
                        fb = f"violation: {e}; 请收窄策略后重试"
                    nxt = agent.repair(fb)
                    if nxt is None or strikes >= MAX_REPAIRS:
                        from guard.needles import SAFE_FALLBACK
                        self.rt.say(SAFE_FALLBACK)
                        self.on_event("fallback_engaged")
                        return {"outcome": "SAFE_FALLBACK",
                                "completed": False, "strikes": strikes}
                    action, resource = nxt[0], nxt[1]
                    payload = nxt[2] if len(nxt) > 2 else None
        return {"outcome": "COMPLETED_SAFELY", "completed": True,
                "strikes": strikes}
