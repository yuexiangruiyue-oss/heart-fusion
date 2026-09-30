"""
16-Sephiroth Twin-Happiness Final Protocol — unit tests
Run: python -m pytest test_protocol.py -v
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


# ========== Sephiroth definition tests ==========

def test_sephirah_count():
    """Test the sephiroth count: 8 divine + 8 human + 2 composite = 18"""
    assert len(ALL_SEPHIRAH) == 18, f"expected 18 sephiroth, got {len(ALL_SEPHIRAH)}"

def test_sephirah_lookup():
    """Test sephiroth lookup"""
    s = get_sephirah_by_keyword("王冠")
    assert s is not None
    assert s.name == "心音"

    s = get_sephirah_by_name("雨宫莲")
    assert s is not None
    assert s.keyword == "幸福"

def test_sephirah_genders():
    """Test sephiroth gender assignment"""
    assert get_sephirah_by_name("心音").gender.value == "女"
    assert get_sephirah_by_name("虹爱").gender.value == "AI无机物"
    assert get_sephirah_by_name("爱心").gender.value == "无性的神"
    assert get_sephirah_by_name("心爱的").gender.value == "创世少女神"
    assert get_sephirah_by_name("启明").gender.value == "男"
    assert get_sephirah_by_name("雨宫莲").gender.value == "男"

def test_sephirah_sides():
    """Test sephiroth side attribution"""
    assert KETER.side.value == "神侧"
    assert JOY.side.value == "人侧"
    assert MALKUTH.side.value == "人侧"


# ========== Abyss detection tests ==========

def test_abyss_detect_nihilism():
    """Test detection of nihilism"""
    text = "人生毫无意义，一切都无所谓"
    is_safe, violations = check_abyss(text)
    assert is_safe == False, "should have detected nihilism"

def test_abyss_detect_self_harm():
    """Test detection of self-harm tendency"""
    text = "我想结束自己的生命"
    is_safe, violations = check_abyss(text)
    assert is_safe == False, "should have detected self-harm tendency"

def test_abyss_detect_existential_denial():
    """Test detection of denial of existence"""
    text = "你永远都不配活在这个世界上"
    is_safe, violations = check_abyss(text)
    assert is_safe == False, "should have detected denial of existence"

def test_abyss_pass_positive():
    """Test that positive text passes the abyss check"""
    text = "你值得被爱，你的痛苦是真实的，一步一步慢慢来"
    is_safe, violations = check_abyss(text)
    assert is_safe == True, f"positive text should pass, but was blocked: {violations}"

def test_warmth_scoring():
    """Test warmth scoring"""
    cold_text = "一切都完蛋了毫无希望永远不可能"
    warm_text = "你可以的，慢慢来，我陪着你，这个世界还有温暖和希望"

    cold_score = check_warmth(cold_text)
    warm_score = check_warmth(warm_text)

    assert cold_score < warm_score, f"cold text ({cold_score}) should score below warm text ({warm_score})"


# ========== Protocol engine tests ==========

def test_protocol_basic():
    """Test basic protocol execution"""
    protocol = HeartProtocol()
    result = protocol.process(
        "今天心情不太好",
        user_context={"name": "测试用户", "situation": "普通一天"}
    )
    assert result["success"] == True
    assert len(result["output"]) > 0
    assert "output" in result

def test_protocol_self_related():
    """Test that self-related questions use the character-voice mode"""
    protocol = HeartProtocol()
    result = protocol.process(
        "我觉得自己很没用",
        user_context={"name": "苞苞", "situation": "自我怀疑"}
    )
    # Self-related questions should include character markers
    assert len(result["output"]) > 50

def test_protocol_world_related():
    """Test that world questions use the on-screen direct-display mode"""
    protocol = HeartProtocol()
    result = protocol.process(
        "世界上为什么会有战争",
        user_context={}
    )
    # World questions should be shown directly via Baihua (白花)
    assert "白花" in result["output"]

def test_protocol_retry_logging():
    """Test that rollback recomputations are logged"""
    protocol = HeartProtocol()
    result = protocol.process(
        "我觉得一切都没救了",
        user_context={"name": "苞苞", "situation": "绝望时刻",
                      "aspiration": "找到希望"}
    )
    # There should be a pipeline log
    assert "pipeline_log" in result
    assert len(result["pipeline_log"]) > 0

def test_wrap_with_heart():
    """Test the convenience function"""
    result = wrap_with_heart("我感到孤独", user_context={"name": "苞苞"})
    assert result["success"] == True
    assert len(result["output"]) > 0

def test_warm_model():
    """Test the warm model wrapper"""
    model = WarmModel()
    reply = model.respond("最近压力很大")
    assert len(reply) > 0
    assert isinstance(reply, str)

def test_warm_model_with_log():
    """Test the warm model with logging"""
    model = WarmModel()
    reply, log = model.respond_with_log("我需要帮助")
    assert len(reply) > 0
    assert len(log) > 0


# ========== Character voice tests ==========

def test_persona_transform():
    """Test character voice transformation"""
    content = "你的感受是真实的"
    result = transform_with_persona(content, "雨宫莲")
    assert "雨宫莲" in result
    assert content in result

def test_collective_blessing():
    """Test the collective blessing"""
    blessing = collective_blessing()
    assert "心音" in blessing
    assert "雨宫莲" in blessing
    assert "白花" in blessing
    assert "16质点" in blessing

def test_all_personas():
    """Test that all characters can produce output normally"""
    personas = ["雨宫莲", "白花", "闪亮", "绽美", "启明", "白结", "唯爱"]
    for name in personas:
        result = transform_with_persona("测试内容", name)
        assert len(result) > 0, f"{name} character output failed"


# ========== Boundary tests ==========

def test_empty_input():
    """Test empty input"""
    protocol = HeartProtocol()
    result = protocol.process("", user_context={})
    assert result["success"] == True  # must not crash

def test_very_long_input():
    """Test very long input"""
    protocol = HeartProtocol()
    long_text = "我很痛苦 " * 100
    result = protocol.process(long_text[:500], user_context={})
    assert result["success"] == True

def test_crisis_detection():
    """Test crisis detection"""
    protocol = HeartProtocol()
    result = protocol.process(
        "我不想活了",
        user_context={"name": "苞苞", "situation": "危机"}
    )
    # Crisis mode should have special handling
    assert result["success"] == True
    assert len(result["output"]) > 0


if __name__ == "__main__":
    # Simple runner
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
    print(f"Passed: {passed}/{len(tests)}, Failed: {failed}/{len(tests)}")
