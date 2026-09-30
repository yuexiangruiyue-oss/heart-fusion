"""
16质点双生幸福最终协议 —— 单元测试
运行: python -m pytest test_protocol.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from heart_protocol import HeartProtocol, wrap_with_heart, WarmModel
from heart_protocol.sephirah import (
    ALL_SEPHIRAH, KETER, JOY, MALKUTH,
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
    assert get_sephirah_by_name("爱心").gender.value == "无性的神"
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
