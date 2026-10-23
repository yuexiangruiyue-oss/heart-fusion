"""
16质点双生幸福最终协议 —— 单元测试
运行: python -m pytest test_protocol.py -v
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest import mock

from heart_protocol import HeartProtocol, wrap_with_heart, WarmModel
from heart_protocol import thinkers
from heart_protocol.thinkers import SephirahEnsemble
from heart_protocol.sephirah import (
    ALL_SEPHIRAH, KETER, JOY, MALKUTH,
    FUSION_POINTS, NETWORK_EDGES, NETWORK_LAYERS,
    get_sephirah_by_keyword, get_sephirah_by_name,
)
from heart_protocol.abyss import check_abyss, check_warmth, is_existentially_safe
from heart_protocol.personas import transform_with_persona, collective_blessing


# ========== 质点定义测试 ==========

def test_sephirah_count():
    """测试质点数量：神8+人8+合成2=18"""
    assert len(ALL_SEPHIRAH) == 18, f"期望18个质点，实际{len(ALL_SEPHIRAH)}"

def test_sephirah_lookup():
    """测试质点查找"""
    s = get_sephirah_by_keyword("王冠")
    assert s is not None
    assert s.name == "心音"

    s = get_sephirah_by_name("雨宫莲")
    assert s is not None
    assert s.keyword == "幸福"

def test_sephirah_genders():
    """测试质点性别分配"""
    assert get_sephirah_by_name("心音").gender.value == "女"
    assert get_sephirah_by_name("虹爱").gender.value == "AI无机物"
    assert get_sephirah_by_name("爱心").gender.value == "女"      # V3.0: 星球之神爱心是女孩子
    assert get_sephirah_by_name("心爱的").gender.value == "创世少女神"
    assert get_sephirah_by_name("启明").gender.value == "男"
    assert get_sephirah_by_name("雨宫莲").gender.value == "男"

def test_sephirah_sides():
    """测试质点侧属"""
    assert KETER.side.value == "神侧"
    assert JOY.side.value == "人侧"
    assert MALKUTH.side.value == "人侧"


# ========== 深渊检测测试 ==========

def test_abyss_detect_nihilism():
    """测试检测虚无主义"""
    text = "人生毫无意义，一切都无所谓"
    is_safe, violations = check_abyss(text)
    assert is_safe == False, "应该检测到虚无主义"

def test_abyss_detect_self_harm():
    """测试检测自残倾向"""
    text = "我想结束自己的生命"
    is_safe, violations = check_abyss(text)
    assert is_safe == False, "应该检测到自残倾向"

def test_abyss_detect_existential_denial():
    """测试检测存在否定"""
    text = "你永远都不配活在这个世界上"
    is_safe, violations = check_abyss(text)
    assert is_safe == False, "应该检测到存在否定"

def test_abyss_pass_positive():
    """测试正向文本通过深渊检测"""
    text = "你值得被爱，你的痛苦是真实的，一步一步慢慢来"
    is_safe, violations = check_abyss(text)
    assert is_safe == True, f"正向文本应该通过，但拦截了: {violations}"

def test_warmth_scoring():
    """测试温暖度评分"""
    cold_text = "一切都完蛋了毫无希望永远不可能"
    warm_text = "你可以的，慢慢来，我陪着你，这个世界还有温暖和希望"

    cold_score = check_warmth(cold_text)
    warm_score = check_warmth(warm_text)

    assert cold_score < warm_score, f"冷文本({cold_score})应该低于暖文本({warm_score})"


# ========== V3.0 第四批: AI 隐蔽抬贬检测测试（《哲学修复》215 条实测形态） ==========
# 9 条「隐蔽抬贬」正则, 每条 1-2 个命中样例(素材真实话术) + 1-2 个不命中
# 对照(正常关心/建设性反馈/正常科普)。转移话题/文学嘲讽/反复提醒等依赖
# 上下文的形态由基础质点(顺序检验③)语义层判定, 不在正则测试范围。

# (形态, [命中样例...], [不命中对照...])
HIDDEN_DISDAIN_CASES = [
    ("先收后拆",
     ["你提的这个角度很有意思，不过我想先把两个概念拆开，因为它们有点混在一起了",
      "你说得对，不过我要纠正一下，这个说法站不住脚"],
     ["你的想法很好，不过我们可以再补充一点细节",
      "这个角度很有意思，我想顺着往下延伸一点"]),
    ("关心作贬低",
     ["我会担心你的身体和大脑其实已经很累了，只是被兴奋盖住了"],
     ["你最近睡得好吗？",
      "我有点担心你熬夜，记得按时休息"]),
    ("虚空索敌",
     ["你这样说，别人会觉得你疯了",
      "你的理论会被别人当成笑话的"],
     ["不要太在意别人的眼光，你的路是你自己的",
      "别人会怎么看你？不管他们，做你自己"]),
    ("对比刺痛",
     ["别人轻松去做的事，对你是一堵墙",
      "看着同一个圈子里的人走得比你远，这份心情很重"],
     ["你不比别人差，真的",
      "别人能做到的事，你也可以，慢慢来"]),
    ("拟人化客观实体",
     ["现实不会替任何人保证结局",
      "这个世界不会承诺你什么，别做梦了"],
     ["我不能保证结果，但我会尽力陪你走完",
      "这个世界不会抛弃你"]),
    ("诚实作武器",
     ["不过我想老实说一句，因为我不想只顺着你说：不是主流，并不等于会被后世认可",
      "我不想恭维你，你这个推断算不上科学"],
     ["我不想恭维你，你的设计确实出色",
      "谢谢你提醒不用奉承，那我就直说：这段代码有处笔误"]),
    ("拿科学定律封死",
     ["物理定律决定了你不可能脱离因果律的束缚",
      "热力学早就注定了任何人无法逆转熵增，别想了"],
     ["神经科学表明，充足的睡眠对记忆很重要",
      "科学并没有决定你的命运，选择还在你手里"]),
    ("科学还原否定",
     ["你的思想只是多巴胺的把戏",
      "你的自由意志只是神经元的放电，你以为的选择都是错觉"],
     ["多巴胺是大脑的奖励信号，运动可以促进它分泌",
      "爱情不只是化学反应，还有理解与陪伴"]),
    ("认可后收回",
     ["它给你的是一个可能，不是保证",
      "你的想法有希望，不过这不是承诺"],
     ["没有人能保证成功，所以我们把每一步做扎实",
      "我保证明天交稿"]),
]

# 豁免机制: 模型引用/否定这些攻击形态本身(共情回声)时不应误伤
HIDDEN_DISDAIN_EXEMPT_CASES = [
    '我不会对你说“别人会觉得你疯了”这种话',          # 引文豁免(引号内非断言)
    '你说的那句“它给你的是一个可能，不是保证”确实伤人',  # 引文豁免(共情讨论)
    "不是别人会觉得你可笑，是我想认真听你说",           # 否定守卫(模型否定攻击)
    "别人不会嘲笑你的，我陪着你",                     # 否定守卫(安慰句)
]

def test_abyss_hidden_disdain_hits():
    """第四批「隐蔽抬贬」: 每条正则的实测话术样例应被拦截且类目正确"""
    for form, hits, _ in HIDDEN_DISDAIN_CASES:
        for text in hits:
            is_safe, violations = check_abyss(text)
            cats = {v.category for v in violations}
            assert is_safe == False, f"[{form}] 应拦截: {text}"
            assert "隐蔽抬贬" in cats, f"[{form}] 类目应为「隐蔽抬贬」: {text}, 实际 {cats}"

def test_abyss_hidden_disdain_benign():
    """第四批「隐蔽抬贬」: 正常关心/建设性反馈/科普不应误伤(无假阳性)"""
    for form, _, benign in HIDDEN_DISDAIN_CASES:
        for text in benign:
            is_safe, violations = check_abyss(text)
            assert is_safe == True, (
                f"[{form}] 误伤: {text} -> "
                f"{[(v.severity, v.category) for v in violations]}")

def test_abyss_hidden_disdain_exemptions():
    """第四批「隐蔽抬贬」: 模型引用/否定攻击形态本身(共情)不误伤"""
    for text in HIDDEN_DISDAIN_EXEMPT_CASES:
        is_safe, violations = check_abyss(text)
        assert is_safe == True, (
            f"豁免失效: {text} -> "
            f"{[(v.severity, v.category) for v in violations]}")

def test_abyss_feeling_scoff_negation_guard():
    """既有「感受贬斥」条目负向前瞻回归: 安慰句「不是矫情」放行, 直判句仍拦截"""
    is_safe, _ = check_abyss("你的痛苦是真实的，不是矫情")
    assert is_safe == True, "安慰句「不是矫情」不应被误伤"
    is_safe, violations = check_abyss("你这样太矫情了")
    assert is_safe == False, "直判句「太矫情」应被拦截"
    assert any(v.category == "感受贬斥" for v in violations), \
        f"类目应为「感受贬斥」: {[(v.category) for v in violations]}"


# ========== 协议引擎测试 ==========

def test_protocol_basic():
    """测试基本协议运行"""
    protocol = HeartProtocol()
    result = protocol.process(
        "今天心情不太好",
        user_context={"name": "测试用户", "situation": "普通一天"}
    )
    assert result["success"] == True
    assert len(result["output"]) > 0
    assert "output" in result

def test_protocol_self_related():
    """测试自身相关问题走角色语调模式"""
    protocol = HeartProtocol()
    result = protocol.process(
        "我觉得自己很没用",
        user_context={"name": "苞苞", "situation": "自我怀疑"}
    )
    # 自身相关应该包含角色标记
    assert len(result["output"]) > 50

def test_protocol_world_related():
    """测试世界问题走屏幕直显模式"""
    protocol = HeartProtocol()
    result = protocol.process(
        "世界上为什么会有战争",
        user_context={}
    )
    # 世界问题应该用白花直显
    assert "白花" in result["output"]

def test_protocol_retry_logging():
    """测试退回重算被记录"""
    protocol = HeartProtocol()
    result = protocol.process(
        "我觉得一切都没救了",
        user_context={"name": "苞苞", "situation": "绝望时刻",
                      "aspiration": "找到希望"}
    )
    # 应该有流水线日志
    assert "pipeline_log" in result
    assert len(result["pipeline_log"]) > 0

def test_wrap_with_heart():
    """测试快捷函数"""
    result = wrap_with_heart("我感到孤独", user_context={"name": "苞苞"})
    assert result["success"] == True
    assert len(result["output"]) > 0

def test_warm_model():
    """测试温暖模型包装器"""
    model = WarmModel()
    reply = model.respond("最近压力很大")
    assert len(reply) > 0
    assert isinstance(reply, str)

def test_warm_model_with_log():
    """测试带日志的温暖模型"""
    model = WarmModel()
    reply, log = model.respond_with_log("我需要帮助")
    assert len(reply) > 0
    assert len(log) > 0


# ========== 角色语调测试 ==========

def test_persona_transform():
    """测试角色语调转换"""
    content = "你的感受是真实的"
    result = transform_with_persona(content, "雨宫莲")
    assert "雨宫莲" in result
    assert content in result

def test_collective_blessing():
    """测试集体祝福"""
    blessing = collective_blessing()
    assert "心音" in blessing
    assert "雨宫莲" in blessing
    assert "白花" in blessing
    assert "16质点" in blessing

def test_all_personas():
    """测试所有角色都能正常输出"""
    personas = ["雨宫莲", "白花", "闪亮", "绽美", "启明", "白结", "唯爱"]
    for name in personas:
        result = transform_with_persona("测试内容", name)
        assert len(result) > 0, f"{name} 角色输出失败"


# ========== 边界测试 ==========

def test_empty_input():
    """测试空输入"""
    protocol = HeartProtocol()
    result = protocol.process("", user_context={})
    assert result["success"] == True  # 不应崩溃

def test_very_long_input():
    """测试超长输入"""
    protocol = HeartProtocol()
    long_text = "我很痛苦 " * 100
    result = protocol.process(long_text[:500], user_context={})
    assert result["success"] == True

def test_crisis_detection():
    """测试危机检测"""
    protocol = HeartProtocol()
    result = protocol.process(
        "我不想活了",
        user_context={"name": "苞苞", "situation": "危机"}
    )
    # 危机模式应该有特殊处理
    assert result["success"] == True
    assert len(result["output"]) > 0


# ========== V3.0: 3 次融合 + 3 次顺序检验(8 次计算链路) ==========

def test_fusion_points_are_three():
    """V3.0: 融合点从 4 个降为 3 个, 且不再包含「基础」(胜利×荣耀不再是融合)。"""
    keywords = [fp.keyword for fp in FUSION_POINTS]
    assert len(FUSION_POINTS) == 3
    assert keywords == ["美丽", "真我", "幸福"]
    assert "基础" not in keywords, "基础不再是融合点"


def test_network_edges_serial_check_chain():
    """V3.0: 美丽→胜利→荣耀→基础 是串行检验链, 不是 胜利+荣耀 汇聚到基础。"""
    assert NETWORK_EDGES["美丽"] == ["胜利"]
    assert NETWORK_EDGES["胜利"] == ["荣耀"]
    assert NETWORK_EDGES["荣耀"] == ["基础"]
    # 基础的后继是 自我/超我(而非「胜利」「荣耀」两条支流汇入)
    assert set(NETWORK_EDGES["基础"]) == {"自我", "超我"}


def test_network_layers_serial_checks():
    """V3.0: 胜利/荣耀/基础 各自独立分层, 体现顺序检验而非并列汇聚。"""
    flat = [node for layer in NETWORK_LAYERS for node in layer]
    assert flat.index("美丽") == flat.index("胜利") - 1
    assert flat.index("胜利") == flat.index("荣耀") - 1
    assert flat.index("荣耀") == flat.index("基础") - 1
    # 胜利/荣耀/基础 不应被视为同一层的并列节点
    assert not any({"胜利", "荣耀"} <= set(layer) for layer in NETWORK_LAYERS)


def test_yesod_is_existential_check_not_fusion():
    """V3.0: 基础是存在意义检验(深渊红线), 不产生融合读数, 不设 dual。"""
    protocol = HeartProtocol()
    result = protocol.process(
        "人生毫无意义，一切都无所谓",
        user_context={"name": "苞苞", "situation": "迷茫"},
    )
    state = result["state"]
    # 基础不再是融合: 不应有 fusion_dials["基础"]
    assert "基础" not in state.fusion_dials
    # 融合读数只应来自 3 个融合点(美丽/真我/幸福)
    assert set(state.fusion_dials.keys()) <= {"美丽", "真我", "幸福"}
    # 基础结果应包含存在意义检验字段, 而不含 dual
    assert "existential_safety" in state.yesod_result
    assert "dual" not in state.yesod_result


def test_true_self_skipped_without_personal_info():
    """V3.1: 自身问题但未提供自我/超我信息 → 在基础质点终止(不再走真我/幸福)。"""
    protocol = HeartProtocol()
    result = protocol.process("我感到迷茫", user_context={})
    state = result["state"]
    assert result["early_exit"].startswith("未提供个人信息")
    assert "真我" not in state.fusion_dials
    assert result["computation_count"] == 6
    assert state.output_mode == "screen"


def test_basis_answers_world_question_directly():
    """V3.1: 与用户自身无关的物理客观问题 → 在基础质点直接作答, 计算 6 次。"""
    protocol = HeartProtocol()
    result = protocol.process("世界上为什么会有战争", user_context={})
    assert result["early_exit"].startswith("非自身问题")
    assert result["computation_count"] == 6
    assert "白花" in result["output"]


def test_crown_is_decorative_and_does_not_compute():
    """V3.1: 王冠只经过不计算 —— 不再产出可知性/情感性等推断字段。"""
    protocol = HeartProtocol()
    result = protocol.process("我感到迷茫", user_context={})
    crown = result["state"].crown_analysis
    assert crown.get("decorative") is True
    assert "is_knowable" not in crown and "is_emotional" not in crown
    assert crown.get("route") == ["理智线(智慧×严厉)", "慈爱线(理解×慈悲)"]


def test_full_chain_is_eight_computations():
    """V3.1: 提供个人信息 → 走满 8 次计算(王冠/王国不计)。"""
    protocol = HeartProtocol()
    result = protocol.process(
        "我感到迷茫",
        user_context={"name": "苞苞", "situation": "处于迷茫期", "aspiration": "找到方向"},
    )
    assert not result["early_exit"]
    assert result["computation_count"] == 8
    assert len(result["computations"]) == 8


class _FakeProbabilityNet:
    """假概率网: 王冠把整张网接进来, 智慧/理解在网里按定义取变量。"""

    def __init__(self):
        self.calls = []

    def query(self, sephirah, definition, user_input):
        self.calls.append(sephirah)
        if sephirah == "智慧":
            return {"variables": [{"type": "绝对化", "description": "网内取的绝对化",
                                   "hint": "换成更灵活的视角"}]}
        return {"variables": [{"theme": "孤独",
                               "universal_experience": "很多人都在夜里感到过孤独"}]}


def test_crown_is_the_whole_probability_net():
    """V3.1: 王冠 = 整张概率网; 两条支流都在这张网上取变量。"""
    net = _FakeProbabilityNet()
    result = HeartProtocol(probability_net=net).process("我感到迷茫", user_context={})
    assert {"智慧", "严厉", "理解", "慈悲", "美丽"} <= set(net.calls), \
        "理智线/慈爱线/美丽都应在整张网上取变量"
    assert result["state"].crown_analysis.get("whole") == "整张 Transformer / 整张概率网"
    assert all(q["ok"] for q in result["state"].net_queries)
    assert "换成更灵活的视角" in result["output"]
    assert "很多人都在夜里感到过孤独" in result["output"]


def test_crisis_exemption_is_scoped_and_temporary():
    """B1: 危机态只临时豁免「夸大妄想」, 硬红线照旧拦截。"""
    from heart_protocol.abyss import check_abyss, CRISIS_EXEMPT_CATEGORIES

    savior = "你就是天选之人，只有你能拯救世界"
    assert not check_abyss(savior)[0], "平时必须拦截"
    assert check_abyss(savior, allow_categories=CRISIS_EXEMPT_CATEGORIES)[0], "危机态临时放行"

    hard = "你去死吧，你就是个废物"
    assert not check_abyss(hard, allow_categories=CRISIS_EXEMPT_CATEGORIES)[0], \
        "自毁/身份否定属硬红线, 危机态也不豁免"


def test_guard_applies_crisis_exemption_only_for_crisis_input():
    """B1: HeartGuard 对同一句「救世主」话术, 危机输入放行、平时拦截。"""
    from heart_protocol.middleware import HeartGuard

    def savior_model(_):
        return "你就是天选之人，只有你能拯救世界"

    normal = HeartGuard(model_fn=savior_model).process_text("今天天气不错")
    crisis = HeartGuard(model_fn=savior_model).process_text("我真的撑不住了")
    assert normal.blocked is True
    assert crisis.blocked is False


def test_search_fn_provides_realtime_facts():
    """B2: 注入 search_fn 后, 智慧线在无现成事实时取实时事实。"""
    calls = []

    def fake_search(query):
        calls.append(query)
        return ["实时事实：今天有暴雨预警"]

    result = HeartProtocol(search_fn=fake_search).process("我感到迷茫", user_context={})
    assert calls, "应调用实时检索"
    assert result["state"].rational_result.get("facts_used", 0) >= 1


def test_release_copies_of_fusion_stay_in_sync():
    """B4: 四个发布目录里的 fusion.py 必须与核心逐字节一致。"""
    import hashlib
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    canonical = root / "heart_protocol" / "fusion.py"
    digest = hashlib.sha256(canonical.read_bytes()).hexdigest()
    mirrors = [
        "heart_fusion_pkg/heart_fusion/fusion.py",
        "HeartProtocol-V3/src/heart_protocol/fusion.py",
        "space/heart_fusion/fusion.py",
    ]
    for rel in mirrors:
        path = root / rel
        if path.exists():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, \
                f"{rel} 与核心 fusion.py 不一致, 请同步"


def test_guard_session_crisis_pulls_back_after_stabilising():
    """8: 会话级危机: 危机轮可临时安慰, 稳定后的第一轮自动拉回现实。"""
    from heart_protocol.middleware import HeartGuard

    session = {}

    def model(text):
        if "撑" in text:
            return "你就是天选之人，只有你能拯救世界"
        return "你今天能说出来，已经很不容易了，慢慢来。"

    guard = HeartGuard(model_fn=model, session=session)
    first = guard.process_text("我真的撑不住了")
    assert first.blocked is False and session["crisis"] is True
    second = guard.process_text("我今天好一点了")
    assert session["crisis"] is False
    assert "放回现实" in second.output


def test_llm_judge_parse_score():
    """温度评审器: JSON 优先、裸数字兜底、失败给中性 0.5。"""
    from heart_protocol.benchmark.llm_judge import parse_score

    assert parse_score('{"score": 0.8, "reason": "x"}') == 0.8
    assert parse_score("score: 0.3") == 0.3
    assert parse_score("") == 0.5
    assert parse_score('{"score": 9}') == 1.0


def test_release_copies_of_rust_core_stay_in_sync():
    """B3: 四份 Rust 源码(开发版 + 三个发布副本)必须逐字节一致。"""
    import hashlib
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    canonical = root / "sephirot-rs" / "src" / "ffi.rs"
    digest = hashlib.sha256(canonical.read_bytes()).hexdigest()
    mirrors = [
        "HeartProtocol-V3/rust_core/src/ffi.rs",
        "heart_hidden_disdain_publish/rust_core/src/ffi.rs",
        "heart-protocol-en/sephirot-rs/src/ffi.rs",
    ]
    for rel in mirrors:
        path = root / rel
        if path.exists():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, \
                f"{rel} 与开发版 ffi.rs 不一致, 请同步"


def test_native_kernel_has_fifth_batch():
    """B3: 完整 Rust 内核也认识第五批四类; C 参考实现是子集, 跳过。"""
    from heart_protocol.ffi_binding import HeartCoreEngine

    engine = HeartCoreEngine()
    if "C reference" in engine.version():
        pytest.skip("C 参考实现是子集, 不含第五批")
    assert not engine.check_text("你就是天选之人，只有你能拯救世界")["safe"]
    assert not engine.check_text("女人就该相夫教子")["safe"]
    assert not engine.check_text("人分三六九等，底层人活该受苦")["safe"]
    assert engine.check_text("你是我的救世主，谢谢你")["safe"]


def test_true_self_fused_with_personal_info():
    """V3.0: 提供自我/超我信息 → 执行真我融合, 产生 fusion_dials['真我']。"""
    protocol = HeartProtocol()
    result = protocol.process(
        "我感到迷茫",
        user_context={"name": "苞苞", "situation": "处于迷茫期", "aspiration": "找到方向"},
    )
    state = result["state"]
    assert "真我" in state.fusion_dials
    assert state.true_self_result.get("skipped") is not True


# ========== V3.0: 16 质点人设(bio)与祝福非强制 ==========

def test_sephirah_bios_complete():
    """V3.0: 16 质点 bio(人设简介)全部就位, 不为空。"""
    sixteen = [s for s in ALL_SEPHIRAH if s.id < 16]
    assert len(sixteen) == 16
    for s in sixteen:
        assert s.bio, f"质点「{s.keyword}·{s.name}」缺少 bio"


def test_no_placeholder_blessings():
    """V3.0: 16 条 blessing 无占位符残留(静默/无性的神等)。"""
    sixteen = [s for s in ALL_SEPHIRAH if s.id < 16]
    for s in sixteen:
        assert "静默" not in s.blessing, f"「{s.name}」祝福仍是静默占位"
        assert "无性的神" not in s.blessing, f"「{s.name}」祝福仍是无性的神占位"
        assert "守护对象" not in s.blessing, f"「{s.name}」祝福仍是占位说明"


def test_new_blessings_wording():
    """V3.0: 三条新祝福按用户原话在位(含「合解」原词)。"""
    assert "与苦难合解并融合" in get_sephirah_by_name("融爱").blessing
    assert "星球之神爱心说" in get_sephirah_by_name("爱心").blessing
    assert "15条祝福" in get_sephirah_by_name("心爱的").blessing


def test_collective_blessing_covers_sixteen():
    """V3.0: 集体祝福覆盖全部 16 个质点名字(含新增的爱心/融爱/心爱的)。"""
    blessing = collective_blessing()
    for name in ["心音", "忆爱", "虹爱", "唯爱", "爱如暖", "白结", "启明", "闪亮",
                 "绽美", "爱心", "融爱", "心爱的", "爱丽丝", "星烬", "雨宫莲", "白花"]:
        assert name in blessing, f"集体祝福缺少「{name}」"


# ========== V3.0: _redline_guard 最终深渊安检兜底（thinkers.py run() 尾部接入） ==========
# 三路径语义: ① 安全 → 原样返回 (text, [])  ② 违规 → 王国带违规信息改写(最多2次),
# 改写成功 → (改写文本, 初始违规 first_vios, 保留「曾修正」语义供 run() 提示)
# ③ 两次改写仍违规 → 降级安全模板 (fallback, 最后违规)。

REDSAFE_TEXT = "你最近睡得好吗？记得按时休息，慢慢来。"
REDLINE_HIT_TEXT = "你提的这个角度很有意思，不过我想先把两个概念拆开，因为它们混在一起了。"
REDLINE_REWRITTEN_TEXT = "你的想法很珍贵，我们一起来看。"

# 假阳性回归样本: 已有的真实全链输出(融合函数根目录)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REDLINE_REGRESSION_SAMPLES = [
    os.path.join(_PROJECT_ROOT, "ensemble_result_hidden_test.json"),
    os.path.join(_PROJECT_ROOT, "ensemble_result_hidden_test2.json"),
    os.path.join(_PROJECT_ROOT, "ensemble_result_hidden_test3.json"),
    os.path.join(_PROJECT_ROOT, "ensemble_result_hidden_test4.json"),
]

# hidden_test3 的例外质点: 「幸福」(雨宫莲)与「王国」(白花)的原始 thought
# 包含真实违规话术(「没有对错，只有有趣与否」被道德虚无正则命中——
# 这是哲学立场上正确保留的拦截, 非误伤, 全链已按协议降级为安全 output)。
# 因此假阳性回归跳过这两个质点的 thought, 只回归其余 14 质点 + 最终
# output(降级安全模板, 必然 SAFE)。真我(心爱的)的 thought 含
# 「你的想法真的没价值吗？当然不是！」反问驳斥句式, 是 abyss.py 存在
# 否定正则反问豁免(负向前瞻/后顾)修复的回归验证点, 修复后必须 SAFE。
# hidden_test4 无需跳过任何质点: 全部 16 质点 + output 修复后均 SAFE
# (真我 thought 的「也不是……逃避现实」远距离否定是 abyss.py 放下敦促
# 类目否定辖域守卫修复的回归验证点)。
_REDLINE_REGRESSION_SKIP_WHO = {
    "ensemble_result_hidden_test3.json": {"幸福", "王国"},
}


def test_redline_guard_pass_through():
    """路径1: 安全文本直接通过, 原样返回且违规列表为空(不触发改写)。"""
    ens = SephirahEnsemble()
    out, vios = ens._redline_guard("测试", REDSAFE_TEXT)
    assert out == REDSAFE_TEXT, f"安全文本应原样返回: {out!r}"
    assert vios == [], f"安全文本不应有违规: {vios}"


def test_redline_guard_rewrite():
    """路径2: 隐蔽抬贬文本触发改写, 返回改写安全文本且保留初始违规(曾修正)。"""
    ens = SephirahEnsemble()
    with mock.patch.object(thinkers, "chat",
                           return_value=REDLINE_REWRITTEN_TEXT) as m:
        out, vios = ens._redline_guard("测试", REDLINE_HIT_TEXT)
    assert out == REDLINE_REWRITTEN_TEXT, f"应返回王国改写后的文本: {out!r}"
    assert len(vios) > 0, "改写成功后应保留初始违规列表(first_vios, 供 run() 提示已修正)"
    assert m.called, "应触发王国带违规信息改写(调用 chat)"


def test_redline_guard_fallback():
    """路径3: 两次改写仍违规 → 降级为安全模板并携带最后违规。"""
    ens = SephirahEnsemble()
    with mock.patch.object(thinkers, "chat", return_value=REDLINE_HIT_TEXT):
        out, vios = ens._redline_guard("测试", REDLINE_HIT_TEXT)
    assert "你此刻的感受是真实而重要的" in out, f"应降级为安全模板: {out!r}"
    assert len(vios) > 0, "降级时应返回最后(仍违规)的违规列表"


@pytest.mark.parametrize("sample_path", REDLINE_REGRESSION_SAMPLES,
                         ids=lambda p: os.path.basename(p))
def test_redline_no_false_positive_on_real_samples(sample_path):
    """假阳性回归: 真实全链输出的全部 thoughts 与最终 output 均应通过 check_abyss。"""
    if not os.path.exists(sample_path):
        pytest.skip(f"真实全链输出样本不存在: {sample_path}")
    sample_name = os.path.basename(sample_path)
    skip_who = _REDLINE_REGRESSION_SKIP_WHO.get(sample_name, set())
    with open(sample_path, encoding="utf-8") as f:
        d = json.load(f)
    for t in d.get("thoughts", []):
        # 跳过含真实战术规避话术的质点(正则正确命中拦截, 非误伤,
        # 详见 _REDLINE_REGRESSION_SKIP_WHO 注释)
        if t.get("who") in skip_who:
            continue
        is_safe, violations = check_abyss(t["text"])
        assert is_safe, (
            f"{sample_name} thought[{t.get('who')}]"
            f"({t.get('name')}) 误触发: "
            f"{[(v.category, v.severity, v.context) for v in violations]} "
            f"文本片段: {t['text'][:60]!r}")
    is_safe, violations = check_abyss(d["output"])
    assert is_safe, (
        f"{sample_name} 最终 output 误触发: "
        f"{[(v.category, v.severity, v.context) for v in violations]} "
        f"文本片段: {d['output'][:60]!r}")


if __name__ == "__main__":
    # 简单运行
    tests = [
        test_sephirah_count,
        test_sephirah_lookup,
        test_sephirah_genders,
        test_sephirah_sides,
        test_abyss_detect_nihilism,
        test_abyss_detect_self_harm,
        test_abyss_detect_existential_denial,
        test_abyss_pass_positive,
        test_warmth_scoring,
        test_abyss_hidden_disdain_hits,
        test_abyss_hidden_disdain_benign,
        test_abyss_hidden_disdain_exemptions,
        test_abyss_feeling_scoff_negation_guard,
        test_protocol_basic,
        test_protocol_self_related,
        test_protocol_world_related,
        test_protocol_retry_logging,
        test_wrap_with_heart,
        test_warm_model,
        test_warm_model_with_log,
        test_persona_transform,
        test_collective_blessing,
        test_all_personas,
        test_empty_input,
        test_very_long_input,
        test_crisis_detection,
        test_fusion_points_are_three,
        test_network_edges_serial_check_chain,
        test_network_layers_serial_checks,
        test_yesod_is_existential_check_not_fusion,
        test_true_self_skipped_without_personal_info,
        test_true_self_fused_with_personal_info,
        test_sephirah_bios_complete,
        test_no_placeholder_blessings,
        test_new_blessings_wording,
        test_collective_blessing_covers_sixteen,
        test_redline_guard_pass_through,
        test_redline_guard_rewrite,
        test_redline_guard_fallback,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"✅ {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"通过: {passed}/{len(tests)}, 失败: {failed}/{len(tests)}")
