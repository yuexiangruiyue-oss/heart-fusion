# -*- coding: utf-8 -*-
"""1177篇全量深度分析：分类×月份矩阵、关键词演变、实体、字数趋势"""
import json, re
from collections import Counter, defaultdict

data = [json.loads(l) for l in open(r"D:\双生天使的怀抱\.workbuddy\tmp_love_full.jsonl", encoding="utf-8")]
data = [d for d in data if not d["body"].startswith("__ERR__")]

RULES = [
    ("卡巴拉与16质点体系", r"质点|卡巴拉|生命之树|王冠|理智线|慈爱线|美丽|胜利|荣耀|基础|王国|深渊|逆卡巴拉|双生协议|双子星协议|sephirot|神名|decagrammaton|流溢|圣婚|新郎|新娘"),
    ("AI与人工智能思辨", r"\bai\b|人工智能|chatgpt|gpt|deepseek|grok|claude|gemini|neuro|vedal|agent|大模型|智能体|llm|sora|comfyui|token|训练|数据集|微调|算法|算力|觉醒|图灵|停机|镜像"),
    ("自我疗愈与创伤书写", r"自闭|孤独症|疗愈|治愈|创伤|原生家庭|霸凌|抑郁|轻生|性别|跨性别|焦虑|绝望|心理|情感逻辑|拥抱|抱抱|取暖|自救|病历|病"),
    ("宇宙物理与科学猜想", r"宇宙|量子|黑洞|白洞|热寂|熵|光速|相对论|爱因斯坦|奇点|氢弹|物理|维度|时空|引力|粒子|能量|太阳|月亮|圆月|星星|天文"),
    ("小说与故事创作", r"小说|故事|章节|第\d+章|娘化|雪融花|启程|爱与罪|剧本|同人|游记"),
    ("神学神性与信仰", r"神|神性|上帝|天使|宗教|基督|佛|信仰|圣|灵性|奇迹|创世|救世|弥赛亚|祈祷"),
    ("游戏与二次元文化", r"游戏|原神|steam|碧蓝|blue archive|崩坏|乙游|galgame|二次元|角色|cosplay|抽卡|星穹|明日方舟|vtuber|b站|哔哩"),
    ("社会观察与代际思考", r"社会|时代|00后|z世代|人类|文明|共产|资本|教育|内卷|阶层|穷人|富|国家|历史|未来|地球"),
    ("爱情与情感哲学", r"爱情|恋爱|情|心|灵魂|羁绊|告白|思念|孤独"),
]
def classify(rec):
    text = rec["name"] + " " + rec["body"]
    for cat, pat in RULES:
        if re.search(pat, text, re.IGNORECASE): return cat
    return "其他"

for d in data: d["cat"] = classify(d)

months = ["2026-04","2026-05","2026-06","2026-07","2026-08","2026-09"]
cats = [r[0] for r in RULES] + ["其他"]

# 1. 分类×月份交叉表
cross = defaultdict(lambda: defaultdict(int))
for d in data: cross[d["cat"]][d["mtime"]] += 1

# 2. 关键词演变（每月词频/万字）
KWS = ["爱","质点","协议","AI|人工智能|模型","神|神性|天使","治愈|疗愈|温暖|拯救","深渊|虚无|绝望","宇宙|量子|物理","数据集|训练|仓库","主播|直播|b站|bilibili","小说|章节","苦难|痛苦|原生家庭|霸凌","未来|希望"]
kw_month = {m: Counter() for m in months}
month_chars = Counter(m for m in [d["mtime"] for d in data])
for d in data:
    for kw in KWS:
        kw_month[d["mtime"]][kw] += len(re.findall(kw, d["body"], re.IGNORECASE))

# 3. 高频实体（专名类）
ENT = ["DeepSeek","ChatGPT","Grok","Claude","Gemini","Kimi","豆包","千问","文心","智谱","元宝","Neuro","Vedal","HuggingFace|拥抱脸|huggingface","ModelScope|魔塔","Zenodo","GitHub","B站|bilibili","小红书","番茄","雪融花","露露卡","昔涟","遐蝶","月香花","月莉莉","心音","忆爱","唯爱","白结","雨宫莲","白花","爱丽丝","星烬","虹爱","绽美","心爱的"]
ent_cnt = Counter()
for d in data:
    for e in ENT:
        if re.search(e, d["body"], re.IGNORECASE): ent_cnt[e.split("|")[0]] += 1

# 4. 每月字数/篇均
m_chars = defaultdict(int); m_cnt = defaultdict(int)
for d in data: m_chars[d["mtime"]] += d["chars"]; m_cnt[d["mtime"]] += 1

# 5. 标题模式
pat_about = sum(1 for d in data if d["name"].startswith("关于"))
pat_chap = sum(1 for d in data if re.search(r"第\d+章", d["name"]))

# 6. 各类前10高频词（2字+，去停用词）
STOP = set("一个我们你们他们这个那个就是可以什么没有自己所以但是因为现在时候知道觉得这些哪些还是以及不是已经这样那样生活时间世界问题事情可能大家其实然后如果如何东西对于因此其中表示成为通过以及所有一直一定起来出来时候这样".split())
def top_words(cat, k=14):
    c = Counter()
    for d in data:
        if d["cat"] != cat: continue
        for w in re.findall(r"[\u4e00-\u9fa5]{2,4}", d["body"]):
            if w not in STOP and len(w) >= 2: c[w] += 1
    return c.most_common(k)

out = {
    "total": len(data), "total_chars": sum(d["chars"] for d in data),
    "cross": {c: {m: cross[c].get(m, 0) for m in months} for c in cats},
    "kw_month": {m: {kw: round(kw_month[m][kw] * 10000 / max(month_chars[m], 1), 1) for kw in KWS} for m in months},
    "ents": ent_cnt.most_common(30),
    "monthly": {m: {"n": m_cnt[m], "chars": m_chars[m], "avg": round(m_chars[m]/max(m_cnt[m],1))} for m in months},
    "title_patterns": {"关于X": pat_about, "章节": pat_chap},
    "cat_words": {c: top_words(c) for c in cats},
}
json.dump(out, open(r"D:\双生天使的怀抱\.workbuddy\tmp_deep_stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved. categories:", {c: sum(cross[c].values()) for c in cats})
print("ents:", ent_cnt.most_common(15))
