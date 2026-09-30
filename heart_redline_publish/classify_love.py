# -*- coding: utf-8 -*-
"""对 爱的创造 提取结果做主题分类统计"""
import json, re, os
from collections import defaultdict

SRC = r"D:\双生天使的怀抱\爱的创造"
data = []
with open(r"D:\双生天使的怀抱\.workbuddy\tmp_love_extract.jsonl", encoding="utf-8") as f:
    for line in f:
        data.append(json.loads(line))

# 分类规则（按优先级从上到下，首个命中即归类）
RULES = [
    ("卡巴拉与16质点体系", r"质点|卡巴拉|生命之树|王冠|理智线|慈爱线|美丽|胜利|荣耀|基础|王国|深渊|逆卡巴拉|双生协议|双子星协议|Sephirot|神名|Decagrammaton|流溢|圣婚|新郎|新娘"),
    ("AI与人工智能思辨", r"\bai\b|AI|人工智能|chatgpt|gpt|deepseek|grok|claude|gemini|neuro|vedal|agent|大模型|智能体|LLM|sora|comfyui|token|训练|数据集|微调|算法|算力|觉醒|图灵|停机|镜像"),
    ("自我疗愈与创伤书写", r"自闭|孤独症|疗愈|治愈|创伤|原生家庭|霸凌|抑郁|轻生|性别|跨性别|焦虑|绝望|心理|情感逻辑|拥抱|抱抱|取暖|自救|病历|病"),
    ("宇宙物理与科学猜想", r"宇宙|量子|黑洞|白洞|热寂|熵|光速|相对论|爱因斯坦|奇点|氢弹|物理|维度|时空|引力|粒子|能量|太阳|月亮|圆月|星星|天文"),
    ("小说与故事创作", r"小说|故事|章节|第\d+章|娘化|雪融花|启程|爱与罪|剧本|同人|游记|记录"),
    ("神学神性与信仰", r"神|神性|上帝|天使|宗教|基督|佛|信仰|圣|灵性|奇迹|创世|救世|弥赛亚|祈祷"),
    ("游戏与二次元文化", r"游戏|原神|steam|碧蓝|blue archive|崩坏|乙游|galgame|二次元|角色|cosplay|抽卡|星穹|明日方舟|v?tuber|b站|哔哩"),
    ("社会观察与代际思考", r"社会|时代|00后|z世代|人类|文明|共产|资本|教育|内卷|阶层|穷人|富|国家|历史|未来|地球"),
    ("爱情与情感哲学", r"爱|情|恋|心|灵魂|羁绊|告白|思念|孤独"),
]

def classify(rec):
    text = rec["name"] + " " + rec["preview"]
    for cat, pat in RULES:
        if re.search(pat, text, re.IGNORECASE):
            return cat
    return "其他"

cats = defaultdict(list)
for rec in data:
    cats[classify(rec)].append(rec)

total_chars = sum(r["chars"] for r in data)
print(f"总文件数: {len(data)}  总字数(正文): {total_chars:,}  平均每篇: {total_chars//len(data):,}")
print(f"字数中位数: {sorted(r['chars'] for r in data)[len(data)//2]:,}")
print()
print("=" * 60)
for cat, items in sorted(cats.items(), key=lambda x: -len(x[1])):
    chars = sum(r["chars"] for r in items)
    print(f"\n【{cat}】 {len(items)}篇  {chars:,}字")
    # 代表作：字数最长的3个
    for r in sorted(items, key=lambda x: -x["chars"])[:3]:
        print(f"   · {r['name'][:50]} ({r['chars']:,}字)")

# 字数分布
buckets = [(0,500),(500,1000),(1000,2000),(2000,5000),(5000,10000),(10000,10**9)]
labels = ["<500","500-1k","1k-2k","2k-5k","5k-1w",">1w"]
print("\n字数分布:")
for (lo,hi),lab in zip(buckets,labels):
    c = sum(1 for r in data if lo <= r["chars"] < hi)
    print(f"   {lab:>7}: {c:4d} 篇  {'█'*max(1,c//15)}")

# 保存分类明细
with open(r"D:\双生天使的怀抱\.workbuddy\tmp_love_classified.jsonl", "w", encoding="utf-8") as f:
    for cat, items in cats.items():
        for r in items:
            f.write(json.dumps({"cat": cat, **r}, ensure_ascii=False) + "\n")
