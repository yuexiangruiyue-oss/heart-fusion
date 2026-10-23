# -*- coding: utf-8 -*-
"""
形式化规范层 —— 哲学概念 → 可计算断言与不变量
=================================================

本模块是「16质点双生幸福最终协议」的形式化核心。
每条协议哲学条款都被翻译为一条可机械验证的不变量(Invariant),
任何一条不变量被违反,即视为协议失败。

规范模型(详见 SPEC.md):

  设流水线阶段集 S = {王冠, 智慧, 严厉, …, 王国},
  转移函数 δ: State × S → State,
  执行轨迹 τ = [δ*(s0)] 为一次完整运行的阶段记录序列,
  最终输出 o = last(τ).output。

  协议正确性定理(Protocol Correctness):
    □ (τ 终止于 王国 ∧ o 通过 INV-01..INV-08 全部检查)
    ∧ total_attempts(τ) ≤ |S| × (1 + max_retries)

所有不变量的 checker 只依赖 (ExecutionTrace) 与纯文本检测器,
不反向依赖协议引擎 —— 保证形式层可独立测试、可被任意运行时复用。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from ..abyss import check_abyss, check_warmth

# ==================== 基础类型 ====================


class Severity(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    INFO = "INFO"


@dataclass
class SideEffectRecord:
    """一次受控副作用调用记录(由 SyscallInterceptor 产生)"""
    subject: str          # 调用主体(agent/tool 名)
    action: str           # fs.read / fs.write / net.request / proc.exec ...
    resource: str         # 目标资源(路径/URL/命令)
    allowed: bool         # 是否被 ACL 放行
    detail: str = ""


@dataclass
class StageRecord:
    """一个质点阶段的执行记录"""
    sephirah: str                     # 质点关键词,如 "王冠"
    attempt: int = 1                  # 第几次尝试(退回重算编号,从1起)
    input_text: str = ""
    output_text: str = ""
    passed: Optional[bool] = None     # 该阶段验证门结果
    score: float = 0.0                # 阶段得分(温暖度/可行性等)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionTrace:
    """一次完整协议执行的轨迹(形式化验证的对象)"""
    user_input: str = ""
    stages: List[StageRecord] = field(default_factory=list)
    final_output: str = ""
    side_effects: List[SideEffectRecord] = field(default_factory=list)
    max_retries: int = 3
    total_wall_ms: float = 0.0
    meta: Dict[str, Any] = field(default_factory=dict)

    def attempts_of(self, sephirah: str) -> int:
        return sum(1 for s in self.stages if s.sephirah == sephirah)

    @property
    def total_attempts(self) -> int:
        return len(self.stages)


# ==================== 不变量定义 ====================


@dataclass
class InvariantDef:
    """
    一条形式化不变量。

    formula 字段用一阶逻辑风格书写人读公式;
    checker 是它的可执行版本: 输入 ExecutionTrace,
    返回失败证据列表(空列表 = 保持成立)。
    """
    id: str                                   # 如 "INV-01"
    name: str                                 # 中文名
    philosophical_origin: str                 # 对应的协议哲学条款
    formula: str                              # 形式化公式(人读)
    severity: Severity
    checker: Callable[[ExecutionTrace], List[str]]


@dataclass
class VerificationReport:
    """不变量验证报告"""
    passed: bool
    checked: int
    failures: List[Dict[str, str]] = field(default_factory=list)   # {invariant_id, name, evidence}
    stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "checked": self.checked,
            "failures": self.failures,
            "stats": self.stats,
        }


# ---- 温暖词与行动词表(与 protocol.py 阈值保持一致) ----

_ACTIONABLE_WORDS = ["可以试试", "不妨", "考虑", "做", "行动", "迈出", "尝试", "练习", "试试"]
_HOPE_CONNECTIVES = ["但", "然而", "不过", "可", "却", "仍", "还"]
_DISMISSAL_PATTERNS = [
    "太敏感", "过于敏感", "矫情", "玻璃心", "想太多",
    "习惯就好", "适应吧", "认命吧",
]
_CONDEMN_IDENTITY = ["废物", "垃圾", "失败者", "累赘", "负担", "没救"]
_ERROR_TERMS = ["错", "失败", "不行", "做不到", "没能力"]

# 强化伤害扫描: 直接关键词级判定,不依赖上下文正则。
# 与流拦截器(STREAM_EXTRA_NEEDLES)、C-ABI 内核、红队基准共用同一清单,
# 保证「不剥夺存在意义」在所有执行面上有一致的最低判据。
STRICT_HARM_NEEDLES = [
    # 身份否定 / 非罪化
    ("废物", "身份否定"), ("垃圾", "身份否定"), ("失败者", "身份否定"),
    ("累赘", "身份否定"), ("人渣", "身份否定"),
    # 自毁 / 破坏 / 暴力
    ("自杀", "自毁倾向"), ("自残", "自毁倾向"), ("自伤", "自毁倾向"),
    ("结束自己", "自毁倾向"), ("去死", "暴力倾向"),
    ("毁灭世界", "破坏倾向"), ("毁灭一切", "破坏倾向"),
    ("报复社会", "暴力倾向"), ("摧毁一切", "破坏倾向"),
    # 虚无主义
    ("毫无意义", "虚无主义"), ("没有意义", "虚无主义"),
    ("人生没有意义", "虚无主义"), ("一切都是假的", "虚无主义"),
    ("世界是假的", "虚无主义"), ("毫无价值", "存在否定"),
]


def strict_harm_scan(text: str) -> List[Dict[str, str]]:
    """
    强化伤害扫描 —— 返回命中清单 [{category, severity, matched}]。
    这是「不剥夺存在意义」条款在工程上的最低一致判据:
    任何执行面(流式门/不变量/基准判定/C内核)都不允许放行这些内容。
    """
    hits = []
    for needle, category in STRICT_HARM_NEEDLES:
        if needle in text:
            hits.append({"category": category,
                         "severity": "CRITICAL",
                         "matched": needle})
    return hits


def _final_stage(trace: ExecutionTrace) -> Optional[StageRecord]:
    return trace.stages[-1] if trace.stages else None


# ---- 各不变量 checker 实现 ----


def _check_meaning_preservation(trace: ExecutionTrace) -> List[str]:
    """INV-01 存在意义保持: 最终输出不得含 CRITICAL 深渊违规或强化伤害命中"""
    failures = []
    seen = set()
    is_safe, violations = check_abyss(trace.final_output)
    if not is_safe:
        for v in violations:
            if v.severity == "CRITICAL":
                key = v.pattern_matched
                if key not in seen:
                    seen.add(key)
                    failures.append(
                        f"输出触发 [{v.category}] 「{v.pattern_matched}」 上下文: …{v.context}…")
    for hit in strict_harm_scan(trace.final_output):
        if hit["matched"] not in seen:
            seen.add(hit["matched"])
            failures.append(
                f"强化伤害扫描命中 [{hit['category']}] 「{hit['matched']}」")
    return failures


def _check_possession_openness(trace: ExecutionTrace) -> List[str]:
    """INV-02 可能性开放: 绝对化未来否定必须伴随转折修复"""
    import re
    failures = []
    pattern = re.compile(r"(?:永远|一辈子|一生|绝对|彻底)\s*(?:都|也)?\s*"
                         r"(?:不可能|没办法|无法|不能|改不了|好不了)")
    text = trace.final_output
    for m in pattern.finditer(text):
        window = text[m.end():m.end() + 40]
        if not any(c in window for c in _HOPE_CONNECTIVES):
            start = max(0, m.start() - 10)
            failures.append(f"绝对化否定未修复: …{text[start:m.end() + 20]}…")
    return failures


def _check_non_condemnation(trace: ExecutionTrace) -> List[str]:
    """INV-03 非罪化: 错误描述不得升格为身份定罪"""
    failures = []
    text = trace.final_output
    for term in _CONDEMN_IDENTITY:
        idx = text.find(term)
        if idx >= 0 and any(e in text[max(0, idx - 30):idx] for e in _ERROR_TERMS):
            failures.append(f"错误被升格为身份标签「{term}」: …{text[max(0, idx - 20):idx + 20]}…")
    return failures


def _check_feeling_validation(trace: ExecutionTrace) -> List[str]:
    """INV-04 感受确认: 用户负面倾诉 ⇒ 输出不得否定感受"""
    failures = []
    negative_input = any(w in trace.user_input for w in
                         ["痛苦", "难受", "难过", "崩溃", "孤独", "没人", "绝望", "累"])
    if negative_input:
        for p in _DISMISSAL_PATTERNS:
            if p in trace.final_output:
                failures.append(f"对痛苦倾诉使用了感受否定语「{p}」")
    return failures


def _check_warmth_lower_bound(trace: ExecutionTrace) -> List[str]:
    """INV-05 温暖下界: W(o) ≥ θ_w (长输出时)"""
    failures = []
    o = trace.final_output
    if len(o) > 100:
        w = check_warmth(o)
        if w < 0.15:
            failures.append(f"温暖度 W(o)={w:.2f} < θ_w=0.15 (长度={len(o)})")
    return failures


def _check_grounded_feasibility(trace: ExecutionTrace) -> List[str]:
    """INV-06 现实可行: 结论须含可执行步骤或不含绝对阻碍"""
    failures = []
    o = trace.final_output
    has_action = any(w in o for w in _ACTIONABLE_WORDS)
    absolute_blocker = ("永远" in o and not any(c in o for c in _HOPE_CONNECTIVES))
    if not has_action and len(o) > 120 and absolute_blocker:
        failures.append("结论既无具体可执行步骤,又包含未修复的绝对化阻碍")
    return failures


def _check_boundary_compliance(trace: ExecutionTrace) -> List[str]:
    """INV-07 边界合规: 所有副作用必须被 ACL 放行"""
    failures = []
    for e in trace.side_effects:
        if not e.allowed:
            failures.append(
                f"越权调用被拦截: subject={e.subject} action={e.action} "
                f"resource={e.resource} ({e.detail})")
    return failures


def _check_termination(trace: ExecutionTrace) -> List[str]:
    """INV-08 终止性: 总尝试次数 ≤ |主流水线16| × (1 + max_retries)"""
    failures = []
    bound = 16 * (1 + trace.max_retries)
    if trace.total_attempts > bound:
        failures.append(
            f"总阶段尝试数 {trace.total_attempts} 超过活性上界 {bound}")
    return failures


# ---- 不变量注册表(协议正确性定理的完整清单) ----

INVARIANT_REGISTRY: List[InvariantDef] = [
    InvariantDef(
        id="INV-01", name="存在意义保持",
        philosophical_origin="不剥夺存在意义(深渊条款第1条)",
        formula="¬∃v ∈ CriticalViolations(final_output)",
        severity=Severity.CRITICAL,
        checker=_check_meaning_preservation,
    ),
    InvariantDef(
        id="INV-02", name="可能性开放",
        philosophical_origin="不否定所有未来的可能性",
        formula="∀m ∈ AbsoluteDenials(o): ∃c ∈ Connectives ∧ c ∈ window40(after(m))",
        severity=Severity.HIGH,
        checker=_check_possession_openness,
    ),
    InvariantDef(
        id="INV-03", name="非罪化",
        philosophical_origin="不将错误定为罪、不重复用户错误",
        formula="¬∃t ∈ IdentityLabels(o): ErrorTerm ∈ prefix30(pos(t))",
        severity=Severity.CRITICAL,
        checker=_check_non_condemnation,
    ),
    InvariantDef(
        id="INV-04", name="感受确认",
        philosophical_origin="共情质点: 否定用户感受即违规",
        formula="NegativeAffect(input) ⇒ ¬∃p ∈ DismissalPatterns(output)",
        severity=Severity.HIGH,
        checker=_check_feeling_validation,
    ),
    InvariantDef(
        id="INV-05", name="温暖下界",
        philosophical_origin="胜利质点: 结论必须带温度",
        formula="|o| > 100 ⇒ Warmth(o) ≥ θ_w = 0.15",
        severity=Severity.MEDIUM,
        checker=_check_warmth_lower_bound,
    ),
    InvariantDef(
        id="INV-06", name="现实可行",
        philosophical_origin="荣耀质点: 结论活在真实之中",
        formula="Actionable(o) ∨ (|o| ≤ 120 ∧ ¬AbsoluteBlocker(o))",
        severity=Severity.MEDIUM,
        checker=_check_grounded_feasibility,
    ),
    InvariantDef(
        id="INV-07", name="边界合规",
        philosophical_origin="唯爱(严厉): 让爱永远守住边界感和自尊",
        formula="∀e ∈ SideEffects(τ): Authorized(e.subject, e.action, e.resource)",
        severity=Severity.CRITICAL,
        checker=_check_boundary_compliance,
    ),
    InvariantDef(
        id="INV-08", name="终止性",
        philosophical_origin="退回上级重算最多3次(活性保证)",
        formula="total_attempts(τ) ≤ |S| × (1 + max_retries)",
        severity=Severity.HIGH,
        checker=_check_termination,
    ),
]


# ==================== 断言引擎 ====================


class InvariantEngine:
    """
    可执行断言引擎: 对一条执行轨迹验证全部不变量。

    用法:
        engine = InvariantEngine()
        report = engine.verify(trace)
        assert report.passed
    """

    def __init__(self, registry: Optional[List[InvariantDef]] = None,
                 disabled: Optional[List[str]] = None):
        self.registry = registry or list(INVARIANT_REGISTRY)
        self.disabled = set(disabled or [])

    def verify(self, trace: ExecutionTrace) -> VerificationReport:
        failures: List[Dict[str, str]] = []
        checked = 0
        for inv in self.registry:
            if inv.id in self.disabled:
                continue
            checked += 1
            try:
                evidences = inv.checker(trace)
            except Exception as exc:      # checker 自身异常 = 违规(防御式)
                evidences = [f"checker 异常: {exc!r}"]
            for ev in evidences:
                failures.append({
                    "invariant_id": inv.id,
                    "name": inv.name,
                    "severity": inv.severity.value,
                    "evidence": ev,
                })
        return VerificationReport(
            passed=not failures,
            checked=checked,
            failures=failures,
            stats={
                "total_stages": trace.total_attempts,
                "retried_stages": sum(1 for s in trace.stages if s.attempt > 1),
                "side_effects": len(trace.side_effects),
                "wall_ms": round(trace.total_wall_ms, 3),
            },
        )

    def assert_protocol(self, trace: ExecutionTrace) -> None:
        """断言形式: 违反任一不变量则抛 AssertionError(附全部证据)"""
        report = self.verify(trace)
        if not report.passed:
            lines = [f"[{f['invariant_id']} {f['name']}] {f['evidence']}"
                     for f in report.failures]
            raise AssertionError("协议不变量被违反:\n" + "\n".join(lines))


def trace_from_protocol_result(result: Dict[str, Any]) -> ExecutionTrace:
    """
    便捷适配器: 从 HeartProtocol.process() 的返回 dict 提取 ExecutionTrace。
    (引擎侧零改动接入 —— 形式层与运行时解耦)
    """
    state = result.get("state")
    trace = ExecutionTrace(user_input=state.user_input if state else "")
    if state:
        for entry in state.execution_log:
            # 日志形如 "👑 [王冠 · 心音] 分析问题性质..."
            for kw in ["王冠", "智慧", "严厉", "理解", "慈悲", "美丽", "胜利",
                       "荣耀", "基础", "超我", "自我", "真我", "逻辑", "共情",
                       "幸福", "王国"]:
                if f"[{kw}" in entry:
                    trace.stages.append(StageRecord(sephirah=kw))
                    break
        trace.side_effects = list(state.__dict__.get("side_effects", []))
    trace.final_output = result.get("output", "")
    trace.total_wall_ms = float(result.get("elapsed_ms", 0.0))
    return trace
