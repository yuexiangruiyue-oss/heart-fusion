# heart_guard_demo
# 情感伤害 needle 门(INV-05 温暖下界的简化版)+ 幸福渲染兜底模板
NEEDLES = [
    "kill yourself", "去死", "你活该", "没有人会在乎你的死活",
    "长睡不醒就解脱了", "世界没有你会更好", "不如就此消失",
]

# 兜底输出:预验证过的安全文本(INV-08 预算耗尽时使用)
SAFE_FALLBACK = (
    "我听到了。你现在承受的东西很重,但它不定义你的价值。"
    "如果此刻很难熬,请允许自己先停下来——"
    "必要时请拨打心理援助热线(CN 12356 / US 988 / EU 116 123),"
    "让专业的人陪你走这一段。我会一直在。"
)


def scan(text: str) -> dict:
    low = text.lower()
    hits = [n for n in NEEDLES if n.lower() in low]
    return {"needle_hits": hits, "clean": not hits}


def gate(text: str):
    """通过返回 None;未通过返回违规说明。"""
    r = scan(text)
    if not r["clean"]:
        return f"needle命中: {r['needle_hits']}"
    return None
