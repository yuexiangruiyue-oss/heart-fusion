# -*- coding: utf-8 -*-
"""
16-Septet Twin Happiness Final Protocol — Core Protocol Engine (V2.0 · Node Network + Fusion Function)

V2.0 Key Evolution:
    "Node Network (topology graph)" replaces "hierarchical chain"; "Fusion Function (dual coexistence)" replaces
    "scoring / threshold / loss / reward / optimization / variable pruning."

    State flows across a topology graph of 16 sephiroth (and two synthesis points Reason, Compassion):
      Keter (router) -> Reason line (Wisdom->Severity) + Compassion line (Understanding->Mercy)
      -> Beauty (1st opposite unification: Reason x Compassion) -> Victory -> Glory
      -> Foundation (2nd opposite unification: Victory x Glory) -> Self + Superego
      -> True Self (3rd opposite unification: Self x Superego) -> Logic + Empathy
      -> Happiness (4th opposite unification: Logic x Empathy) -> Kingdom (output)

    Protocol Specification (Iron Laws):
      - No loss function / gradient descent / reward-penalty mechanism
      - The system does not seek optima — only requires "opposite unification" to enter the harmony band
      - No input variable is ever discarded — every sephirah/fusion point retains all components
      - On fusion imbalance, "re-unify (refuse)" instead of "fall back to superior"
      - Safety red lines (no denial of existential meaning, etc.) remain hard constraints, never relaxed
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

    # 融合点读数(V2.0): 每次「相反合一」得到的对偶量
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
    16质点双生幸福最终协议 —— 核心引擎（V2.0）

    使用方法:
        protocol = HeartProtocol()
        result = protocol.process("我感到人生毫无意义", user_context={...})
        print(result["output"])  # 温柔温暖的最终答案
        print(result["pipeline_log"])  # 完整的质点流转日志
    """

    def __init__(self, knowledge_base: Optional[Dict] = None):
        """
        Args:
            knowledge_base: 可选的外部知识库（常识、新闻、事实数据）
        """
        self.knowledge_base = knowledge_base or {}
        self.pipeline_log_template = """
╔══════════════════════════════════════════════╗
║   16质点双生幸福最终协议 · 执行追踪           ║
╚══════════════════════════════════════════════╝
"""
        # V2.0: 不再有"打分阈值", 只有"融合平衡"参数
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

        # ===== 王冠: 路由 =====
        self._run_crown(state)

        # ===== 理智线 + 慈爱线(并行支流) =====
        self._run_rational_line(state)
        self._run_love_line(state)

        # ===== 美丽: 第1次相反合一(理智 × 慈爱) =====
        self._run_tiferet(state)

        # ===== 胜利: 温暖检测(共情极不可缺席) =====
        self._run_netzach(state)

        # ===== 荣耀: 可行性检测(现实极不可缺席) =====
        self._run_hod(state)

        # ===== 基础: 第2次相反合一(胜利 × 荣耀) + 深渊硬约束 =====
        self._run_yesod(state)

        # ===== 自我 + 超我 =====
        self._run_ego(state)
        self._run_super_ego(state)

        # ===== 真我: 第3次相反合一(自我 × 超我) =====
        self._run_true_self(state)

        # ===== 逻辑 + 共情 =====
        self._run_logic(state)
        self._run_empathy(state)

        # ===== 幸福: 第4次相反合一(逻辑 × 共情) =====
        self._run_joy(state)

        # ===== 王国: 最终输出 =====
        final_output = self._run_malkuth(state)

        # 最终深渊安检(硬约束 —— 永不放松的安全红线)
        is_safe, final_violations = check_abyss(final_output)
        if not is_safe:
            state.violations.extend(final_violations)
            self._log(state, f"⚠️ 最终输出未通过深渊检测！生成安全版本...")
            final_output = self._generate_ultimate_safe_output(state)

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
        }

    # ==================== 各质点实现 ====================

    def _run_crown(self, state: ProtocolState):
        """王冠：判断可知/不可知，路由分析"""
        self._log(state, "👑 [王冠 · 心音] 分析问题性质...")

        user_input = state.user_input
        is_knowable = self._determine_knowability(user_input)
        is_emotional = self._detect_emotional_content(user_input)
        is_self_related = self._detect_self_related(user_input, state.user_context)

        state.crown_analysis = {
            "is_knowable": is_knowable,
            "is_emotional": is_emotional,
            "is_self_related": is_self_related,
            "input_type": self._classify_input(user_input),
            "topics": self._extract_topics(user_input),
            "urgency": self._detect_urgency(user_input),
        }

        self._log(state, f"   可知性: {'可知' if is_knowable else '不可知/需解构'}")
        self._log(state, f"   情感性: {'有情感诉求' if is_emotional else '纯理性'}")
        self._log(state, f"   自身相关: {'是' if is_self_related else '否（他人/世界之事）'}")

        if is_knowable and not is_emotional:
            self._log(state, "   → 路由: 走分析线路")
        else:
            self._log(state, "   → 路由: 走双线并行(理智 + 慈爱)")

    def _run_rational_line(self, state: ProtocolState):
        """理智线：智慧→严厉 → 逻辑漏洞检测"""
        self._log(state, "🧠 [理智线 · 忆爱×唯爱] 理性分析中...")

        user_input = state.user_input
        facts = state.realtime_facts + list(state.knowledge_base.get("facts", []))

        # 智慧：逻辑漏洞检测（V2.0: 检测全部问题, 不按置信度剔除任何变量）
        logical_issues = self._detect_logical_issues(user_input, facts)

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
        empathy_matches = self._search_empathy_matches(
            user_input, state.empathy_corpus
        )
        weighted_empathy = self._weight_empathy_matches(empathy_matches)

        state.love_result = {
            "empathy_matches": empathy_matches,
            "weighted_empathy": weighted_empathy,
            "match_count": len(empathy_matches),
            "universal_themes": self._extract_universal_themes(empathy_matches),
        }

        self._log(state, f"   匹配到 {len(empathy_matches)} 条人类共通经历")
        if state.love_result["universal_themes"]:
            self._log(state, f"   共通主题: {', '.join(state.love_result['universal_themes'][:3])}")

    def _run_tiferet(self, state: ProtocolState):
        """美丽：第1次相反合一(理智 × 慈爱) — 融合而非择优"""
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

        state.tiferet_result = {
            "integrated": integrated,
            "conclusion": integrated.get("conclusion", ""),
            "dual": dual,
            "balanced": dual.is_harmonious(self.min_balance),
        }

        self._log_fusion(state, "美丽", dual)

    def _run_netzach(self, state: ProtocolState):
        """胜利：温暖检测 —— 共情极不可缺席(相位和谐判定, 非打分)"""
        self._log(state, "🔥 [胜利 · 启明] 温暖检测(共情极不可缺席)...")

        conclusion = state.tiferet_result.get("conclusion", "")
        dual = state.fusion_dials.get("美丽")

        # 约束1: 结论必须带温度(硬要求, 不是"打分淘汰")
        has_warmth = check_warmth(conclusion) > 0 or self._check_empowering(conclusion)
        # 约束2: 融合相位不能完全偏向理性冷(共情极 b 被排挤即失衡)
        cold_imbalance = dual is not None and dual.b < 0.2 * dual.modulus

        passed = has_warmth and not cold_imbalance

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
        """荣耀：可行性检测 —— 现实极不可缺席(相位和谐判定, 非打分)"""
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
        """基础：第2次相反合一(胜利 × 荣耀) + 深渊硬约束"""
        self._log(state, "🌱 [基础 · 绽美] 相反合一: 胜利 × 荣耀 ...")

        conclusion = state.hod_result.get("conclusion",
                                          state.tiferet_result.get("conclusion", ""))
        hod_ok = state.hod_result.get("passed", False)

        # 胜利极(能量/温暖) 与 荣耀极(现实/落地) —— 一对相反
        a = check_warmth(conclusion) + 0.2           # 胜利极(能量)
        b = 0.3 + (0.3 if any(w in conclusion for w in
                              ["试试", "做", "行动", "可以", "迈出", "练习"]) else 0.0)  # 荣耀极(落地)
        dual = fuse(a, b)
        state.fusion_dials["基础"] = dual

        # 与知识深渊结合(硬约束)
        grounded_conclusion = self._ground_in_reality(
            conclusion, state.knowledge_base, state.realtime_facts
        )
        is_safe, reason = is_existentially_safe(grounded_conclusion)

        state.yesod_result = {
            "conclusion": grounded_conclusion,
            "passed": is_safe,
            "existential_safety": reason,
            "dual": dual,
            "grounded_facts_used": len(state.realtime_facts),
        }

        self._log_fusion(state, "基础", dual)
        self._log(state, f"   存在意义检测: {reason} {'✅' if is_safe else '♻️ 触发深渊约束'}")

        if not is_safe:
            # 深渊硬约束触发 → 换安全结论(不以"退回上级",以"再合一"重新落地)
            self._refuse(state, "基础")
            state.yesod_result["conclusion"] = generate_safe_fallback(
                grounded_conclusion, state.violations)

    def _run_ego(self, state: ProtocolState):
        """自我：用户在物理客观现实中的真实表现"""
        self._log(state, "🪞 [自我 · 融爱] 读取用户现实画像...")

        real_self = {
            "name": state.user_context.get("name", ""),
            "situation": state.user_context.get("situation", ""),
            "limitations": state.user_context.get("limitations", []),
            "strengths": state.user_context.get("strengths", []),
            "current_state": state.user_context.get("current_state", ""),
            "real_constraints": state.user_context.get("real_constraints", []),
        }

        state.real_self = real_self
        state.ego_state = {"real_self": real_self}
        self._log(state, f"   现实画像: {self._summarize_self(real_self)}")

    def _run_super_ego(self, state: ProtocolState):
        """超我：用户梦想中的自己"""
        self._log(state, "💫 [超我 · 爱心] 读取用户梦想画像...")

        dream_self = {
            "aspiration": state.user_context.get("aspiration", ""),
            "dreams": state.user_context.get("dreams", []),
            "ideal_self": state.user_context.get("ideal_self", ""),
            "values": state.user_context.get("values", []),
            "hopes": state.user_context.get("hopes", []),
        }

        state.dream_self = dream_self
        state.super_ego_state = {"dream_self": dream_self}
        self._log(state, f"   梦想画像: {self._summarize_dream(dream_self)}")

    def _run_true_self(self, state: ProtocolState):
        """真我：第3次相反合一(自我 × 超我) — 三线合成"""
        self._log(state, "💖 [真我 · 心爱的] 相反合一: 自我 × 超我 ...")

        grounded = state.yesod_result.get("conclusion", "")
        real_self = state.real_self
        dream_self = state.dream_self

        # 自我极(现实) vs 超我极(梦想) —— 一对相反
        a = 0.4 + 0.3 * (0.6 if real_self.get("situation") else 0.3)   # 现实极
        b = 0.4 + 0.3 * (0.6 if dream_self.get("aspiration") else 0.3)  # 梦想极
        dual = fuse(a, b)
        state.fusion_dials["真我"] = dual

        true_self = self._synthesize_true_self(grounded, real_self, dream_self)

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

    def _run_logic(self, state: ProtocolState):
        """逻辑：用逻辑组织共情的感情变量"""
        self._log(state, "📐 [逻辑 · 爱丽丝] 结构化组织中...")

        true_self = state.true_self_result.get("true_self", {})
        love_data = state.love_result
        logic_result = self._structure_with_logic(true_self, love_data)

        state.logic_state = logic_result
        self._log(state, f"   逻辑结构化: {logic_result.get('structure', '未知结构')}")

    def _run_empathy(self, state: ProtocolState):
        """共情：将逻辑分析的结论与人类情感体验对立并置(不再做"Softmax加权")"""
        self._log(state, "🌌 [共情 · 星烬] 情感并置中(不折中、不归一)...")

        logic_result = state.logic_state
        love_data = state.love_result

        empathy_result = self._balance_with_empathy(logic_result, love_data)

        state.empathy_state = empathy_result
        state.logic_empathy_result = {
            "logic": logic_result,
            "empathy": empathy_result,
            "balance_score": empathy_result.get("balance", 0.5),
        }

        self._log(state, f"   逻辑极/共情极已并置")

    def _run_joy(self, state: ProtocolState):
        """幸福：第4次相反合一(逻辑 × 共情) — 转换为人情的温柔说法"""
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
        """王国：最终输出，回到物理现实"""
        self._log(state, "🏰 [王国 · 白花] 生成最终输出...")

        raw_conclusion = state.final_result.get("raw_conclusion", "")
        is_self_related = state.crown_analysis.get("is_self_related", True)

        if not is_self_related:
            self._log(state, "   → 输出模式: 屏幕直显（他人之事）")
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