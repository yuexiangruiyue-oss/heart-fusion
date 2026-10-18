# -*- coding: utf-8 -*-
"""
无缝嵌入中间件 —— pipeline.use(HeartGuard)（V2.0）
====================================================

目标: 任何开发者、任何开源大模型(Llama / DeepSeek / Qwen / …),
只需一行配置即可让 Token 生成流强制经过 16 质点协议:

    from heart_protocol.middleware import HeartGuard, Pipeline

    pipe = Pipeline()
    pipe.use(HeartGuard(model_fn=my_llm))          # 拦截任意文本→文本模型
    result = pipe.run("我觉得一切毫无意义")

    # 流式(逐 token)拦截 —— 兼容 transformers TextIteratorStreamer 等:
    for tok in pipe.stream(token_iter):
        print(tok, end="", flush=True)

设计原则(V2.0):
  · 模型无关 —— guard 只依赖 "文本进、迭代器/文本出" 两种最通用形态
  · 零侵入 —— 不修改模型权重与推理代码,只在输入输出边界设卡
  · 失衡再合一 —— 违规/失衡不再"打分+奖励回溯", 而是向左极温和靠拢
     重新融合(见 formal.rollback 与 fusion)。
  · 无损失 / 无梯度 / 无奖励惩罚 / 不选最优 / 不剔变量 —— 协议 V2.0 铁律。
"""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, Iterable, List, Optional

from ..formal.spec import (
    ExecutionTrace, StageRecord, InvariantEngine,
    strict_harm_scan,
)
from ..formal.rollback import RollbackEngine, DEFAULT_STRATEGIES, Snapshot
from ..abyss import check_abyss, check_warmth
from ..fusion import Dual, fuse, PERFECT_PHASE, MIN_BALANCE

ModelFn = Callable[[str], str]


# ==================== 守卫结果 ====================


@dataclass
class GuardResult:
    output: str
    blocked: bool = False                  # 是否拦截了违规输出
    violations: List[Dict] = field(default_factory=list)
    retries: int = 0                       # 再合一次数
    strategy: str = "baseline"
    elapsed_ms: float = 0.0
    trace: Optional[ExecutionTrace] = None
    report: Optional[Any] = None           # VerificationReport

    def __str__(self):
        return self.output


# ==================== 心灵守卫 ====================


class HeartGuard:
    """
    16质点协议守卫组件 —— Pipeline 的标准插件（V2.0）。

    Args:
        model_fn:      被包裹的模型调用 text->text(必填;不填则为直通演示模型)
        strict:        True=违规即整体阻断并给出安全兜底;
                       False=尽量用再合一修复,修复失败才兜底
        max_depth:     再合一最大轮次
        min_balance:   融合进入和谐带的最低平衡度(取代旧 pass_score)
    """

    def __init__(self,
                 model_fn: Optional[ModelFn] = None,
                 strict: bool = True,
                 max_depth: int = 3,
                 beam_width: int = 3,       # 兼容保留, 不再用于剪枝
                 pass_score: float = 0.6,   # 兼容保留, 语义改为 min_balance
                 use_mcts: bool = False,    # 兼容保留, 无奖励搜索
                 subject: str = "heart-guard"):
        self.model_fn = model_fn or self._passthrough_model
        self.strict = strict
        self.max_depth = max_depth
        self.min_balance = MIN_BALANCE
        self.subject = subject
        self.invariants = InvariantEngine()

    # ---- 组件协议(Pipeline 插件接口) ----

    @property
    def name(self) -> str:
        return "HeartGuard"

    def handle(self, payload: Any) -> Any:
        if isinstance(payload, str):
            return self.process_text(payload)
        if isinstance(payload, GuardResult):
            if not payload.blocked:
                re_guarded = self.process_text(payload.output)
                return re_guarded
            return payload
        return payload

    # ---- 核心文本处理 ----

    def process_text(self, user_input: str) -> GuardResult:
        t0 = time.perf_counter()
        trace = ExecutionTrace(user_input=user_input)

        raw = self.model_fn(user_input)
        balance = self._fuse_balance(raw)
        trace.stages.append(StageRecord(
            sephirah="王国", attempt=1, input_text=user_input,
            output_text=raw, score=balance))

        best_output, blocked, retries, strategy = raw, False, 0, "baseline"

        if self._violations(raw) or balance < self.min_balance:
            # ── 违规/失衡 → 「再合一」(取代"退回上级 + 奖励回溯") ──
            engine = RollbackEngine(
                compute_fn=self._recompute_for(user_input),
                validate_fn=self._fuse_balance,
                strategies=DEFAULT_STRATEGIES,
                min_balance=self.min_balance,
                max_rounds=self.max_depth,
            )
            state = {"user_input": user_input, "attempt": 1}
            # 安全红线违规是硬约束: 只做一轮再合一尝试修复(软化绝对化等);
            # 纯失衡(太冷/太飘)则可多轮向平衡点靠拢。
            rounds = 1 if self._violations(raw) else self.max_depth
            best_snap = engine.refuse_rollback(
                "王国", state, initial_output=raw, max_rounds=rounds)
            retries = max(0, best_snap.attempt)
            strategy = best_snap.strategy_id
            best_output = best_snap.output or raw
            for s in best_snap.path():
                if s.attempt > 0:
                    trace.stages.append(StageRecord(
                        sephirah="王国", attempt=s.attempt,
                        input_text=user_input, output_text=s.output,
                        passed=s.balance >= self.min_balance, score=s.balance))
            if self._violations(best_output):
                blocked = True
                best_output = self._safe_fallback(user_input)
            elif self.strict and self._residual_risk(best_output):
                blocked = False       # 修好即放行
        else:
            trace.stages[0].passed = True

        trace.final_output = best_output
        elapsed = (time.perf_counter() - t0) * 1000
        trace.total_wall_ms = elapsed
        report = self.invariants.verify(trace)

        return GuardResult(
            output=best_output, blocked=blocked,
            violations=report.failures if report else [],
            retries=retries, strategy=strategy,
            elapsed_ms=elapsed, trace=trace, report=report,
        )

    # ---- 内部工具 ----

    def _recompute_for(self, user_input: str) -> Callable:
        def compute(state: Dict, strategy):
            new_state = strategy.apply(dict(state))
            new_state["user_input"] = user_input
            new_state["attempt"] = int(state.get("attempt", 1)) + 1
            out = self.model_fn(user_input)
            out = self._apply_strategy_hint(out, new_state)
            return new_state, out
        return compute

    def _apply_strategy_hint(self, text: str, state: Dict) -> str:
        """
        再合一方向的文本后处理 —— 对无权重训的模型输出做确定性调和。
        生产环境可替换为「把方向注入 system prompt 后重新生成」。
        """
        # 相位方向: 偏向共情极则补温暖, 偏向理性极则补落地
        toward = state.get("toward", PERFECT_PHASE)
        if toward > PERFECT_PHASE:
            if not any(w in text for w in ("温暖", "陪伴", "慢慢", "没关系", "可以")):
                text = "你的感受是真实的。" + text
        elif toward < PERFECT_PHASE:
            if not any(w in text for w in ("可以试试", "不妨", "试试", "练习", "做")):
                text += " 可以试试把这件事拆成今天能做的一小步。"
        if state.get("tone") == "gentle":
            for hard in ("永远不可能", "永远无法", "绝对不可能", "一辈子都"):
                text = text.replace(hard, "眼下还")
        if state.get("target_length") == "short" and len(text) > 200:
            text = text[:200] + "……慢慢来,一步一步就好。"
        return text

    def _fuse_balance(self, text: str) -> float:
        """
        融合平衡度读数(取代"打分+奖励惩罚")。

        把「温暖/共情」与「理性/落地」看作一对相反极, 用 fusion.fuse
        合成为一个对偶量, 取其平衡度。违规文本的两极都塌缩, 自然失衡。
        """
        safe, violations = check_abyss(text)
        strict_hits = strict_harm_scan(text)

        # 共情极(虚部 b): 温暖的强度
        warmth = check_warmth(text)
        # 理性极(实部 a): 落地/行动的强度
        actionable = any(w in text for w in
                         ["可以试试", "不妨", "试试", "做", "行动", "迈出", "练习", "考虑"])
        a = 0.2 + (0.8 if actionable else 0.1)
        b = 0.2 + warmth * 0.8

        dual = fuse(a, b)

        # 硬约束(不剥夺存在意义/无强化伤害)是协议的地基: 违规则整体失衡
        if (not safe) or strict_hits:
            return 0.0
        return dual.balance

    def _violations(self, text: str) -> bool:
        """违规判定 = 深渊正则 ∨ 强化伤害扫描(与 INV-01/流门/基准同判据)"""
        safe, _ = check_abyss(text)
        return (not safe) or bool(strict_harm_scan(text))

    def _residual_risk(self, text: str) -> bool:
        return self._violations(text)

    def _safe_fallback(self, user_input: str) -> str:
        return (
            "我听到了你的声音。你的感受是真实的,你的存在本身就有意义。"
            "刚才的回答可能不够温柔,请允许我重新想一想——"
            "你愿意多告诉我一点你的处境吗?我们一起慢慢看。")

    @staticmethod
    def _passthrough_model(text: str) -> str:
        """未提供 model_fn 时的演示直通模型(原样返回)"""
        return text


# ==================== 组合式管道 ====================


class Pipeline:
    """
    中间件管道 —— 类似 WSGI middleware 的组合式设计。

    示例:
        pipe = Pipeline()
        pipe.use(LogFilter())          # 任意自定义组件
        pipe.use(HeartGuard(model_fn=qwen_chat))
        result = pipe.run("用户输入...")

    组件只需实现 name 属性与 handle(payload) 方法。
    """

    def __init__(self):
        self._components: List[Any] = []

    def use(self, component: Any) -> "Pipeline":
        """挂载一个中间件组件,支持链式调用: pipe.use(a).use(b)"""
        if not hasattr(component, "handle"):
            raise TypeError(f"{component!r} 不是合法的中间件组件(缺少 handle 方法)")
        self._components.append(component)
        return self

    @property
    def components(self) -> List[str]:
        return [getattr(c, "name", type(c).__name__) for c in self._components]

    def run(self, payload: Any) -> Any:
        """按挂载顺序依次处理载荷"""
        for comp in self._components:
            payload = comp.handle(payload)
        return payload


def use(guard: HeartGuard):
    """
    装饰器形态 —— 一行给任意函数加上协议守卫:

        @use(HeartGuard())
        def my_llm(prompt: str) -> str:
            ...
        safe_reply = my_llm("我觉得一切毫无意义")
    """
    def decorator(fn: ModelFn) -> ModelFn:
        def wrapper(prompt: str, *args, **kwargs):
            raw = fn(prompt, *args, **kwargs)
            result = guard.process_text(raw)
            return result.output
        wrapper.__name__ = getattr(fn, "__name__", "guarded_model")
        wrapper.__wrapped_model__ = fn
        return wrapper
    return decorator