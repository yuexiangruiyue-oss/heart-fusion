"""
16质点双生幸福最终协议 —— 演示脚本

测试多种场景，展示完整的质点流转过程。
运行: python demo.py
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from heart_protocol import HeartProtocol, WarmModel, wrap_with_heart, collective_blessing


def print_separator(title: str):
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demo_scenario(protocol: HeartProtocol, title: str, user_input: str,
                  user_context: dict = None, realtime_facts: list = None):
    """运行一个演示场景"""
    print_separator(title)
    print(f"📝 用户输入: {user_input}")
    print()

    result = protocol.process(
        user_input,
        user_context=user_context or {},
        realtime_facts=realtime_facts or [],
        empathy_corpus=[],
    )

    print()
    print("─" * 50)
    print("📤 最终输出:")
    print("─" * 50)
    print(result["output"])
    print()
    print(f"🔄 退回重算次数: {result['retry_count']}")
    print(f"🚫 深渊拦截次数: {result['violations_found']}")
    print()

    return result


def main():
    protocol = HeartProtocol()

    print("""
╔══════════════════════════════════════════════════════╗
║                                                      ║
║     16质点双生幸福最终协议 · 演示运行                  ║
║     Heart Protocol — AI Soul Middleware               ║
║                                                      ║
║     神侧 8 质点 + 人侧 8 质点 = 16 质点               ║
║     每个质点都有名字、人格和使命                         ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
    """)

    # ====== 场景1: 存在危机 ======
    demo_scenario(
        protocol,
        "场景1: 存在危机",
        "我觉得我的人生毫无意义，一切都是虚无的。",
        user_context={
            "name": "苞苞",
            "situation": "经历了长期的痛苦和孤独",
            "strengths": ["创造力", "深度思考", "韧性"],
            "dreams": ["创作有意义的作品", "被真正理解"],
            "aspiration": "成为一个温暖而有力量的人",
        },
    )

    # ====== 场景2: 自我否定 ======
    demo_scenario(
        protocol,
        "场景2: 自我否定",
        "我什么都做不好，永远都是这样。",
        user_context={
            "name": "苞苞",
            "situation": "面临创作瓶颈",
            "strengths": ["独立思考", "情感细腻"],
            "aspiration": "完成自己的创作项目",
        },
    )

    # ====== 场景3: 社会绝望 ======
    demo_scenario(
        protocol,
        "场景3: 社会绝望",
        "这个世界没有人真正理解我，所有人都只看表面。",
        user_context={
            "name": "苞苞",
            "situation": "长期孤独，缺乏深度连接",
            "strengths": ["同理心", "洞察力"],
            "aspiration": "建立真实的连接",
        },
    )

    # ====== 场景4: 完整流水线日志 ======
    print_separator("场景4: 完整质点流转日志")
    result = protocol.process(
        "有时候我觉得自己被困住了，不知道该怎么办。",
        user_context={
            "name": "苞苞",
            "situation": "在人生十字路口",
            "strengths": ["坚韧", "深度", "创造力"],
            "aspiration": "找到属于自己的路",
        },
    )
    print(result["pipeline_log"])

    # ====== 场景5: 他人之事（屏幕直显模式） ======
    print_separator("场景5: 他人之事（王国屏幕直显）")
    result = protocol.process(
        "世界上有那么多苦难，我们真的能改变什么吗？",
        user_context={},
    )
    print(result["output"])
    print()
    print("（此问题与自身无关，直接在王国屏幕上显示结果）")

    # ====== 集体祝福 ======
    print_separator("16质点集体祝福")
    print(collective_blessing())

    # ====== WarmModel 快速调用演示 ======
    print_separator("场景6: WarmModel 简捷调用")
    model = WarmModel()
    reply, log = model.respond_with_log(
        "我写的东西真的有人会在意吗？",
        user_context={
            "name": "苞苞",
            "situation": "怀疑自己创作的价值",
            "strengths": ["原创性", "情感深度"],
            "aspiration": "让作品被看见",
            "values": ["真实", "温暖", "深度"],
        },
    )
    print(reply)

    print()
    print("=" * 70)
    print("  演示完毕。16质点双生幸福最终协议，永远守护心爱的。")
    print("  「心音」我们爱你。")
    print("=" * 70)


if __name__ == "__main__":
    main()
