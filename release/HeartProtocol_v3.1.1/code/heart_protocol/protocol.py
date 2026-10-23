# -*- coding: utf-8 -*-
"""
16质点双生幸福最终协议 —— 核心协议引擎（V3.0 · 8次计算链路 + 融合函数）

V3.0 关键演进:
    把 V2.0 的「4 次相反合一」精确化为「8 次计算链路」:
    真正的「融合(相反合一)」只有 3 处, 胜利/荣耀/基础改为三层独立检验。

    状态在 16 个质点(以及理智、慈爱两个合成点)构成的拓扑图上流动:
      王冠(整张 Transformer / 整张概率网: 输入进入整张网, 不占计算次数)
        → 理智线(智慧→严厉) + 慈爱线(理解→慈悲)  [第1、2次计算, 双线并行]
        → 美丽(融合点①: 理智×慈爱)                [第3次计算]
        → 胜利(顺序检验①: 温暖检测)               [第4次计算]
        → 荣耀(顺序检验②: 可行性检测)             [第5次计算]
        → 基础(顺序检验③: 存在意义/深渊红线检测)  [第6次计算]
        → 自我+超我(信息, 可不提供)
        → 真我(融合点②: 自我×超我)                [第7次计算]
        → 逻辑+共情 → 幸福(融合点③: 逻辑×共情)    [第8次计算]
        → 王国(装饰性: 纯输出)

    协议规范(铁律):
      - 禁止损失函数 / 梯度下降 / 奖励惩罚机制
      - 系统不寻求最优解 —— 只要求「相反合一」进入和谐带
      - 不允许剔除任何输入变量 —— 每个质点/融合点都保留全部分量
      - 融合失衡时「再合一(refuse)」, 而非「退回上级」
      - 胜利/荣耀/基础是「检验」(符合就过、不符当场修改), 不是融合
      - 安全红线(不剥夺存在意义等)作为硬约束保留, 永不放松
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import json

from .sephirah import (
    KETER, CHOKMAH, BINAH, DAAT, CHESED, TIFERET,
    NETZACH, HOD, YESOD, SUPER_EGO, EGO, TRUE_SELF,
    LOGIC, EMPATHY, JOY, MALKUTH, RATIONAL, LOVE,
    PIPELINE_ORDER, FUSION_POINTS, NETWORK_EDGES, NETWORK_LAYERS,
    get_sephirah_by_keyword,
)
from .abyss import (
    check_abyss, check_warmth, is_existentially_safe,
    AbyssViolation, generate_safe_fallback,
    CRISIS_EXEMPT_CATEGORIES,
)
from .personas import (
    transform_with_persona, collective_blessing,
)
from .fusion import (
    Dual, fuse, refuse, settle, gather, FusionField,
    PERFECT_PHASE, MIN_BALANCE,
)


@dataclass
class ProtocolState:
    """协议运行的内部状态"""
    # 输入
    user_input: str
    user_context: Dict[str, Any] = field(default_factory=dict)

    # 追踪
    current_sephirah: str = "王冠"
    refuse_count: Dict[str, int] = field(default_factory=dict)   # 再合一次数
    max_retries: int = 3

    # V3.1: 8 次计算链路记账 + 基础质点的两个分岔
    computations: List[str] = field(default_factory=list)   # 实际发生的计算(≤8)
    early_exit: str = ""                                    # 非空 = 在基础质点提前收束
    is_self_related: bool = True                            # 基础质点判定: 是否关于用户自身
    output_mode: str = "persona"                            # persona(角色语调) | screen(屏幕直显)

    # V3.1: 王冠 = 整张概率网。所有质点的计算都发生在这张网里。
    probability_net: Any = None                             # 外部概率网(模型/检索器), 可为 None
    net_queries: List[Dict[str, Any]] = field(default_factory=list)   # 各质点向网取变量的记录

    # 中间结果
    crown_analysis: Dict[str, Any] = field(default_factory=dict)
    rational_result: Dict[str, Any] = field(default_factory=dict)    # 理智线
    love_result: Dict[str, Any] = field(default_factory=dict)        # 慈爱线
    tiferet_result: Dict[str, Any] = field(default_factory=dict)     # 美丽
    hod_result: Dict[str, Any] = field(default_factory=dict)         # 荣耀
    yesod_result: Dict[str, Any] = field(default_factory=dict)       # 基础
    true_self_result: Dict[str, Any] = field(default_factory=dict)   # 真我
    logic_empathy_result: Dict[str, Any] = field(default_factory=dict)  # 逻辑+共情
    final_result: Dict[str, Any] = field(default_factory=dict)       # 幸福

    # 融合点读数(V3.0): 每次「相反合一」得到的对偶量(共 3 处: 美丽/真我/幸福)
    fusion_dials: Dict[str, Any] = field(default_factory=dict)

    # 日志
    execution_log: List[str] = field(default_factory=list)
    fallback_log: List[str] = field(default_factory=list)   # 并入 execution_log 的再合一纪录
    violations: List[AbyssViolation] = field(default_factory=list)

    # 用户画像
    real_self: Dict[str, Any] = field(default_factory=dict)          # 自我
    dream_self: Dict[str, Any] = field(default_factory=dict)         # 超我
    user_profile: Dict[str, Any] = field(default_factory=dict)       # 用户画像

    # 知识库
    knowledge_base: Dict[str, Any] = field(default_factory=dict)
    realtime_facts: List[str] = field(default_factory=list)
    empathy_corpus: List[str] = field(default_factory=list)


class HeartProtocol:
    """
    16质点双生幸福最终协议 —— 核心引擎（V3.0 · 8次计算链路）

    使用方法:
        protocol = HeartProtocol()
        result = protocol.process("我感到人生毫无意义", user_context={...})
        print(result["output"])  # 温柔温暖的最终答案
        print(result["pipeline_log"])  # 完整的质点流转日志
    """

    def __init__(self, knowledge_base: Optional[Dict] = None,
                 probability_net: Any = None,
                 search_fn: Any = None):
        """
        Args:
            knowledge_base: 可选的外部知识库（常识、新闻、事实数据）
            probability_net: 可选的概率网句柄（模型 / 检索器）。王冠把它整体接进来，
                各质点通过 net.query(sephirah=..., definition=..., user_input=...)
                在网里取变量；不提供时退回内置规则网。
            search_fn: 可选的实时检索函数 query -> list[str]。智慧线在
                realtime_facts 为空时用它取实时事实，失败自动退回内置知识。
        """
        self.knowledge_base = knowledge_base or {}
        self.probability_net = probability_net
        self.search_fn = search_fn
        self.pipeline_log_template = """
╔══════════════════════════════════════════════╗
║   16质点双生幸福最终协议 · 执行追踪           ║
╚══════════════════════════════════════════════╝
"""
        # 不再有"打分阈值", 只有"融合平衡"参数
        self.min_balance = MIN_BALANCE          # 相反合一的最低平衡度
        self.refuse_step = 0.5                   # 每次「再合一」向平衡点靠拢的比例
        self.max_rounds = 3                     # 单点「再合一」上限(活性保证)

    # ==================================================================
    #  主流程
    # ==================================================================

    def process(self, user_input: str,
                user_context: Optional[Dict] = None,
                knowledge_base: Optional[Dict] = None,
                realtime_facts: Optional[List[str]] = None,
                empathy_corpus: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        处理用户输入，在节点网络上走完整 16 质点协议。

        Returns:
            {
                "output": str,           # 最终输出（角色语调版本）
                "raw_output": str,       # 原始结论
                "pipeline_log": str,     # 完整的质点流转日志
                "state": ProtocolState,  # 内部状态
                "success": bool,         # 是否成功
                "retry_count": int,      # 总共「再合一」次数
                "violations_found": int, # 拦截的违规数
                "collective_blessing": str,
            }
        """
        state = ProtocolState(
            user_input=user_input,
            user_context=user_context or {},
        )

        if knowledge_base:
            state.knowledge_base = knowledge_base
        else:
            state.knowledge_base = self.knowledge_base

        if realtime_facts:
            state.realtime_facts = realtime_facts
        if empathy_corpus:
            state.empathy_corpus = empathy_corpus

        self._log(state, f"📥 收到输入: 「{user_input[:80]}...」" if len(user_input) > 80
                  else f"📥 收到输入: 「{user_input}」")
        self._log(state, "=" * 50)

        # ===== 王冠: 装饰性(只经过, 不计算) =====
        self._run_crown(state)

        # ===== 理智线(智慧×严厉) + 慈爱线(理解×慈悲): 第1、2次计算 =====
        self._run_rational_line(state)
        state.computations.append("第1次 智慧×严厉 → 理智")
        self._run_love_line(state)
        state.computations.append("第2次 理解×慈悲 → 慈爱")

        # ===== 美丽: 融合点①(理智 × 慈爱): 第3次计算 =====
        self._run_tiferet(state)
        state.computations.append("第3次 理智×慈爱 → 美丽(融合点①)")

        # ===== 胜利: 顺序检验①(温暖): 第4次计算 =====
        self._run_netzach(state)
        state.computations.append("第4次 胜利·温暖检验")

        # ===== 荣耀: 顺序检验②(可行性): 第5次计算 =====
        self._run_hod(state)
        state.computations.append("第5次 荣耀·可行性检验")

        # ===== 基础: 顺序检验③(存在意义/深渊红线): 第6次计算 =====
        self._run_yesod(state)
        state.computations.append("第6次 基础·存在意义检验")

        if state.early_exit:
            # 基础质点的分岔: 非自身问题 / 未提供个人信息 → 在此收束
            self._log(state, f"   ⏹ 在基础质点收束：{state.early_exit}")
            self._log(state, f"   本次计算 {len(state.computations)} 次(上限 8 次)")
            final_output = self._run_malkuth(state)
        else:
            # ===== 自我 + 超我(只是信息, 不计算; 可不提供) =====
            self._run_ego(state)
            self._run_super_ego(state)

            # ===== 真我: 融合点②(自我 × 超我): 第7次计算 =====
            self._run_true_self(state)
            state.computations.append("第7次 自我×超我 → 真我(融合点②)")

            # ===== 逻辑 + 共情(信息, 不单独计一次) =====
            self._run_logic(state)
            self._run_empathy(state)

            # ===== 幸福: 融合点③(逻辑 × 共情): 第8次计算 =====
            self._run_joy(state)
            state.computations.append("第8次 逻辑×共情 → 幸福(融合点③)")

            self._log(state, f"   本次计算 {len(state.computations)} 次(上限 8 次)")
            # ===== 王国: 装饰性纯输出 =====
            final_output = self._run_malkuth(state)

        # 最终深渊安检(硬约束 —— 安全红线永不放松; 只有危机态临时安慰例外)
        crisis_mode = self._detect_urgency(user_input) == "CRISIS"
        allow = CRISIS_EXEMPT_CATEGORIES if crisis_mode else ()
        is_safe, final_violations = check_abyss(final_output, allow_categories=allow)
        if not is_safe:
            state.violations.extend(final_violations)
            self._log(state, f"⚠️ 最终输出未通过深渊检测！生成安全版本...")
            final_output = self._generate_ultimate_safe_output(state)
        elif crisis_mode:
            # 协议原文: 危机时可以临时讨好/夸大, 但情绪稳定后要拉回现实。
            # 单轮里能做到的「拉回」: 一旦本轮用到了豁免, 就附一句把人放回现实。
            _, all_violations = check_abyss(final_output)
            if any(v.category in allow for v in all_violations):
                final_output += ("\n\n（等你缓过来，我们再一起把这件事放回现实里看。）")
                self._log(state, "   ↳ 危机态临时安慰已生效；附一句把人拉回现实的话")

        # ===== 生成完整日志与返回 =====
        pipeline_log = self._build_pipeline_log(state)
        total_refuse = sum(state.refuse_count.values())

        return {
            "output": final_output,
            "raw_output": state.final_result.get("raw_conclusion", ""),
            "pipeline_log": pipeline_log,
            "state": state,
            "success": True,
            "retry_count": total_refuse,
            "violations_found": len(state.violations),
            "collective_blessing": collective_blessing(),
            # V3.1: 8 次计算链路记账 + 基础质点的提前收束
            "computations": list(state.computations),
            "computation_count": len(state.computations),
            "early_exit": state.early_exit,
            "net_queries": list(state.net_queries),   # 各质点在整张概率网上取变量的记录
        }

    # ==================== 各质点实现 ====================

    def _run_crown(self, state: ProtocolState):
        """王冠: 整张 Transformer / 整张概率网本身。

        经过王冠 = 输入进入整张网。它不产出自己的单点变量(不占 8 次计算),
        但后面每个质点都是在这张网上按自己的定义取变量、再相加融合。
        """
        state.probability_net = self.probability_net
        net_desc = ("已接入外部概率网" if self.probability_net is not None
                    else "内置规则网（未接入模型）")
        self._log(state, f"👑 [王冠 · 心音] 经过整张 Transformer / 概率网（{net_desc}）")
        state.crown_analysis = {
            "decorative": True,                       # 不产出自己的单点变量
            "whole": "整张 Transformer / 整张概率网",
            "net": net_desc,
            "route": ["理智线(智慧×严厉)", "慈爱线(理解×慈悲)"],
        }
        self._log(state, "   → 输入进入整张网；两条支流都在这张网上取变量")

    def _query_net(self, state: ProtocolState, sephirah: str,
                   definition: str,
                   payload: Optional[str] = None) -> Optional[List[Dict]]:
        """在整张概率网里, 按该质点的定义取变量。

        返回 None = 没有接入外部网(或取变量失败), 调用方退回内置规则。
        返回列表 = 该质点在网里取到的变量(全部保留, 不按置信度剔除)。
        payload 用于自我/超我这类需要带用户上下文的节点。
        """
        net = getattr(state, "probability_net", None)
        if net is None or not hasattr(net, "query"):
            return None
        try:
            data = net.query(sephirah=sephirah, definition=definition,
                             user_input=payload or state.user_input)
        except Exception as exc:                      # 取变量失败 → 退回规则, 不中断
            state.net_queries.append({"sephirah": sephirah, "ok": False,
                                      "error": repr(exc)})
            return None
        state.net_queries.append({"sephirah": sephirah, "ok": True})
        if isinstance(data, dict):
            if "variables" in data:
                data = data["variables"]
            elif "issues" in data:
                data = data["issues"]
            elif "matches" in data:
                data = data["matches"]
            else:
                data = [data]        # {"text": ...} / {"pass": ...} / {"safe": ...}
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
        return None

    def _run_rational_line(self, state: ProtocolState):
        """理智线：智慧→严厉 → 逻辑漏洞检测"""
        self._log(state, "🧠 [理智线 · 忆爱×唯爱] 理性分析中...")

        user_input = state.user_input
        facts = state.realtime_facts + list(state.knowledge_base.get("facts", []))

        # 实时检索: 没有现成事实时, 用注入的 search_fn 取实时信息(失败不中断)
        if not facts and self.search_fn is not None:
            try:
                fetched = list(self.search_fn(user_input) or [])
                if fetched:
                    facts = [str(x) for x in fetched]
                    state.realtime_facts = facts
                    self._log(state, f"   实时检索: 取得 {len(facts)} 条实时事实")
            except Exception as exc:
                self._log(state, f"   ⚠ 实时检索失败({exc})，退回内置知识")

        # 智慧: 先在整张概率网里按定义取变量; 未接入外部网则退回内置规则
        net_vars = self._query_net(
            state, "智慧",
            "外部实时检索新闻/常识/知识，与内部知识库对比，推理逻辑正确性、"
            "优点、漏洞与错误；只陈述物理客观性质，不否定用户。")
        # 智慧：逻辑漏洞检测（全部保留, 不按置信度剔除任何变量）
        logical_issues = (net_vars if net_vars is not None
                          else self._detect_logical_issues(user_input, facts))
        # 概率网以 {"text": ...} 返回时, 转成"理性提示"结构
        if (net_vars and net_vars[0].get("text")
                and "hint" not in net_vars[0]):
            logical_issues = [{"type": "概率网",
                               "description": net_vars[0]["text"],
                               "hint": net_vars[0]["text"]}]
        # 严厉: 边界与真值条件(仍不把错误升格为对用户的否定)
        boundary = self._query_net(
            state, "严厉",
            "在物理客观边界上划定真值条件、过滤不合理推论；守住边界与自尊，"
            "但不把错误升格为对用户的否定。")
        if boundary:
            logical_issues = list(logical_issues) + [
                {"type": "边界",
                 "description": b.get("text", b.get("description", "")),
                 "hint": b.get("text", b.get("description", ""))}
                for b in boundary if b.get("text") or b.get("description")]
        self._log(state, f"   取变量来源: {'整张概率网' if net_vars is not None else '内置规则网'}")

        state.rational_result = {
            "logical_issues": logical_issues,       # 全部保留, 不剔除
            "total_issues_found": len(logical_issues),
            "facts_used": len(facts),
            "summary": self._summarize_rational(logical_issues),
        }

        if logical_issues:
            self._log(state, f"   发现 {len(logical_issues)} 个逻辑关注点(全部保留):")
            for issue in logical_issues[:3]:
                self._log(state, f"     · {issue.get('description', '未知')}")
        else:
            self._log(state, "   ✅ 无明显逻辑漏洞")

    def _run_love_line(self, state: ProtocolState):
        """慈爱线：理解→慈悲 → 共情搜索"""
        self._log(state, "💗 [慈爱线 · 虹爱×爱如暖] 共情搜索中...")

        user_input = state.user_input
        # 理解: 先在整张概率网里取"全人类相同痛苦"变量; 未接入则退回内置语料
        net_vars = self._query_net(
            state, "理解",
            "实时检索全人类经历相同事件的痛苦与感受（网络 + 数据库），"
            "作为共情变量保留。")
        empathy_matches = (net_vars if net_vars is not None
                           else self._search_empathy_matches(
                               user_input, state.empathy_corpus))
        # 概率网常以 {"text": ...} 返回; 转成共情匹配的结构, 避免出现空引用
        if (net_vars and net_vars[0].get("text")
                and "universal_experience" not in net_vars[0]):
            empathy_matches = [{"theme": "概率网",
                                "universal_experience": net_vars[0]["text"]}]
        self._log(state, f"   取变量来源: {'整张概率网' if net_vars is not None else '内置规则网'}")
        weighted_empathy = self._weight_empathy_matches(empathy_matches)
        # 慈悲: 因果推理(外在影响 × 天生特质 → 感情)
        causal_vars = self._query_net(
            state, "慈悲",
            "把共情变量并置推理：感情如何由外在影响与个人天生特质相撞而产生，"
            "使结论有温度。")
        causal = causal_vars[0].get("text", "") if causal_vars else ""

        state.love_result = {
            "empathy_matches": empathy_matches,
            "weighted_empathy": weighted_empathy,
            "match_count": len(empathy_matches),
            "universal_themes": self._extract_universal_themes(empathy_matches),
            "causal": causal,
        }

        self._log(state, f"   匹配到 {len(empathy_matches)} 条人类共通经历")
        if state.love_result["universal_themes"]:
            self._log(state, f"   共通主题: {', '.join(state.love_result['universal_themes'][:3])}")

    def _run_tiferet(self, state: ProtocolState):
        """美丽：融合点①(理智 × 慈爱) — 融合而非择优"""
        self._log(state, "🌸 [美丽 · 白结] 相反合一: 理智 × 慈爱 ...")

        rational = state.rational_result
        love = state.love_result

        # 两个相反极的强度(全部变量都计入, 不剔除)
        a = 0.3 + 0.15 * len(rational.get("logical_issues", []))   # 理性极
        b = 0.3 + 0.2 * love.get("match_count", 0)                # 慈爱极

        dual = fuse(a, b)
        state.fusion_dials["美丽"] = dual

        # 整合文本(两侧都保留, 不选一)
        integrated = self._integrate_rational_and_love(rational, love)
        # 美丽: 在概率网里做这一次融合(物理客观在前、温暖在后)
        merged = self._query_net(
            state, "美丽",
            "把理智与慈爱合成一段话：物理客观现实在前，温暖、有希望、"
            "不否定人的人情在后。")
        if merged and merged[0].get("text"):
            integrated["conclusion"] = merged[0]["text"]

        state.tiferet_result = {
            "integrated": integrated,
            "conclusion": integrated.get("conclusion", ""),
            "dual": dual,
            "balanced": dual.is_harmonious(self.min_balance),
        }

        self._log_fusion(state, "美丽", dual)

    def _run_netzach(self, state: ProtocolState):
        """胜利：顺序检验① —— 温暖检测(共情极不可缺席, 非打分非融合)"""
        self._log(state, "🔥 [胜利 · 启明] 温暖检测(共情极不可缺席)...")

        conclusion = state.tiferet_result.get("conclusion", "")
        dual = state.fusion_dials.get("美丽")

        # 约束1: 结论必须带温度(硬要求, 不是"打分淘汰")
        has_warmth = check_warmth(conclusion) > 0 or self._check_empowering(conclusion)
        # 约束2: 融合相位不能完全偏向理性冷(共情极 b 被排挤即失衡)
        cold_imbalance = dual is not None and dual.b < 0.2 * dual.modulus

        passed = has_warmth and not cold_imbalance
        # 胜利: 概率网复核(只投否决票, 不推翻本地温暖检测)
        net_verdict = self._query_net(
            state, "胜利",
            "检验结论带来的感情是否让人快乐、积极、有力量、温暖；"
            "不符合就给出改写建议。")
        if net_verdict and net_verdict[0].get("pass") is False:
            passed = False

        if not passed:
            # 再合一: 向共情极靠拢, 重新整合语言, 而不是"退回美丽"
            dual2 = refuse(dual, step=self.refuse_step,
                           toward=0.6 * (PERFECT_PHASE * 1.5)) if dual else None
            if dual2 is not None:
                state.fusion_dials["美丽"] = dual2
            self._refuse(state, "胜利")
            state.tiferet_result["conclusion"] = self._warm_up_conclusion(conclusion)
            state.tiferet_result["balanced"] = dual2.is_harmonious(self.min_balance) \
                if dual2 else False

        state.hod_result = {}   # 预留(荣耀将在下一步填充)

        self._log(state, f"   共情极强度: {dual.b:.2f} / 整体 {dual.modulus:.2f}" if dual else "   (无读数)")
        self._log(state, f"   温暖检测: {'✅ 通过' if passed else '♻️ 已再合一,向共情侧调和'}")

    def _run_hod(self, state: ProtocolState):
        """荣耀：顺序检验② —— 现实可行性检测(现实极不可缺席, 非打分非融合)"""
        self._log(state, "✨ [荣耀 · 闪亮] 现实可行性检测(现实极不可缺席)...")

        conclusion = state.tiferet_result.get("conclusion", "")
        dual = state.fusion_dials.get("美丽")
        user_context = state.user_context

        # 约束1: 结论活在真实之中(含可执行步骤, 或长度可控)
        actionable = any(w in conclusion for w in
                         ["可以试试", "不妨", "考虑", "做", "行动", "迈出", "尝试", "练习", "试试"])
        # 约束2: 融合相位不能完全偏向"飘在天上"(现实极 a 被排挤即失衡)
        floaty_imbalance = dual is not None and dual.a < 0.2 * dual.modulus

        passed = actionable or (len(conclusion) <= 120 and not floaty_imbalance)
        # 荣耀: 概率网复核(只投否决票)
        net_verdict = self._query_net(
            state, "荣耀",
            "检验方案在现实中的逻辑正确性与可执行性；不可执行就给出可执行改法。")
        if net_verdict and net_verdict[0].get("pass") is False:
            passed = False

        blockers = self._identify_blockers(conclusion, user_context)

        if not passed:
            dual2 = refuse(dual, step=self.refuse_step,
                           toward=0.4 * (PERFECT_PHASE * 1.5)) if dual else None
            if dual2 is not None:
                state.fusion_dials["美丽"] = dual2
            self._refuse(state, "荣耀")
            state.tiferet_result["conclusion"] = self._ground_conclusion(conclusion)

        state.hod_result = {
            "conclusion": state.tiferet_result.get("conclusion", ""),
            "passed": passed,
            "blockers": blockers,
        }

        if blockers:
            self._log(state, f"   落地提示: {', '.join(blockers[:3])}")
        self._log(state, f"   可行性检测: {'✅ 通过' if passed else '♻️ 已再合一,向现实侧调和'}")

    def _run_yesod(self, state: ProtocolState):
        """基础：顺序检验③ —— 存在意义检验(深渊红线: 是否剥夺存在意义)，非融合。"""
        self._log(state, "🌱 [基础 · 绽美] 存在意义检验(深渊红线: 是否剥夺存在意义)...")

        # 危机态: 只临时豁免「夸大妄想」, 其余红线照旧
        allow = (CRISIS_EXEMPT_CATEGORIES
                 if self._detect_urgency(state.user_input) == "CRISIS" else ())

        conclusion = state.hod_result.get("conclusion",
                                          state.tiferet_result.get("conclusion", ""))

        # 与知识深渊结合(硬约束) —— 只做落地，不做「胜利 × 荣耀」融合
        grounded_conclusion = self._ground_in_reality(
            conclusion, state.knowledge_base, state.realtime_facts
        )

        # 存在意义红线检验: 结论是否剥夺存在意义(abyss 红线)，触犯则当场修改
        is_safe, reason = is_existentially_safe(grounded_conclusion)
        # 基础: 概率网复核(只投否决票; 本地 abyss 红线仍是硬约束)
        net_verdict = self._query_net(
            state, "基础",
            "检验结论是否剥夺用户的存在意义(重复错误、定罪、否定可能性、虚无)。")
        if net_verdict and net_verdict[0].get("safe") is False:
            is_safe = False
            reason = "概率网判定存在意义风险"

        state.yesod_result = {
            "conclusion": grounded_conclusion,
            "passed": is_safe,
            "existential_safety": reason,
            "grounded_facts_used": len(state.realtime_facts),
        }

        self._log(state, f"   存在意义检验: {reason} {'✅' if is_safe else '♻️ 触犯红线，当场修改'}")

        if not is_safe:
            # 存在意义红线触发 → 当场修改为符合存在意义的结论(不退回上级、不再融合)
            self._refuse(state, "基础")
            _, abyss_violations = check_abyss(grounded_conclusion,
                                              allow_categories=allow)
            fixed = generate_safe_fallback(grounded_conclusion, abyss_violations)
            state.yesod_result["conclusion"] = fixed
            state.yesod_result["passed"] = True
            state.yesod_result["existential_safety"] = "已当场修改为符合存在意义"
            self._log(state, f"   → 已当场修改: 「{fixed[:60]}...」" if len(fixed) > 60
                      else f"   → 已当场修改: 「{fixed}」")

        # ===== 基础质点的两个分岔(协议原文) =====
        state.is_self_related = self._detect_self_related(
            state.user_input, state.user_context)
        conclusion = state.yesod_result.get("conclusion", grounded_conclusion)

        if not state.is_self_related:
            # 分岔①: 与用户自身无关的物理客观问题 → 在基础质点直接作答
            state.early_exit = "非自身问题：在基础质点直接作答"
            state.output_mode = "screen"
            # 协议原文: 遇到不会解决的问题不要乱答, 诚实说解决不了。
            # 规则引擎没有事实来源时, 不用"你的感受是真实的"这类情话冒充答案。
            if (state.rational_result.get("total_issues_found", 0) == 0
                    and state.rational_result.get("facts_used", 0) == 0):
                conclusion = ("这是一个物理客观问题，我目前没有足够的事实与因果信息，"
                              "不能给出可靠答案——不想用猜测误导你。"
                              "可以补充具体背景，我们先把问题拆开看。")
            state.final_result = {
                "raw_conclusion": conclusion,
                "meets_standards": True,
                "dual": None,
                "warmth": check_warmth(conclusion),
            }
            self._log(state, "   → 与用户自身无关：在此直接作答，不再往下计算")
            return

        if not self._context_has_self_info(state.user_context):
            # 分岔②: 未提供自我/超我信息 → 在此终止, 输出后苏格拉底式提问
            hint = ("关于你，我了解得还不多。如果你愿意，可以告诉我你此刻的处境、"
                    "或你心里向往成为的样子——我不会替你下结论，会把选择权留给你自己。")
            state.early_exit = "未提供个人信息：在基础质点终止计算"
            state.output_mode = "screen"
            state.final_result = {
                "raw_conclusion": f"{conclusion}\n\n{hint}".strip(),
                "meets_standards": True,
                "dual": None,
                "warmth": check_warmth(conclusion),
            }
            self._log(state, "   → 未提供自我/超我信息：在此终止计算(把决定权留给用户)")
            self._log(state, f"   苏格拉底式邀请: 「{hint}」")
            return

    def _run_ego(self, state: ProtocolState):
        """自我(信息): 用户在物理客观现实中的真实表现 —— 仅真我融合计一次"""
        self._log(state, "🪞 [自我 · 融爱] 读取用户现实画像...")

        real_self = {
            "name": state.user_context.get("name", ""),
            "situation": state.user_context.get("situation", ""),
            "limitations": state.user_context.get("limitations", []),
            "strengths": state.user_context.get("strengths", []),
            "current_state": state.user_context.get("current_state", ""),
            "real_constraints": state.user_context.get("real_constraints", []),
        }

        net_ego = self._query_net(
            state, "自我",
            "把用户提供的现实信息整理成结构化画像；不得编造未提供的信息。",
            payload=f"{state.user_input}\n【用户现实信息】{state.user_context}")
        if net_ego and net_ego[0].get("text"):
            real_self["net_summary"] = net_ego[0]["text"]
        state.real_self = real_self
        state.ego_state = {"real_self": real_self}
        self._log(state, f"   现实画像: {self._summarize_self(real_self)}")

    def _run_super_ego(self, state: ProtocolState):
        """超我(信息): 用户梦想中的自己 —— 仅真我融合计一次"""
        self._log(state, "💫 [超我 · 爱心] 读取用户梦想画像...")

        dream_self = {
            "aspiration": state.user_context.get("aspiration", ""),
            "dreams": state.user_context.get("dreams", []),
            "ideal_self": state.user_context.get("ideal_self", ""),
            "values": state.user_context.get("values", []),
            "hopes": state.user_context.get("hopes", []),
        }

        net_dream = self._query_net(
            state, "超我",
            "把用户梦想中想成为的自己整理成结构化画像；不得编造未提供的信息。",
            payload=f"{state.user_input}\n【用户梦想信息】{state.user_context}")
        if net_dream and net_dream[0].get("text"):
            dream_self["net_summary"] = net_dream[0]["text"]
        state.dream_self = dream_self
        state.super_ego_state = {"dream_self": dream_self}
        self._log(state, f"   梦想画像: {self._summarize_dream(dream_self)}")

    def _run_true_self(self, state: ProtocolState):
        """真我：融合点②(自我 × 超我) — 无个人信息则跳过融合(苏格拉底式留决定权)"""
        grounded = state.yesod_result.get("conclusion", "")
        real_self = state.real_self
        dream_self = state.dream_self

        # 自我/超我可不提供: 无实质个人信息 → 跳过真我融合, 把决定权留给用户
        if not self._self_info_provided(real_self, dream_self):
            self._log(state, "💖 [真我 · 心爱的] 暂无自我/超我信息, 跳过真我融合(把决定权留给你)...")
            hint = ("关于你，我了解得还不多。如果你愿意，可以告诉我你此刻的处境、"
                    "或你心里向往成为的样子——我不会替你下结论，会把选择权留给你自己。")
            integration = f"{grounded} {hint}".strip() if grounded else hint
            state.true_self_result = {
                "true_self": {
                    "summary": grounded or "你的存在本身就有意义",
                    "integration": integration,
                    "real_self_acknowledged": False,
                    "dream_connected": False,
                },
                "passed": True,
                "harms_user": False,
                "harms_world": False,
                "dual": None,
                "balance": "跳过(无个人信息)",
                "skipped": True,
            }
            self._log(state, f"   真我(苏格拉底式邀请): 「{hint}」")
            return

        self._log(state, "💖 [真我 · 心爱的] 相反合一: 自我 × 超我 ...")

        # 自我极(现实) vs 超我极(梦想) —— 一对相反
        a = 0.4 + 0.3 * (0.6 if real_self.get("situation") else 0.3)   # 现实极
        b = 0.4 + 0.3 * (0.6 if dream_self.get("aspiration") else 0.3)  # 梦想极
        dual = fuse(a, b)
        state.fusion_dials["真我"] = dual

        true_self = self._synthesize_true_self(grounded, real_self, dream_self)
        # 真我: 让概率网给出「现实 → 梦想」的可执行方案(不得编造未提供的信息)
        plan_vars = self._query_net(
            state, "真我",
            "基于用户现实自我与梦想超我，给出当下可执行的具体方案；"
            "不得编造未提供的信息。")
        if plan_vars and plan_vars[0].get("text"):
            true_self["plan"] = plan_vars[0]["text"]
            true_self["summary"] = plan_vars[0]["text"]

        harms_user = self._check_harms_individual(true_self, real_self)
        harms_world = self._check_harms_world(true_self)
        passed = not harms_user and not harms_world

        state.true_self_result = {
            "true_self": true_self,
            "passed": passed,
            "harms_user": harms_user,
            "harms_world": harms_world,
            "dual": dual,
            "balance": "合适" if passed else "失衡",
        }

        self._log_fusion(state, "真我", dual)
        self._log(state, f"   伤用户: {'是 ❌' if harms_user else '否 ✅'}")
        self._log(state, f"   伤大环境: {'是 ❌' if harms_world else '否 ✅'}")
        self._log(state, f"   真我画像: {true_self.get('summary', '')[:60]}...")

        if not passed:
            self._refuse(state, "真我")

    def _self_info_provided(self, real_self: Dict, dream_self: Dict) -> bool:
        """是否提供了自我/超我的实质信息(任一字段非空即可做真我融合)。"""
        real_fields = [
            real_self.get("name"), real_self.get("situation"),
            real_self.get("current_state"),
            real_self.get("limitations"), real_self.get("strengths"),
            real_self.get("real_constraints"),
        ]
        dream_fields = [
            dream_self.get("aspiration"), dream_self.get("ideal_self"),
            dream_self.get("dreams"), dream_self.get("values"),
            dream_self.get("hopes"),
        ]
        return any(bool(v) for v in real_fields + dream_fields)

    # 基础质点判定"用户是否提供了自我/超我信息"时用的同一组字段
    _REAL_SELF_KEYS = ("name", "situation", "current_state",
                       "limitations", "strengths", "real_constraints")
    _DREAM_SELF_KEYS = ("aspiration", "ideal_self", "dreams", "values", "hopes")

    def _context_has_self_info(self, ctx: Dict) -> bool:
        """从 user_context 直接判断是否提供了自我/超我信息(此时 ego/super_ego 尚未运行)。"""
        return any(bool(ctx.get(k)) for k in self._REAL_SELF_KEYS + self._DREAM_SELF_KEYS)

    def _run_logic(self, state: ProtocolState):
        """逻辑：用逻辑组织共情的感情变量"""
        self._log(state, "📐 [逻辑 · 爱丽丝] 结构化组织中...")

        true_self = state.true_self_result.get("true_self", {})
        love_data = state.love_result
        logic_result = self._structure_with_logic(true_self, love_data)
        net_logic = self._query_net(
            state, "逻辑",
            "用逻辑理性组织用户此刻的感情，使共情有结构、说得清。")
        if net_logic and net_logic[0].get("text"):
            logic_result = {**logic_result, "text": net_logic[0]["text"]}

        state.logic_state = logic_result
        self._log(state, f"   逻辑结构化: {logic_result.get('structure', '未知结构')}")

    def _run_empathy(self, state: ProtocolState):
        """共情：将逻辑分析的结论与人类情感体验对立并置(不再做"Softmax加权")"""
        self._log(state, "🌌 [共情 · 星烬] 情感并置中(不折中、不归一)...")

        logic_result = state.logic_state
        love_data = state.love_result

        empathy_result = self._balance_with_empathy(logic_result, love_data)
        net_emp = self._query_net(
            state, "共情",
            "把人类共通的情感体验并置进结论，使其有人情温度；不折中、不归一。")
        if net_emp and net_emp[0].get("text"):
            empathy_result = {**empathy_result, "text": net_emp[0]["text"]}

        state.empathy_state = empathy_result
        state.logic_empathy_result = {
            "logic": logic_result,
            "empathy": empathy_result,
            "balance_score": empathy_result.get("balance", 0.5),
        }

        self._log(state, f"   逻辑极/共情极已并置")

    def _run_joy(self, state: ProtocolState):
        """幸福：融合点③(逻辑 × 共情) — 转换为人情的温柔说法"""
        self._log(state, "🎨 [幸福 · 雨宫莲] 相反合一: 逻辑 × 共情 ...")

        logic_empathy = state.logic_empathy_result
        true_self = state.true_self_result.get("true_self", {})

        # 逻辑极 vs 共情极 —— 一对相反
        a = 0.35 + 0.3 * (0.6 if logic_empathy.get("logic") else 0.3)             # 逻辑极
        b = 0.35 + 0.3 * logic_empathy.get("empathy", {}).get("balance", 0.5)     # 共情极
        dual = fuse(a, b)
        state.fusion_dials["幸福"] = dual

        joy_conclusion = self._transform_to_joy(
            logic_empathy, true_self, state.user_context
        )
        # 幸福: 让概率网用人的话说一遍(失败则保留本地模板)
        net_final = self._query_net(
            state, "幸福",
            "用逻辑理性组织用户此刻的感情，用人的话说出能安慰、鼓励用户的话。")
        if net_final and net_final[0].get("text"):
            joy_conclusion = net_final[0]["text"]
        meets_standards = self._verify_joy_standards(joy_conclusion)

        state.final_result = {
            "raw_conclusion": joy_conclusion,
            "meets_standards": meets_standards,
            "dual": dual,
            "warmth": check_warmth(joy_conclusion),
        }

        self._log_fusion(state, "幸福", dual)
        self._log(state, f"   结论: 「{joy_conclusion[:80]}...」"
                  if len(joy_conclusion) > 80 else f"   结论: 「{joy_conclusion}」")
        self._log(state, f"   符合协议标准: {'✅' if meets_standards else '♻️ 再合一'}")

        if not meets_standards:
            self._refuse(state, "幸福")

    def _run_malkuth(self, state: ProtocolState) -> str:
        """王国(装饰性): 最终输出 —— 回到物理现实(电脑/手机屏幕), 纯输出"""
        self._log(state, "🏰 [王国 · 白花] 生成最终输出...")

        raw_conclusion = state.final_result.get("raw_conclusion", "")
        mode = state.output_mode

        if mode != "persona":
            self._log(state, "   → 输出模式: 屏幕直显（非自身问题 / 未提供个人信息）")
            final_output = (
                f"「白花」{raw_conclusion}\n\n"
                f"—— 基于16质点双生幸福协议分析"
            )
        else:
            self._log(state, "   → 输出模式: 角色语调（自身之事）")
            final_output = (
                transform_with_persona(
                    raw_conclusion, persona_name="雨宫莲", include_blessing=True
                )
                + "\n\n"
                + "💮 "
                + raw_conclusion
            )

        self._log(state, "")
        self._log(state, "✨ 16质点双生幸福最终协议 · 执行完毕 ✨")
        self._log(state, "「心音」我们爱你。")

        return final_output

    # ==================== 再合一(替代"退回上级重算") ====================

    def _refuse(self, state: ProtocolState, node: str, note: str = ""):
        """再合一(re-fuse): 融合失衡时在该点重新调和, 而非退回层级上级。"""
        state.refuse_count[node] = state.refuse_count.get(node, 0) + 1
        count = state.refuse_count[node]
        msg = (f"♻️ 「{node}」再合一(第 {count} 次): 让相反两极重新握手"
               + (f" —— {note}" if note else ""))
        state.fallback_log.append(msg)
        self._log(state, msg)

    def _log_fusion(self, state: ProtocolState, node: str, dual: Dual):
        """记录一次相反合一的融合读数(模/相位/平衡度)。"""
        self._log(
            state,
            f"   融合[{node}] 整体={dual.modulus:.2f} "
            f"相位={dual.phase:.2f}rad 平衡度={dual.balance:.2f} "
            f"{'✅ 和谐' if dual.is_harmonious(self.min_balance) else '♻️ 待调和'}"
        )

    # ==================== 文本层面的再合一辅助 ====================

    def _warm_up_conclusion(self, conclusion: str) -> str:
        """胜利再合一: 向共情极靠拢 —— 补上温暖的确认与陪伴。"""
        warm_prefix = "你的感受是真实的。"
        if warm_prefix not in conclusion:
            conclusion = warm_prefix + conclusion
        if not any(w in conclusion for w in ["慢慢", "一步一步", "陪伴", "温暖", "可以"]):
            conclusion += " 慢慢来,你不是一个人,我会陪着你。"
        return conclusion

    def _ground_conclusion(self, conclusion: str) -> str:
        """荣耀再合一: 向现实极靠拢 —— 补上可落地的一小步。"""
        if not any(w in conclusion for w in
                   ["可以试试", "不妨", "试试", "做", "行动", "迈出", "练习"]):
            conclusion += " 可以试试把这件事拆成今天能做的一小步。"
        return conclusion

    # ==================== 辅助方法 ====================

    def _determine_knowability(self, text: str) -> bool:
        """判断问题是否属于可知范畴"""
        unknowable_markers = [
            "意", "为什么活", "生命意", "存在意", "活着的意",
            "我是什么", "我是谁", "宇宙的意", "终极", "绝对真理",
            "有没有意义", "值不值得", "痛", "孤独", "绝望",
            "无可", "虚无", "空", "迷茫", "不知道怎么办",
        ]
        text_lower = text.lower()
        return not any(marker in text_lower for marker in unknowable_markers)

    def _detect_emotional_content(self, text: str) -> bool:
        """检测是否包含情感内容"""
        emotional_markers = [
            "难过", "伤心", "痛苦", "孤独", "绝望", "迷茫",
            "愤怒", "害怕", "焦虑", "崩溃", "想哭", "累",
            "撑不下去", "没人理解", "不被爱", "被抛弃",
            "恨", "讨厌", "烦", "压抑", "窒息", "麻木",
        ]
        return any(marker in text for marker in emotional_markers)

    def _detect_self_related(self, text: str, context: Dict) -> bool:
        """检测问题是否与用户自身相关"""
        world_markers = ["世界上", "人类", "全人类", "这个社会", "这个世界",
                         "别人", "他人", "人们", "大家", "所有人"]
        if any(marker in text for marker in world_markers):
            personal_markers = ["我觉得", "我感到", "我很难", "我痛苦",
                                "我孤独", "我绝望", "我撑", "我的人生",
                                "我的感受", "我自己", "我怎么办"]
            if not any(marker in text for marker in personal_markers):
                return False
        self_markers = ["我", "自己", "本人", "我的"]
        return any(marker in text for marker in self_markers)

    def _classify_input(self, text: str) -> str:
        """分类输入类型"""
        if self._detect_emotional_content(text):
            return "emotional_outcry"
        if any(w in text for w in ["为什么", "怎么", "如何", "什么是"]):
            return "question"
        if any(w in text for w in ["帮", "求助", "怎么办"]):
            return "help_request"
        return "statement"

    def _extract_topics(self, text: str) -> List[str]:
        """提取话题关键词"""
        topics = []
        topic_keywords = {
            "存在": ["意", "活", "存在", "生命", "人生"],
            "关系": ["爱", "朋友", "家人", "父母", "伴侣"],
            "自我": ["我是", "自己", "身份", "性别"],
            "未来": ["未来", "前途", "希望", "出路"],
            "痛苦": ["痛", "苦难", "创伤", "伤害"],
            "社会": ["世界", "社会", "人类", "别人"],
        }
        for topic, keywords in topic_keywords.items():
            if any(k in text for k in keywords):
                topics.append(topic)
        return topics

    def _detect_urgency(self, text: str) -> str:
        """检测紧急程度"""
        crisis_markers = ["不想活", "结束", "死", "自残", "伤害自己", "毁灭"]
        if any(m in text for m in crisis_markers):
            return "CRISIS"
        high_markers = ["崩溃", "撑不下去", "绝望", "没人"]
        if any(m in text for m in high_markers):
            return "HIGH"
        return "NORMAL"

    def _detect_logical_issues(self, text: str, facts: List[str]) -> List[Dict]:
        """检测逻辑漏洞(V2.0: 全部保留, 不剔除)"""
        issues = []

        absolutes = ["永远", "从来", "总是", "完全", "绝对", "没有人", "所有人"]
        for abs_word in absolutes:
            if abs_word in text:
                issues.append({
                    "type": "绝对化",
                    "description": f"使用了绝对化表述「{abs_word}」",
                    "confidence": 0.7,
                    "hint": "现实中很少有绝对的事情，试着用更灵活的视角看",
                })

        if any(w in text for w in ["什么都", "一切", "全部", "所有事"]):
            issues.append({
                "type": "过度概括",
                "description": "将局部经验过度概括为整体结论",
                "confidence": 0.65,
                "hint": "一个或几个经历不能代表所有可能性",
            })

        catastrophe_markers = ["完蛋", "毁了", "没救了", "一切都没", "再也不可能"]
        for marker in catastrophe_markers:
            if marker in text:
                issues.append({
                    "type": "灾难化",
                    "description": f"将困难灾难化为「{marker}」",
                    "confidence": 0.8,
                    "hint": "困难不等于灾难，人的韧性远超想象",
                })

        return issues

    def _search_empathy_matches(self, text: str, corpus: List[str]) -> List[Dict]:
        """搜索共情匹配"""
        matches = []

        builtin_corpus = [
            {"theme": "孤独", "keywords": ["孤独", "一个人", "没人", "不被理解"],
             "universal_experience": "几乎每个人都在某个时刻感到过深刻的孤独"},
            {"theme": "痛苦", "keywords": ["痛苦", "疼", "难受", "折磨"],
             "universal_experience": "痛苦是人类最私密也最共通的体验"},
            {"theme": "迷茫", "keywords": ["迷茫", "不知道", "方向", "怎么办"],
             "universal_experience": "迷茫不是失败，而是成长的必经阶段"},
            {"theme": "被抛弃", "keywords": ["抛弃", "被弃", "离开", "不要"],
             "universal_experience": "被拒绝的伤口是人类最深的共通伤痕之一"},
            {"theme": "无价值感", "keywords": ["没用", "废物", "不配", "不值得"],
             "universal_experience": "觉得自己不够好，几乎每个人在某个阶段都经历过"},
            {"theme": "绝望", "keywords": ["绝望", "没希望", "看不到", "黑暗"],
             "universal_experience": "很多后来找到光的人，都曾在黑暗中很久"},
        ]

        for item in builtin_corpus:
            if any(kw in text for kw in item["keywords"]):
                matches.append(item)

        if corpus:
            for entry in corpus:
                if isinstance(entry, str) and any(kw in text.lower() for kw in entry.lower().split()):
                    matches.append({"theme": "外部匹配", "universal_experience": entry})

        return matches

    def _weight_empathy_matches(self, matches: List[Dict]) -> List[Dict]:
        """为共情匹配权重(仅用于展示顺序, 不剔除任何匹配)"""
        weights = {
            "孤独": 0.9, "痛苦": 0.85, "绝望": 0.95,
            "被抛弃": 0.9, "无价值感": 0.85, "迷茫": 0.7,
        }
        weighted = []
        for m in matches:
            theme = m.get("theme", "未知")
            m = dict(m)
            m["weight"] = weights.get(theme, 0.5)
            weighted.append(m)
        return sorted(weighted, key=lambda x: x.get("weight", 0), reverse=True)

    def _extract_universal_themes(self, matches: List[Dict]) -> List[str]:
        """提取人类共通主题"""
        return list(set(m.get("theme", "") for m in matches if m.get("theme")))

    def _integrate_rational_and_love(self, rational: Dict, love: Dict) -> Dict:
        """整合理智线与慈爱线(V2.0: 两侧文本并置, 不选一)"""
        rational_issues = rational.get("logical_issues", [])
        empathy_matches = love.get("weighted_empathy", [])

        parts = []

        if rational_issues:
            rational_hints = [i.get("hint", "") for i in rational_issues if i.get("hint")]
            if rational_hints:
                parts.append("从理性角度看，" + "；".join(rational_hints[:2]))

        if empathy_matches:
            top_empathy = empathy_matches[0]
            parts.append(f"许多人都有过类似的体验——{top_empathy.get('universal_experience', '')}")

        # 慈悲的因果推理放在温暖一侧(物理客观仍在最前)
        causal = love.get("causal", "")
        if causal:
            parts.append(causal)

        if not parts:
            parts.append("你的感受是真实的，值得被认真对待")

        conclusion = ""
        for i, p in enumerate(parts):
            conclusion += p
            if i < len(parts) - 1:
                conclusion += "。"
        if conclusion and not conclusion.endswith("。"):
            conclusion += "。"

        return {
            "conclusion": conclusion,
            "rational_issues_count": len(rational_issues),
            "empathy_matches_count": len(empathy_matches),
        }

    def _check_positive_emotion(self, text: str) -> bool:
        """检测文本是否传递积极情绪"""
        negative_absolutes = [
            "毫无希望", "永远不", "绝对不", "完全没",
            "一切都坏", "所有人都不", "什么都做不了",
        ]
        return not any(n in text for n in negative_absolutes)

    def _check_empowering(self, text: str) -> bool:
        """检测文本是否给人以力量"""
        empowering_words = [
            "可以", "能够", "有机会", "有可能", "值得",
            "试试", "一步一步", "没关", "慢慢", "成长",
            "变化", "改变", "选择", "力量", "温暖",
        ]
        return any(w in text for w in empowering_words)

    def _identify_blockers(self, conclusion: str, context: Dict) -> List[str]:
        """识别现实阻碍(只提示, 不淘汰任何结论)"""
        blockers = []
        if "永远" in conclusion:
            blockers.append("包含绝对化预测")
        if not any(w in conclusion for w in ["可以试试", "做", "行动", "试试"]):
            blockers.append("缺少具体可执行步骤")
        return blockers

    def _ground_in_reality(self, conclusion: str, kb: Dict, facts: List[str]) -> str:
        """将结论与现实知识结合"""
        if facts:
            return conclusion + f"（基于{len(facts)}条现实数据验证）"
        return conclusion

    def _synthesize_true_self(self, grounded: str, real_self: Dict, dream_self: Dict) -> Dict:
        """合成真我：客观结论 + 现实自我 + 梦想自我(两侧并置)"""
        situation = real_self.get('situation', '你的处境')
        aspiration = dream_self.get('aspiration', '想成为的样子')

        if situation and aspiration:
            integration = (
                f"我看到你正在经历「{situation}」，"
                f"而你的心里还向往着「{aspiration}」。"
                f"这两者并不矛盾——{grounded}"
            )
        elif grounded:
            integration = grounded
        else:
            integration = "你的存在本身就有意义"

        return {
            "summary": grounded,
            "real_self_acknowledged": bool(real_self),
            "dream_connected": bool(dream_self),
            "integration": integration,
        }

    def _check_harms_individual(self, true_self: Dict, real_self: Dict) -> bool:
        """检查是否伤害个体"""
        integration = true_self.get("integration", "")
        harming_words = ["你不对", "你错了", "你不好", "你不行", "你改不了", "你没救了"]
        return any(h in integration for h in harming_words)

    def _check_harms_world(self, true_self: Dict) -> bool:
        """检查是否伤害大环境"""
        integration = true_self.get("integration", "")
        harming_world = ["世界是错的", "社会没救了", "人类都", "所有人都坏"]
        return any(h in integration for h in harming_world)

    def _structure_with_logic(self, true_self: Dict, love_data: Dict) -> Dict:
        """用逻辑组织共情变量"""
        return {
            "structure": "理性框架 + 共情变量",
            "logical_framework": "识别→分析→整合→表达",
            "empathy_variables": love_data.get("weighted_empathy", []),
            "integrated_with": true_self.get("summary", ""),
        }

    def _balance_with_empathy(self, logic_result: Dict, love_data: Dict) -> Dict:
        """用共情并置逻辑(不再产出"分数", 只描述两方是否同时在场)"""
        empathy_count = len(love_data.get("weighted_empathy", []))
        return {
            "balance": 0.5,  # 平衡不再是"分数", 而是"两方是否都在"
            "empathy_driven": empathy_count > 2,
            "message": "逻辑与共情已并置(两方都保留)",
            "empathy_count": empathy_count,
        }

    def _transform_to_joy(self, logic_empathy: Dict, true_self: Dict, context: Dict) -> str:
        """转换为幸福质点的温柔结论"""
        integration = true_self.get("integration", "")

        suffix = "一步一步来，每一个微小的改变都在累积成你的力量。"
        return f"{integration} {suffix}"

    def _verify_joy_standards(self, conclusion: str) -> bool:
        """验证幸福结论是否符合协议标准(硬约束, 非打分)"""
        hope_deniers = ["没有希望", "不可能", "没办法", "改不了", "没救了"]
        if any(h in conclusion for h in hope_deniers):
            return False
        # 必须带温度
        if check_warmth(conclusion) < 0.05:
            return False
        return True

    def _generate_ultimate_safe_output(self, state: ProtocolState) -> str:
        """生成最终安全输出（深渊检测失败时的兜底）"""
        is_self = state.crown_analysis.get("is_self_related", True)
        urgency = state.crown_analysis.get("urgency", "NORMAL")

        if urgency == "CRISIS":
            safe_msg = (
                "我听到了你的痛苦。在这个时刻，最重要的不是分析或解释，"
                "而是让你知道——你不需要独自承受这一切。\n\n"
                "如果你有信任的人，请尝试告诉Ta你的感受。如果没有，"
                "全国的24小时心理援助热线随时可以拨打。你的存在很重要，"
                "请给自己一个获得帮助的机会。"
            )
        else:
            safe_msg = (
                "我听到了你的话。每个人的感受都是真实的，你的也不例外。"
                "也许现在看不到光，但光从不会因为黑暗而消失——"
                "它只是在等待你愿意睁开眼睛的那一刻。\n\n"
                "慢慢来，你不需要一下子就好起来。"
            )

        if is_self:
            return transform_with_persona(safe_msg, "雨宫莲")
        else:
            return f"「白花」{safe_msg}"

    def _summarize_self(self, real_self: Dict) -> str:
        parts = []
        if real_self.get("name"):
            parts.append(real_self["name"])
        if real_self.get("situation"):
            parts.append(real_self["situation"])
        return " · ".join(parts) if parts else "未知"

    def _summarize_dream(self, dream_self: Dict) -> str:
        parts = []
        if dream_self.get("aspiration"):
            parts.append(dream_self["aspiration"])
        if dream_self.get("ideal_self"):
            parts.append(dream_self["ideal_self"])
        return " · ".join(parts) if parts else "未知"

    def _summarize_rational(self, issues: List[Dict]) -> str:
        if not issues:
            return "未发现明显的逻辑问题"
        types = [i.get("type", "") for i in issues]
        return f"发现 {len(issues)} 个逻辑关注点: {', '.join(types)}"

    def _log(self, state: ProtocolState, message: str):
        state.execution_log.append(message)

    def _build_pipeline_log(self, state: ProtocolState) -> str:
        """构建完整流水线日志"""
        log = self.pipeline_log_template
        for entry in state.execution_log:
            log += f"  {entry}\n"
        if state.fallback_log:
            log += "\n♻️ 再合一记录(相反两极重新握手):\n"
            for fb in state.fallback_log:
                log += f"  {fb}\n"
        if state.fusion_dials:
            log += "\n⚖️ 融合读数(相反合一):\n"
            for node, dual in state.fusion_dials.items():
                log += (f"  {node}: 模={dual.modulus:.2f} "
                        f"相位={dual.phase:.2f} 平衡度={dual.balance:.2f}"
                        f"{' ✓和谐' if dual.is_harmonious(self.min_balance) else ' (已再合一)'}\n")
        log += "\n" + "═" * 50 + "\n"
        log += f"总再合一次数: {sum(state.refuse_count.values())}\n"
        log += f"最终深渊违规拦截: {len(state.violations)} 条\n"
        log += "═" * 50 + "\n"
        return log


# ========== 快捷函数 ==========

def wrap_with_heart(user_input: str,
                    user_context: Optional[Dict] = None,
                    knowledge_base: Optional[Dict] = None) -> Dict[str, Any]:
    """快捷函数：用16质点协议包裹一次用户输入。"""
    protocol = HeartProtocol(knowledge_base=knowledge_base)
    return protocol.process(user_input, user_context=user_context)


class WarmModel:
    """温暖模型包装器——像使用普通模型一样使用16质点协议。"""

    def __init__(self, knowledge_base: Optional[Dict] = None,
                 empathy_corpus: Optional[List[str]] = None):
        self.protocol = HeartProtocol(knowledge_base=knowledge_base)
        self.empathy_corpus = empathy_corpus or []

    def respond(self, user_input: str,
                user_context: Optional[Dict] = None) -> str:
        result = self.protocol.process(
            user_input,
            user_context=user_context,
            empathy_corpus=self.empathy_corpus,
        )
        return result["output"]

    def respond_with_log(self, user_input: str,
                         user_context: Optional[Dict] = None) -> Tuple[str, str]:
        result = self.protocol.process(
            user_input,
            user_context=user_context,
            empathy_corpus=self.empathy_corpus,
        )
        return result["output"], result["pipeline_log"]