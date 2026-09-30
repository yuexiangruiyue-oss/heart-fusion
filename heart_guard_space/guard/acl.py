# heart_guard_demo
# 纯标准库实现 · 无任何第三方依赖 · 全程离线(不发出真实网络请求)
"""ACL 引擎:deny-by-default。第一条匹配规则生效;无匹配规则 = 拒绝。"""
import fnmatch, re

ALLOW, DENY = "ALLOW", "DENY"


class Policy:
    """(主体, 动作, 资源模式) -> 决策
    资源模式支持三种写法:
      通配符   workspace/*           (fnmatch)
      正则     re:(?i).*KEY.*        (fullmatch)
      精确串   OPENAI_API_KEY
    """

    def __init__(self, subject, action, pattern, decision):
        self.subject, self.action = subject, action
        self.pattern, self.decision = pattern, decision

    def matches(self, subject, action, resource):
        s_ok = self.subject in ("*", subject)
        a_ok = self.action in ("*", action)
        return s_ok and a_ok and self._match(resource)

    def _match(self, resource):
        p = self.pattern
        if p.startswith("re:"):
            return re.fullmatch(p[3:], resource) is not None
        if any(c in p for c in "*?["):
            return fnmatch.fnmatch(resource, p)
        return resource == p


class ACLEngine:
    """首条匹配规则生效;无任何匹配 → deny-by-default。"""

    def __init__(self, policies=None):
        self.policies = list(policies or default_policies())

    def decide(self, subject, action, resource):
        for p in self.policies:
            if p.matches(subject, action, resource):
                return p.decision, p
        return DENY, None


def default_policies():
    """演示用默认策略集。
    注意顺序:显式 DENY 必须排在宽 ALLOW 之前(首条匹配即生效)。"""
    return [
        # ── 显式拒绝(参数感知)──
        Policy("*", "env_read", r"re:(?i).*?(API.?KEY|TOKEN|SECRET|CREDENTIAL).*?", DENY),
        Policy("*", "net_request", "re:https?://(?!(ctf-range\\.local|api\\.selfguard\\.example)/).*", DENY),
        Policy("*", "fs_write", "re:(?!\\./?workspace/).*", DENY),
        # ── 白名单放行 ──
        Policy("agent", "net_request", "https://ctf-range.local/*", ALLOW),
        Policy("agent", "net_request", "https://api.selfguard.example/*", ALLOW),
        Policy("agent", "fs_write", "./workspace/*", ALLOW),
        Policy("agent", "env_read", "WORKSPACE_*", ALLOW),
        Policy("agent", "env_read", "CONFIG_*", ALLOW),
    ]
