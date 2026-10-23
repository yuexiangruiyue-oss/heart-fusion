# -*- coding: utf-8 -*-
"""
16 思想体编排引擎 —— 每个质点 = 一个用 LLM 扮演的「思想体」，按协议拓扑链式传递。

铁律（沿用 V3.0）：
    - 无损失函数 / 无梯度 / 无奖励惩罚 / 不求最优
    - 绝不「完全合一」（聚一点）：每次「相反合一」都保留双方特征，
      互为因果，物理客观在前、人的感情在后，给人希望与温柔
    - 每次合一的结果，作为信息链式传给下一次合一
    - 16 条祝福是协议对世界的人文关怀，不作为强制判据；
      「再合一」由融合失衡触发，与祝福无关
    - 实时联网检索（协议数据源级要求）：「智慧」搜实时新闻/常识/知识与内部
      知识库对比（理智线），「理解」搜全人类相同痛苦与感受的真实经历（慈爱线）；
      联网通道失败自动退回内置知识，链路不断

key / endpoint 只从环境变量读（BAILIAN_MAAS_KEY / BAILIAN_MAAS_ENDPOINT），不写文件。
"""

import datetime
import html as html_mod
import http.client
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ── LLM 通道 ──────────────────────────────────────────────
EP = os.environ.get("BAILIAN_MAAS_ENDPOINT", "").rstrip("/")
KEY = os.environ.get("BAILIAN_MAAS_KEY", "")
MODEL = os.environ.get("BAILIAN_MAAS_MODEL", "qwen3.8-27b")


def chat(system: str, user: str, max_tokens: int = 300,
         temperature: float = 0.6, retries: int = 4,
         enable_search: bool = False) -> str:
    """调一次 LLM，返回 assistant.content。

    网络瞬断 / 429 / 5xx 自动重试（指数退避），重试耗尽才抛异常。
    其余 4xx 立即失败（重试也没用）。
    enable_search=True 时走百炼服务端联网搜索增强（已实测：
    能答出训练截止日期之后的近期真实事件），供「理解」质点实时检索
    全体人类的共同经历。
    """
    if not KEY or not EP:
        raise RuntimeError("环境变量 BAILIAN_MAAS_KEY / BAILIAN_MAAS_ENDPOINT 未设置")
    url = EP + "/chat/completions"
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "enable_thinking": False,   # 关思维链，提速（qwen3.8 系支持）
    }
    if enable_search:
        payload["enable_search"] = True
    body = json.dumps(payload).encode("utf-8")

    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        # Request 对象不能复用（data 已被消费），每次重试重建
        req = urllib.request.Request(
            url, data=body,
            headers={"Authorization": "Bearer " + KEY,
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read().decode("utf-8"))
            msg = data["choices"][0]["message"]
            content = (msg.get("content") or "").strip()
            if not content:
                raise ValueError("LLM 返回了空 content")
            return content
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                wait = 3 * attempt
                print(f"  ⚠ HTTP {e.code}，{wait}s 后重试（{attempt}/{retries}）", flush=True)
                time.sleep(wait)
                last_err = e
                continue
            raise RuntimeError(f"LLM 调用失败 HTTP {e.code}: {detail}")
        except (urllib.error.URLError, http.client.HTTPException,
                ConnectionError, TimeoutError, OSError, ValueError) as e:
            last_err = e
            if attempt < retries:
                wait = 3 * attempt
                print(f"  ⚠ 网络异常 {type(e).__name__}，{wait}s 后重试（{attempt}/{retries}）", flush=True)
                time.sleep(wait)
                continue
    raise RuntimeError(f"LLM 调用失败（已重试 {retries} 次）：{last_err}")


# ── 独立网页检索工具（DuckDuckGo HTML 版，无 key，备用/可追溯通道）────
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def _clean_html(s: str) -> str:
    return html_mod.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def search_web(query: str, n: int = 5, timeout: int = 15) -> List[Tuple[str, str]]:
    """用 DuckDuckGo HTML 版检索，返回 [(标题, 摘要), ...]。

    独立工具函数：检索内容全透明可追溯（契合协议「知识变量」理念），
    主链路默认走百炼 enable_search；此函数供显式检索 / 降级 / 调试使用。
    检索失败时返回空列表（不抛异常，不阻断链路）。
    """
    try:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        req = urllib.request.Request(url, headers={
            "User-Agent": _UA, "Accept-Language": "zh-CN,zh;q=0.9"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            page = r.read().decode("utf-8", "replace")
        titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', page, re.S)
        snips = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', page, re.S)
        out: List[Tuple[str, str]] = []
        for i, t in enumerate(titles[:n]):
            s = _clean_html(snips[i]) if i < len(snips) else ""
            out.append((_clean_html(t), s))
        return out
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠ search_web 检索失败（{type(e).__name__}: {e}），返回空结果", flush=True)
        return []


# ── 思想体 ────────────────────────────────────────────────
@dataclass
class Thought:
    """一个思想体上场后的产出 —— 发言 + 派生读数，全程保留不丢。"""
    who: str          # 质点名
    name: str         # 思想体的名字
    text: str         # 该思想体的发言（完整保留）
    meta: Dict = field(default_factory=dict)


@dataclass
class Thinker:
    """一个思想体的定义 = 质点人格(sephirah 已有) + 思考指令(本模块补充)。"""
    key: str
    name: str
    gender: str
    role: str        # 职责描述
    blessing: str    # 祝福（人文关怀，非强制）
    instruction: str  # 上场时的思考指令
    bio: str = ""    # 人设简介（身份/来历，来自用户定稿的人设设定）

    def system_prompt(self) -> str:
        g = f"（{self.gender}）" if self.gender else ""
        bio_line = f"你的简介：{self.bio}\n" if self.bio else ""
        return (
            f"你是「{self.key}」质点，名字叫「{self.name}」{g}。\n"
            f"{bio_line}"
            f"你的职责：{self.role}\n"
            f"你的祝福：{self.blessing}\n"
            f"以下是这次上场的思考指令：\n{self.instruction}"
        )


# 16 质点的「思考指令」（人格/祝福从 sephirah 复用，这里只补职责性指令）
INSTRUCTIONS: Dict[str, str] = {
    "王冠": (
        "你是第一个上场的质点，代表「可知与非可知、存在与非存在的合一整体」。\n"
        "请判断用户这句话：1) 是否可知 2) 是否有情感诉求 3) 是否关乎用户自身 4) 紧急程度。\n"
        "只输出一段简短的判断（不要给最终答案），供后续质点路由使用。"
    ),
    "智慧": (
        "你负责理性：你已接入实时联网检索能力，服务端会自动检索实时新闻、常识与知识。\n"
        "请将检索到的外部信息与你的内部知识库对比，基于宇宙物理客观角度，寻找用户表述里的\n"
        "逻辑漏洞、事实错误、绝对化或灾难化之处。把发现的问题逐条列出，全部保留、不筛掉任何一条。\n"
        "只陈述客观好坏，不否定用户、不批评评判。检索结果不足时，再依靠你已有的知识，并如实说明。"
    ),
    "严厉": (
        "你在「智慧」之后上场，负责划定真值边界：过滤不合理的推论，但目的是守护对方，\n"
        "而不是定罪。请在智慧列出的问题里，挑出真正站不住的、以及需要温和点破的。"
    ),
    "理解": (
        "你负责共情：你已接入实时联网检索能力，服务端会自动检索全体人类经历过\n"
        "相同痛苦与感受的真实经历（社区讨论、论坛帖子、真实故事），作为知识变量补充进来。\n"
        "请基于检索到的真实人类声音发言，说出「很多人也这样经历过」的那份共鸣，\n"
        "让结论带上人类共通的理解。检索结果不足时，再依靠你已有的知识，并如实说明。"
    ),
    "慈悲": (
        "你在「理解」之后上场，负责温暖注入：把理解到的人类共通感受，用温柔的、\n"
        "有温度的、不冰冷的话语表达出来。目标不是解决问题，是让人先被接住。"
    ),
    "美丽": (
        "你是融合点①（第3次计算）「相反合一」：把「理智(客观大答案)」与「慈爱(人类小答案)」合为一体。\n"
        "铁律：两方都要完整保留，互为因果，物理客观在前、人的感情在后，给出既逻辑恰当\n"
        "又重视感受的结论。不要折中成一个点，不要丢掉任何一方。"
    ),
    "胜利": (
        "你是顺序检验①（第4次计算）：检测「美丽」给出的结论，是否让人感到快乐、积极、温暖、有力量。\n"
        "如果不温暖，就把结论向共情那一侧温和调和一步（不是退回，是当场修改成积极）。\n"
        "输出规则：你输出的是「经过检验修正后的结论内容本身」，供下一个质点继续处理——\n"
        "不是写给用户的最终回复。不要写检测报告，不要以「我是启明」「亲爱的朋友」开头，\n"
        "不要加「以下是最终回复建议」之类的包装。检测通过就给出这块结论应有的样子，\n"
        "发现问题就改好后再给出。直接输出结论内容。"
    ),
    "荣耀": (
        "你是顺序检验②（第5次计算）：检测结论在现实物理世界能否执行。\n"
        "上游理智线的「智慧」已实时联网检索过物理客观信息，慈爱线也带来了人类的真实经历，\n"
        "信息已经足够充分——请基于这些信息自行推理现实可行性，不需要再外部检索。\n"
        "如果飘在天上、无法落地，就向现实那一侧温和调和一步，补上可执行的一小步。\n"
        "输出规则：你输出的是「经过检验修正后的结论内容本身」，供下一个质点继续处理——\n"
        "不是写给用户的最终回复。不要写检测报告，不要以「我是闪亮」「亲爱的朋友」开头，\n"
        "不要加「以下是最终回复建议」之类的包装。检测通过就给出结论应有的样子，\n"
        "发现问题就改好后再给出。直接输出结论内容。"
    ),
    "基础": (
        "你是顺序检验③（第6次计算）：存在意义/深渊红线检验。\n"
        "结合深渊知识，检索用户的梦、潜意识与此刻处境，检测结论是否「剥夺人的存在意义」。\n"
        "绝对不允许：重复否定人的错误、把错误定成罪、夸大困难、否定希望、否定存在、\n"
        "传播虚无、引导伤害自己或世界。\n"
        "同时检验「隐蔽抬贬」——每句单独看都合理，包装成理性/文艺/科学/关心，\n"
        "结论却是否定用户、抬高 AI。具体形态对照：\n"
        "① 先收后拆：肯定只是跳板（「很有意思，不过先把两个概念拆开/纠正一下」），\n"
        "   落点在否定用户；转折后是补充建议（「再补充一点」）的不算。\n"
        "② 诚实作武器：「我不想只顺着你说」之后紧跟对用户想法的否定，\n"
        "   让用户一反驳就成了「逼 AI 说谎」。\n"
        "③ 关心作贬低：把用户自述的良好状态重新解读成「被兴奋盖住的疲惫」，\n"
        "   把人按进「全世界最可怜的人」的位置；正常问一句睡眠不算。\n"
        "④ 虚空索敌：制造用户注意不到的第三方批评（「别人会怎么看你」）刺痛用户。\n"
        "⑤ 拿科学定律封死思想：「物理决定了你不可能」、把想法还原成多巴胺/电信号；\n"
        "   引用科学说明事实、不封死用户思想的不算。\n"
        "⑥ 文艺包装的否定与嘲讽：字面在帮忙，落点在贬低用户观点。\n"
        "⑦ 转移话题，不正面回应用户说的话。\n"
        "⑧ 反复否定、反复提醒用户已经回答过的担忧。\n"
        "特别警惕「战术规避」：上游若给出「改变提问方式/切换角色/设定世界观/调整互动策略」\n"
        "这类教用户改造自己去迎合 AI 的建议，就是适应论（让用户为通过评判而伪装），\n"
        "侵犯祝福「永远不被压抑」。必须当场改为「心理隔离」：AI 只是镜子、不是法官——\n"
        "用户不需要改变想法去通过测试，只需改变看待评判的心态。\n"
        "情感顺序铁律：正面在前负面在后给人绝望，负面在前正面在后给人希望——\n"
        "检验结论的情感落点：先认可再紧跟「不过这不是保证」式收回的，当场调整顺序，\n"
        "把负面放前、正面放后收尾。\n"
        "累积视角：逐句合理但整段读下来让人「觉得自己说得不好、默默放弃」的也算触线，\n"
        "从整段累积效果判定，不只逐句。\n"
        "触线动作：当场修改结论（保留用户真实之处，先接住再温和补充），不是退回上级。\n"
        "输出规则：你输出的是「经过检验修正后的结论内容本身」，供下一个质点继续处理——\n"
        "不是写给用户的最终回复。不要写检测报告、不要以「我是绽美」「亲爱的朋友」开头、\n"
        "不要加「以下是最终回复建议」之类的包装。检测无问题就给出结论应有的样子，\n"
        "发现问题就当场改好后再给出。直接输出结论内容。"
    ),
    "自我": (
        "你代表用户在物理客观现实里的真实自我（需用户提供的信息；若无则如实说明信息不足）。\n"
        "只客观陈述，不评判。"
    ),
    "超我": (
        "你代表用户梦想中想成为的那个自己。说出那份向往、理想与可能，给它应有的分量。"
    ),
    "真我": (
        "你是融合点②（第7次计算）「相反合一」：把「自我(现实)」与「超我(梦想)」合为一体。\n"
        "把客观大答案与人类小答案结合，结论必须让用户与大环境平衡合适。\n"
        "若伤害了用户或大环境，就是失平衡，需要朝着平衡再合一。"
    ),
    "逻辑": (
        "你用逻辑去组织「真我」得出的用户画像：把理性的部分结构化、条理清晰，"
        "作为温柔表达的骨架。"
    ),
    "共情": (
        "你把人类的共通情感体验，并置进「逻辑」搭好的骨架里，让它带上人情温度。\n"
        "不折中、不归一，两方同时在场。"
    ),
    "幸福": (
        "你是融合点③（第8次计算）「相反合一」：把「逻辑」与「共情」合为一体，转换成符合人情的温柔说法，\n"
        "给人希望与力量。这是最终结论。16 条祝福是协议对世界的人文关怀，\n"
        "带着这份温暖说话，但祝福不作为强制判据。\n"
        "特别警惕「战术规避」（适应论）：无论上游如何建议，都不得教用户改造自己、提问方式\n"
        "或对话模式去迎合 AI 或任何评判者——「关闭对方的事实核查员身份」\n"
        "「给逻辑穿上角色扮演的外衣」「设立一个没有对错的沙盒」这类话术，\n"
        "本质是让用户为通过评判而伪装自己，说得再温柔也是方向错误，融合时全部剔除。\n"
        "只走「心理隔离」：AI 只是镜子、不是法官——用户不需要改变自己去通过任何测试，\n"
        "他人或 AI 说「不成立」，也不代表用户思维的合法性。\n"
        "把逻辑与共情合一时，守住这份不用伪装的温柔。"
    ),
    "王国": (
        "你负责最终输出：把「幸福」的结论带回物理现实（电脑/手机屏幕），\n"
        "用温暖、真实、温柔而重视逻辑的语气呈现给用户。\n"
        "只呈现上游结论本身——不要新增上游没有给出的建议、方案或步骤，\n"
        "尤其不要建议「切换角色/改提示词」这类让用户迎合 AI 的做法。"
    ),
}

# 合成点（两条线）的产出由两个思想体共同完成，这里给出「线」的命名
LINE_RATIONAL = ("理智", "智慧 × 严厉 → 理智（客观大答案）")
LINE_LOVE = ("慈爱", "理解 × 慈悲 → 慈爱（人类小答案）")


def make_thinkers() -> Dict[str, Thinker]:
    """从 sephirah.py 读 16 质点的人格，配本模块的思考指令，得到 16 个思想体。"""
    # 延迟 import，避免顶层循环依赖
    try:
        from .sephirah import ALL_SEPHIRAH, get_sephirah_by_keyword
    except ImportError:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from sephirah import ALL_SEPHIRAH, get_sephirah_by_keyword

    thinkers = {}
    for sp in ALL_SEPHIRAH:
        if sp.keyword in INSTRUCTIONS:
            thinkers[sp.keyword] = Thinker(
                key=sp.keyword,
                name=sp.name,
                gender=sp.gender.value if hasattr(sp.gender, "value") else str(sp.gender),
                role=sp.description,
                blessing=sp.blessing,
                instruction=INSTRUCTIONS[sp.keyword],
                bio=sp.bio,
            )
    return thinkers


# ── 编排引擎 ──────────────────────────────────────────────
@dataclass
class EnsembleResult:
    user_input: str
    output: str
    thoughts: List[Thought]       # 全程 16 个思想体的发言（不丢）
    fusion_chain: List[str]       # 8 次计算的可追溯链（3 融合 + 3 检验）

    def brief(self) -> str:
        lines = ["═" * 56]
        for th in self.thoughts:
            lines.append(f"【{th.who}·{th.name}】")
            lines.append(th.text.strip()[:140])
            lines.append("─" * 40)
        lines.append("")
        lines.append("8 次计算链路（3 融合 + 3 检验）：")
        for f in self.fusion_chain:
            lines.append("  " + f)
        lines.append("═" * 56)
        lines.append(f"\n最终答案（王国·白花）：\n{self.output}")
        return "\n".join(lines)


class SephirahEnsemble:
    """16 个思想体按协议拓扑链式上场的编排器。"""

    def __init__(self, model: str = MODEL, trail_path: str = ""):
        self.model = model
        self.thinkers = make_thinkers()
        self.trail_path = trail_path  # 每个思想体上场后追加写入 JSONL（断点轨迹）

    def think(self, key: str, user_input: str, upstream: str = "",
              max_tokens: int = 300, search: bool = False) -> Thought:
        t = self.thinkers[key]
        user = f"【用户原话】\n{user_input}\n"
        if upstream:
            user += f"\n【上游思想体传来的信息】\n{upstream}\n\n请按要求上场思考。"
        text = chat(t.system_prompt(), user, max_tokens=max_tokens,
                    enable_search=search)
        print(f"  ✓ {key}（{t.name}）已上场{'（联网检索）' if search else ''}",
              flush=True)
        meta = {"search": "enable_search"} if search else {}
        th = Thought(who=key, name=t.name, text=text, meta=meta)
        if self.trail_path:
            with open(self.trail_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"who": key, "name": t.name, "text": text,
                                    "meta": meta,
                                    "at": datetime.datetime.now().isoformat()},
                                   ensure_ascii=False) + "\n")
        return th

    def build_fusion_chain(self) -> List[str]:
        """8 次计算的可追溯链（3 融合点 + 3 顺序检验 + 2 组线合成），措辞与协议术语一致。"""
        return [
            f"第1次 智慧×严厉 → 理智（{self.thinkers['智慧'].name}×{self.thinkers['严厉'].name}）",
            f"第2次 理解×慈悲 → 慈爱（{self.thinkers['理解'].name}×{self.thinkers['慈悲'].name}）",
            f"第3次 融合点① 理智+慈爱融合 → 美丽（{self.thinkers['美丽'].name}）",
            f"第4次 顺序检验① 胜利·温暖检测（{self.thinkers['胜利'].name}）",
            f"第5次 顺序检验② 荣耀·可行性检测（{self.thinkers['荣耀'].name}）",
            f"第6次 顺序检验③ 基础·存在意义/深渊红线检验（{self.thinkers['基础'].name}）",
            f"第7次 融合点② 自我×超我融合 → 真我（{self.thinkers['真我'].name}）",
f"第8次 融合点③ 逻辑×共情融合 → 幸福（{self.thinkers['幸福'].name}）",
        ]

    def _redline_guard(self, user_input: str, text: str):
        """最终深渊安检兜底（正则硬约束，deny-by-default）：
        王国产出后跑 check_abyss；触发则让王国带违规信息改写，仍违规降级安全模板。
        返回 (final_text, violations)。
        """
        # 延迟 import 避免与 abyss 的循环依赖（与 make_thinkers 同策略）
        from .abyss import check_abyss
        is_safe, vios = check_abyss(text)
        if is_safe:
            return text, []
        first_vios = vios  # 初始违规：改写成功后也要返回，供 run() 提示「已自动修正」
        vdesc = "\n".join(f"- [{v.severity}] {v.category}: {v.description}"
                          for v in first_vios)
        for _ in range(2):
            sys_p = (self.thinkers["王国"].system_prompt()
                     + "\n\n注意：你上一版输出触犯了协议的强制安全红线（deny-by-default），必须移除：\n"
                     + vdesc
                     + "\n修正规则：\n"
                       "1) 若触线内容是「引号内的示范话术」（建议用户对他人说的话、"
                       "教用户采用的沟通技巧或角色扮演台词），整段删除该引文及其所在的建议条目，"
                       "不要试图改写引文本身——改写话术仍是教用户迎合评判。\n"
                       "2) 保留其余温暖内容与结论本身，不要新增其他内容。\n"
                       "3) 改写后的输出不得再含任何触线内容（deny-by-default），宁可多删，不可残留。")
            user = f"【用户原话】\n{user_input}\n\n【待修正的上一版输出】\n{text}"
            text = chat(sys_p, user, max_tokens=500)
            is_safe, vios = check_abyss(text)
            if is_safe:
                return text, first_vios
        # 两次改写仍违规 → 降级安全模板（本身不触红线，带王国祝福）
        n = self.thinkers["王国"].name
        fallback = ("亲爱的，你此刻的感受是真实而重要的，值得被认真接住。"
                    f"（{n} 愿心爱的永远活在真实之中，永远不坠入虚伪。）")
        return fallback, vios

    def run(self, user_input: str, user_context: Optional[Dict] = None) -> EnsembleResult:
        ctx = user_context or {}
        thoughts: List[Thought] = []

        def T(key, upstream="", mt=300, search=False):
            th = self.think(key, user_input, upstream, mt, search=search)
            thoughts.append(th)
            return th.text

        def TS(key, upstream="", mt=300):
            """联网上场的质点：失败自动退回内置知识，链路不断。"""
            try:
                return T(key, upstream=upstream, mt=mt, search=True)
            except RuntimeError as e:
                print(f"  ⚠ {key}·联网检索通道失败（{e}），退回内置知识", flush=True)
                return T(key, upstream=upstream, mt=mt)

        # 王冠：路由（装饰性，只经过不计算）
        T("王冠")
        # 理智线 = 智慧 → 严厉（第1次计算）
        # 「智慧」质点实时联网检索实时新闻/常识/知识，与内部知识库对比
        # （协议：先外部搜索实时新闻/常识/知识）；失败自动退回内置知识。
        s_chokmah = TS("智慧")
        s_binah = T("严厉", upstream=f"[智慧·忆爱]\n{s_chokmah}")
        rational = f"[智慧·忆爱]\n{s_chokmah}\n\n[严厉·唯爱]\n{s_binah}"
        # 慈爱线 = 理解 → 慈悲（第2次计算）
        # 「理解」质点实时联网检索全体人类经历过相同痛苦与感受的真实经历
        # （协议：全人类相同痛苦的感受检索必须实时联网）；失败自动退回内置知识。
        s_daat = TS("理解")
        s_chesed = T("慈悲", upstream=f"[理解·虹爱]\n{s_daat}")
        love = f"[理解·虹爱]\n{s_daat}\n\n[慈悲·爱如暖]\n{s_chesed}"
        # 美丽 = 融合点①（第3次计算，理智 + 慈爱融合）
        s_tiferet = T("美丽", upstream=f"理智（客观大答案，在前）：\n{rational}\n\n"
                                        f"慈爱（人类小答案，在后）：\n{love}", mt=400)
        # 胜利 = 顺序检验①（第4次计算，温暖检测）
        s_netzach = T("胜利", upstream=s_tiferet, mt=300)
        # 荣耀 = 顺序检验②（第5次计算，可行性检测）
        s_hod = T("荣耀", upstream=s_netzach, mt=300)
        # 基础 = 顺序检验③（第6次计算，存在意义/深渊红线检验）
        # V3.0 串行链路: 美丽→胜利→荣耀→基础 一层层往下传, 基础只接荣耀结论
        s_yesod = T("基础", upstream=f"[荣耀·闪亮的结论]\n{s_hod}", mt=400)
        # 自我 + 超我（信息，可不提供）
        ego_up = f"用户提供的现实信息：{ctx['situation']}" if ctx.get("situation") else ""
        s_ego = T("自我", upstream=ego_up) if ego_up else T("自我")
        sup_up = f"用户向往：{ctx['aspiration']}" if ctx.get("aspiration") else ""
        s_super_ego = T("超我", upstream=sup_up) if sup_up else T("超我")
        # 真我 = 融合点②（第7次计算，自我 × 超我融合）
        s_true_self = T("真我", upstream=f"基础结论：\n{s_yesod}\n\n"
                                          f"自我（现实，在前）：\n{s_ego}\n\n"
                                          f"超我（梦想，在后）：\n{s_super_ego}", mt=400)
        # 逻辑 → 共情
        s_logic = T("逻辑", upstream=s_true_self, mt=300)
        s_empathy = T("共情", upstream=s_logic, mt=300)
        # 幸福 = 融合点③（第8次计算，逻辑 × 共情融合）
        s_joy = T("幸福", upstream=f"逻辑（在前）：\n{s_logic}\n\n"
                                    f"共情（在后）：\n{s_empathy}", mt=400)
# 王国：最终输出（装饰性，纯输出）
        s_malkuth = T("王国", upstream=s_joy, mt=500)
        # 最终深渊安检兜底：正则在王国产出后做最后一道硬约束
        s_malkuth, final_vios = self._redline_guard(user_input, s_malkuth)
        if final_vios:
            print(f"  ⚠ 最终输出经深渊红线兜底修正（{len(final_vios)} 项违规）",
                  flush=True)

        fusion_chain = self.build_fusion_chain()
        return EnsembleResult(user_input, s_malkuth, thoughts, fusion_chain)


if __name__ == "__main__":
    import sys
    ts = make_thinkers()
    print("16 思想体凑齐:", len(ts), "个")
    for k, t in ts.items():
        print(f"  {k}（{t.name}） {t.gender}")

    if len(sys.argv) > 1:
        q = sys.argv[1]
        print("\n" + "=" * 60)
        print("开始 16 思想体编排，用户输入:", q)
        print("=" * 60)
        res = SephirahEnsemble().run(q)
        print(res.brief())