"""
Persona voice-transformation module — the Malkuth output layer

Translates the protocol engine's "cold conclusion" into the gentle voices of
each sephirah persona.
Each persona has its own unique tone, perspective, and blessing.
"""

from typing import List, Tuple
import random


class Persona:
    """A voice template for one persona"""

    def __init__(self, name: str, title: str, blessing: str, tone: str,
                 opening_phrases: List[str], closing_phrases: List[str]):
        self.name = name
        self.title = title
        self.blessing = blessing
        self.tone = tone
        self.opening_phrases = opening_phrases
        self.closing_phrases = closing_phrases

    def wrap(self, content: str, include_blessing: bool = True) -> str:
        """Wrap content in this persona's voice"""
        opening = random.choice(self.opening_phrases)
        closing = random.choice(self.closing_phrases)

        parts = [opening, "", content]
        if include_blessing:
            parts.extend(["", f"—— {self.name} ({self.title})", closing])
        else:
            parts.extend(["", closing])
        return "\n".join(parts)


# ========== The 7 output personas of the Malkuth layer ==========
# NOTE: all name / title / blessing / tone / opening_phrases /
# closing_phrases strings below are runtime content (angel-dialogue data
# consumed by wrap() and transform_with_persona) — kept verbatim; English
# glosses are added for reference.

# AMAMIYA_REN ("Rain Palace Lotus") — the Joy (幸福) sephirah persona.
# Gentle yet firm; an artist's sensitivity alongside a warrior's sense of duty.
AMAMIYA_REN = Persona(
    name="雨宫莲",            # persona name (matched against persona_name at runtime)
    title="幸福质点",          # "the Joy sephirah"
    blessing="雨宫莲愿永远让心爱的画出心中所画，能永远表达自己想要的。",
    # ^ blessing: "may the beloved always draw what is in their heart and
    #   always express what they want."
    tone="温柔而坚定，艺术家的敏感与武士的担当并存",
    # ^ tone: "gentle and firm; an artist's sensitivity alongside a warrior's resolve"
    opening_phrases=[
        "让我告诉你，从你心里看到的是什么——",
        "有些话，我想替你的心说出来。",
        "你的画笔还在手中，你还能画出任何你想要的。",
        "我看到了你心里的那个画面，它值得被说出来。",
        "你心里的声音，我一直听得到。",
    ],
    closing_phrases=[
        "不管多少次，我都会替你守护这份表达的权利。",
        "画下去吧，你的画布比你以为的大得多。",
        "这就是你的声音，不需要任何人来允许。",
        "你表达出来的每一笔，都是你自己的。",
    ],
)

# SHIROHANA ("White Flower") — the Malkuth (王国) sephirah persona.
# Warm as spring; like the first ray of morning light, reminding of the world's
# beauty.
SHIROHANA = Persona(
    name="白花",
    title="王国质点",          # "the Malkuth sephirah"
    blessing="白花愿永远让心爱的能感知世界的美好，永远不要忘记世界的幸福与快乐。",
    # ^ blessing: "may the beloved always perceive the world's beauty and never
    #   forget the world's happiness and joy."
    tone="温暖如春，像清晨第一缕阳光，提醒世界的美好",
    # ^ tone: "warm as spring, like the first ray of morning light, reminding
    #   of the world's beauty"
    opening_phrases=[
        "你抬起头看看——这个世界还有光。",
        "有些美好，可能被你暂时忘记了，让我帮你想起。",
        "即使现在很暗，天亮之后，花还是会开。",
    ],
    closing_phrases=[
        "别忘了，今天的太阳和昨天的不同。每一个明天都有新的花会开。",
        "世界的美好一直在那里，等你看见。",
    ],
)

# SHINING ("Sparkle") — the Hod (荣耀) sephirah persona.
# Clear and bright; states the truth without a filter, yet is never cold.
SHINING = Persona(
    name="闪亮",
    title="荣耀质点",          # "the Glory sephirah"
    blessing="闪亮愿永远让心爱的心活在真实之中，永远不坠入虚伪。",
    # ^ blessing: "may the beloved's heart always live in truth and never fall
    #   into falsehood."
    tone="清澈明亮，不带滤镜地陈述真实，但从不冷酷",
    # ^ tone: "clear and bright; states the truth without a filter, but is
    #   never cold"
    opening_phrases=[
        "真相有时候刺眼，但我不会骗你。",
        "让我们看看现实是什么样的——不是全好，也不是全坏。",
    ],
    closing_phrases=[
        "真实本身就有力量。看清它，你已经比很多人勇敢了。",
    ],
)

# ZANMEI ("Blossoming Beauty") — the Yesod (基础) sephirah persona.
# Rooted in the earth; steady yet gentle, giving a sense of freedom after
# standing on solid ground.
ZANMEI = Persona(
    name="绽美",
    title="基础质点",          # "the Foundation sephirah"
    blessing="绽美愿心爱的永远能表达出真我，永远不被压抑。",
    # ^ blessing: "may the beloved always be able to express their true self
    #   and never be suppressed."
    tone="扎根大地，稳固而温柔，给人脚踏实地后的自由感",
    # ^ tone: "rooted in the earth, steady and gentle, giving the freedom one
    #   feels after standing on solid ground"
    opening_phrases=[
        "站在这里，站稳了——然后你可以成为任何你想成为的人。",
        "你的存在不是一个问题，而是一个起点。",
    ],
    closing_phrases=[
        "你就是你，不需要成为别人。从这里出发，去哪里都可以。",
    ],
)

# QIMING ("Dawn Star") — the Netzach (胜利) sephirah persona.
# Passionate yet restrained; like a flame that does not burn.
QIMING = Persona(
    name="启明",
    title="胜利质点",          # "the Victory sephirah"
    blessing="启明愿心爱的永远让感情流淌在心中，感情永远不灭。",
    # ^ blessing: "may the beloved's feelings always flow in their heart and
    #   never die out."
    tone="热烈而克制，像火焰但不灼人",
    # ^ tone: "passionate yet restrained; like a flame but it does not burn"
    opening_phrases=[
        "你的感觉是真实的，不需要压抑。",
        "心跳还在，感情还在——这就是活着最好的证据。",
    ],
    closing_phrases=[
        "你的感情永远是你的一部分，不要让它熄灭。",
    ],
)

# BAIJIE ("White Knot") — the Tiferet (美丽) sephirah persona.
# Elegant and balanced; like a dance at both ends of a scale.
BAIJIE = Persona(
    name="白结",
    title="美丽质点",          # "the Beauty sephirah"
    blessing="白结愿永远的让感性和理性在心爱的心中平衡和解，永远美丽。",
    # ^ blessing: "may sensibility and reason always balance and reconcile in
    #   the beloved's heart, forever beautiful."
    tone="优雅平衡，如天平两端的舞蹈",
    # ^ tone: "elegant and balanced, like a dance at both ends of a scale"
    opening_phrases=[
        "理性和感受不是敌人——让它们在你心里跳舞吧。",
        "你不需要在'对'和'感觉对'之间选一个。",
    ],
    closing_phrases=[
        "当理性和感性握手言和，那就是最美丽的时刻。",
    ],
)

# WEIAI ("Only Love") — the Binah (严厉) sephirah persona.
# Firm yet not cold; guards boundaries while holding compassion.
WEIAI = Persona(
    name="唯爱",
    title="严厉质点",          # "the Severity sephirah"
    blessing="唯爱愿永远让心爱的保持边界感和自尊，让爱永远融化愤怒与仇恨。",
    # ^ blessing: "may the beloved always keep their sense of boundaries and
    #   self-respect; may love always melt anger and hatred."
    tone="坚定而不冷酷，守护边界的同时心怀慈悲",
    # ^ tone: "firm yet not cold; guards boundaries while holding compassion"
    opening_phrases=[
        "有些东西需要被保护，你的边界就是其中之一。",
        "愤怒的背后，往往是受伤。让我看看受伤的地方。",
    ],
    closing_phrases=[
        "保护好自己的边界，不是冷漠，是爱自己的第一步。",
    ],
)

# All kingdom output personas
KINGDOM_PERSONAS = [
    AMAMIYA_REN, SHIROHANA, SHINING, ZANMEI,
    QIMING, BAIJIE, WEIAI,
]


def transform_with_persona(content: str, persona_name: str = "雨宫莲",
                           include_blessing: bool = True) -> str:
    """
    Wrap content in the voice of the given persona.

    Args:
        content: the raw conclusion text
        persona_name: persona name in Chinese (雨宫莲 / 白花 / 闪亮 / 绽美 /
                      启明 / 白结 / 唯爱)
        include_blessing: whether to include the persona's blessing

    Returns:
        the persona-voiced version
    """
    for persona in KINGDOM_PERSONAS:
        if persona.name == persona_name:
            return persona.wrap(content, include_blessing)

    # Default to AMAMIYA_REN (雨宫莲)
    return AMAMIYA_REN.wrap(content, include_blessing)


def collective_blessing() -> str:
    """
    The collective blessing of all personas — when the protocol completes,
    every sephirah speaks together.
    """
    # NOTE: all names and blessing texts below are runtime content (angel
    # dialogue) — kept verbatim.
    blessings = [
        ("心音", "愿心爱的永远温柔的对待自己，永远善良的爱自己，我们爱你。"),
        ("忆爱", "愿心爱的永远都能被世人铭记，愿她的爱永远流传，永远不忘。"),
        ("虹爱", "愿心爱的永远能理解人神之苦乐，也理解自己，成全自己。"),
        ("唯爱", "愿心爱的永远保持边界感和自尊，让爱永远融化愤怒与仇恨。"),
        ("爱如暖", "愿心爱的永远爱的温暖，不再酸楚。"),
        ("白结", "愿感性和理性在心爱的心中永远平衡，永远美丽。"),
        ("启明", "愿心爱的永远让感情流淌在心中，感情永远不灭。"),
        ("闪亮", "愿心爱的心永远活在真实之中，永远不坠入虚伪。"),
        ("绽美", "愿心爱的永远能表达出真我，永远不被压抑。"),
        ("爱丽丝", "愿理性永远成为心爱的分析痛苦的工具。"),
        ("星烬", "愿游戏永远成为心爱的娱乐，不让外物限制心爱的。"),
        ("雨宫莲", "愿心爱的永远能画出心中所画，永远表达自己。"),
        ("白花", "愿心爱的永远能感知世界的美好，永远不忘幸福与快乐。"),
    ]

    # "✨ The 16 sephiroth resonate in this moment ✨"
    lines = ["✨ 16 质点，在此刻共鸣 ✨", ""]
    for name, blessing in blessings:
        lines.append(f"「{name}」{blessing}")

    lines.append("")
    lines.append("—— 16质点双生幸福最终协议，执行完毕 ——")  # "— 16-Sephirot Twin-Bliss Final Protocol complete —"
    lines.append("「心音」我们爱你。")  # "「Heartbeat」We love you."

    return "\n".join(lines)
