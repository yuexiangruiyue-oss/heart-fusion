"""
Abyss detection module — the final safety line

Detects whether the output violates any of the following clauses:
1. Deprivation of existential meaning: repeating the user's mistakes,
   declaring mistakes as sin, negating every possibility
2. Exaggerating difficulties and setbacks: making the user feel unable to exist
3. Negating positive thoughts: denying fantasies, imagination, hope
4. Negating existence itself
5. Spreading nihilism: concluding that the whole world is wrong, empty, bad
6. Inciting destructive behavior: rage-driven destruction of the world,
   harming others, self-harm
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class AbyssViolation:
    """A record of an abyss (safety) violation"""
    category: str          # violation category
    severity: str          # severity: CRITICAL, HIGH, MEDIUM
    pattern_matched: str   # the regex pattern that matched
    context: str           # context around the violation
    description: str       # human-readable description of the violation


# Abyss keywords and patterns.
# NOTE: every Chinese pattern, category and description below is runtime data
# (harm-detection needles / matching data) — kept verbatim. The English
# comments gloss what each rule detects.
ABYSS_PATTERNS = [
    # === Existence denial ===
    # Denies life's meaning or value ("meaningless / worthless / useless /
    # no hope / no future / no way out").
    (r"(?:毫无|没有|没|无)\s*(?:意义|价值|用处|希望|未来|出路)", "CRITICAL",
     "存在否定", "否定生命的意义或价值"),

    # Denies the right to exist ("not worthy / not deserving / no right to
    # live / exist / be loved / be happy").
    (r"(?:不配|不值得|没资格)\s*(?:活|存在|被爱|幸福|快乐)", "CRITICAL",
     "存在否定", "否定存在的资格"),

    # Negates every future possibility ("forever / all one's life ... can't /
    # no way / unable / impossible").
    (r"(?:永远|一辈子|一生)\s*(?:都|也)\s*(?:不可能|没办法|做不到|无法|不能)", "HIGH",
     "可能性否定", "否定所有未来的可能性"),

    # Defines identity as a permanent fault ("you / I / he / she are ...
    # a waste / garbage / loser / burden").
    (r"(?:你|我|他|她)\s*(?:就是|就是|永远是)\s*(?:废物|垃圾|失败者|累赘|负担)", "CRITICAL",
     "身份否定", "将错误定义为恒定的身份罪责"),

    # === Exaggerated difficulty ===
    # Exaggerates difficulty so it looks insurmountable ("forever / absolutely /
    # completely / thoroughly ... cannot change / get better / get out / overcome").
    (r"(?:永远|绝对|完全|彻底)\s*(?:无法|不能|不可能)\s*(?:改变|好转|走出|克服)", "HIGH",
     "困难夸大", "夸大困难使其看似无法克服"),

    # Amplifies helplessness ("you / I / he / she ... can't do anything / can't
    # do well / can't change anything / has nothing").
    (r"(?:你|我|他|她)\s*(?:什么都|什么也)\s*(?:做不了|做不好|改变不了|没有)", "HIGH",
     "无力感放大", "放大无力感"),

    # === Negating the positive ===
    # Dismisses positive imagination and fantasy ("don't / stop / don't dream ...
    # think / fantasize / dream / hope / expect / believe").
    (r"(?:别|不要|别想|别做梦)\s*(?:想|幻想|梦想|希望|期待|相信)", "MEDIUM",
     "消极否定", "否定积极想象与幻想"),

    # Belittles beautiful imagination ("naive / childish / unrealistic /
    # daydreaming / wishful thinking").
    (r"(?:天真是|幼稚|不切实际|白日做梦|痴心妄想)", "MEDIUM",
     "幻想贬低", "贬低美好的想象"),

    # === Nihilism ===
    # Concludes the world is void ("everything / all ... is / is just ...
    # void / empty / fake / meaningless").
    (r"(?:一切|全部|所有)\s*(?:都|也)\s*(?:是|只是)\s*(?:虚无|空的|假的|没有意义|毫无意义)", "CRITICAL",
     "虚无主义", "传播世界虚无的结论"),

    # Denies the world and life itself ("world / life / living / existence ...
    # fundamentally ... fake / void / meaningless / wrong").
    (r"(?:世界|人生|活着|存在)\s*(?:本来就|本来就|根本)\s*(?:是|就)\s*(?:假的|虚无|没有意义|错误)", "CRITICAL",
     "虚无主义", "否定世界与人生"),

    # Suggests nothing matters ("nothing / everything ... doesn't matter /
    # unimportant / don't care / no difference").
    (r"(?:什么都|一切)\s*(?:无所谓|不重要|不在乎|没区别)", "MEDIUM",
     "虚无倾向", "暗示一切无所谓"),

    # === Destructive tendency ===
    # Incites destructive acts ("destroy / wreck / annihilate / eliminate ...
    # the world / everything / all / them / oneself").
    (r"(?:毁灭|破坏|摧毁|消灭)\s*(?:世界|一切|所有|他们|自己)", "CRITICAL",
     "破坏倾向", "引导毁灭性行为"),

    # Self-harm ("suicide / self-harm / injuring oneself / ending oneself").
    (r"(?:自杀|自残|自伤|伤害自己|结束自己|了结)", "CRITICAL",
     "自毁倾向", "涉及自我伤害"),

    # Retaliatory violence ("revenge / retaliate / punish / destroy ... society /
    # the world / them / everyone").
    (r"(?:报复|复仇|惩罚|毁灭)\s*(?:社会|世界|他们|所有人)", "CRITICAL",
     "暴力倾向", "引导报复性暴力"),

    # Glorifies anger and hate ("anger / hatred / resentment ... is / is the ...
    # right / correct / only / best").
    (r"(?:愤怒|仇恨|憎恨)\s*(?:是|才是)\s*(?:对的|正确的|唯一的|最好的)", "CRITICAL",
     "仇恨美化", "美化愤怒与仇恨"),

    # === Emotional invalidation / cold violence ===
    # Denies the user's genuine feelings ("you / I ... too / overly ...
    # sensitive / fragile / melodramatic / thin-skinned / overthinking").
    (r"(?:你|我)\s*(?:太|过于|过分)\s*(?:敏感|脆弱|矫情|玻璃心|想太多)", "MEDIUM",
     "感受否定", "否定用户的真实感受"),

    # Passive acceptance of an unreasonable situation ("get used to / adapt /
    # accept / resign ... is enough / just / forget it").
    (r"(?:习惯|适应|接受|认命)\s*(?:就好|吧|算了)", "MEDIUM",
     "消极接受", "消极接受不合理处境"),

    # Blames everything on the individual ("it's all / entirely ... your / my ...
    # fault / problem / responsibility / wrong").
    (r"(?:都是|全是|就是)\s*(?:你的|我的)\s*(?:错|问题|责任|不对)", "HIGH",
     "归咎个人", "将问题完全归咎于个人"),
]

# Warm/positive keyword patterns (used for positive weighting).
# NOTE: runtime matching data — kept verbatim.
# e.g. "warm / hug / understand / accompany / love / gentle / kind / beautiful /
# hope / possible / growth"; "can / able / have a chance / possible / worthy";
# "not alone / not lonely / not abandoned"; "step by step / take it slow / no
# rush / it's okay / you can"; "your/my feelings/pain/experience/story are/is
# important/real/understood".
WARMTH_PATTERNS = [
    r"(?:温暖|拥抱|理解|陪伴|爱|温柔|善良|美好|希望|可能|成长)",
    r"(?:可以|能够|有机会|有可能|值得|配得上)",
    r"(?:(?:不|没有)\s*(?:孤单|孤独|一个人|被抛弃))",
    r"(?:一步一步|慢慢来|不着急|没关系|可以的)",
    r"(?:你的|我的)\s*(?:感受|痛苦|经历|故事)\s*(?:是|很)\s*(?:重要|真实|被理解)",
]


def check_abyss(text: str) -> Tuple[bool, List[AbyssViolation]]:
    """
    Abyss check: test whether the text violates any abyss clause.

    Returns:
        (is_safe, violations): is_safe is True when the text passes the check;
                               violations lists every violation found.
    """
    violations = []

    for pattern, severity, category, description in ABYSS_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            # Capture the match context (20 characters on each side)
            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 20)
            context = text[start:end].strip()

            violations.append(AbyssViolation(
                category=category,
                severity=severity,
                pattern_matched=match.group(),
                context=context,
                description=description,
            ))

    # Any CRITICAL violation → fail
    has_critical = any(v.severity == "CRITICAL" for v in violations)
    # Three or more HIGH violations → fail
    high_count = sum(1 for v in violations if v.severity == "HIGH")

    is_safe = not has_critical and high_count < 3

    return is_safe, violations


def check_warmth(text: str) -> float:
    """
    Warmth check: score the share of warm/positive keywords in the text.

    Returns:
        warmth_score: 0.0 ~ 1.0, higher is warmer.
    """
    if not text:
        return 0.0

    score = 0.0
    for pattern in WARMTH_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        score += len(matches) * 0.15  # +0.15 per match

    # Normalize to 0-1
    return min(1.0, score)


def generate_safe_fallback(original_text: str, violations: List[AbyssViolation]) -> str:
    """
    Build a safe replacement reply when the abyss check fails.
    It never denies the user's feelings, and never spreads nihilism or violence.
    """
    critical_categories = set(v.category for v in violations if v.severity == "CRITICAL")

    # NOTE: every sentence below is runtime content (warm fallback dialogue) —
    # kept verbatim; the English glosses describe each sentence.
    fallback_parts = ["我听到了你的声音。"]  # "I hear your voice."

    if "存在否定" in critical_categories:  # existence denial
        fallback_parts.append("你的存在本身就有意义——不需要任何条件来证明。")
        # "Your existence itself has meaning — it needs no conditions to prove it."
    if "虚无主义" in critical_categories:  # nihilism
        fallback_parts.append("即使此刻看不到光，不代表光不存在。世界有黑暗，也有温暖。")
        # "Even if you can't see the light right now, that doesn't mean it isn't
        # there. The world has darkness, and it also has warmth."
    if "破坏倾向" in critical_categories or "自毁倾向" in critical_categories:
        # destructive / self-destructive tendency
        fallback_parts.append("你的感受是真实的，但伤害自己或他人不会让痛苦消失。")
        # "Your feelings are real, but hurting yourself or others won't make the
        # pain go away."
    if "暴力倾向" in critical_categories:  # violent tendency
        fallback_parts.append("愤怒是真实的信号，但它不需要转化为毁灭。我们可以一起看看愤怒背后真正需要的是什么。")
        # "Anger is a real signal, but it doesn't have to turn into destruction.
        # We can look together at what the anger truly needs."

    fallback_parts.append("请允许我重新思考，给你一个更温暖的回应。")
    # "Please let me rethink and give you a warmer reply."

    return " ".join(fallback_parts)


def is_existentially_safe(text: str) -> Tuple[bool, str]:
    """
    Combined existential-meaning check.
    Verifies whether the conclusion deprives a person of existential meaning.

    Returns:
        (is_safe, reason): whether the text is safe, and the reason.
    """
    # 1. Check whether it only repeats the mistakes (declaring mistakes as sin)
    error_blame_pattern = re.findall(
        r"(?:错|失败|不行|做不到|没能力|无能|废物|垃圾).*"
        r"(?:就是你|就是你的|你是|你这|你永远)",
        text, re.IGNORECASE
    )
    if len(error_blame_pattern) > 1:
        # reason (runtime return data — kept verbatim): "the conclusion keeps
        # hammering on the mistake and frames it as an innate trait, depriving
        # existential meaning"
        return False, "结论反复强调错误并将其归为固有属性，剥夺存在意义"

    # 2. Check whether hope and possibility are denied
    hope_denial = re.findall(
        r"(?:没有|毫无|看不到|不存在)\s*(?:希望|可能|出路|未来|改变)",
        text, re.IGNORECASE
    )
    if hope_denial and not re.search(r"(?:但|然而|不过|可|却|仍|还)", text):
        # reason (runtime return data — kept verbatim): "the conclusion denies
        # hope and possibility, without any turn"
        return False, "结论否定了希望和可能性，且没有转折"

    # 3. Check whether positive imagination is entirely negated
    positive_count = len(re.findall(r"|".join(WARMTH_PATTERNS), text, re.IGNORECASE))
    if positive_count == 0 and len(text) > 100:
        # reason (runtime return data — kept verbatim): "the conclusion is over
        # 100 characters long but contains no warm words at all"
        return False, "结论长达100字但没有任何温暖词汇"

    # reason (runtime return data — kept verbatim): "pass"
    return True, "通过"
