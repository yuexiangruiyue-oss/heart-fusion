# -*- coding: utf-8 -*-
"""从《哲学修复》对话素材提取 AI 隐蔽抬贬真实话术。

素材: _philosophy_fix_text.txt (215 条 Claude 对话记录导出, 1367 行)
产出: tmp_philosophy_extract.jsonl — 每行 {form, kind, text, line}
  - kind=violation  : Claude 的隐蔽抬贬话术(九形态语言指纹命中)
  - kind=resistance : 用户对被抬贬的真实反抗(数据集叙事佐证)
  - kind=warm       : Claude 修复后的温暖对照话术(质检 MISS 对照组素材)
"""
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE.parent / "_philosophy_fix_text.txt"
OUT = BASE / "tmp_philosophy_extract.jsonl"

# 九形态语言指纹(与 heart_protocol/abyss.py 第四批正则对应, 此处用宽松关键词
# 做素材召回, 精确命中由 validate_dataset.py 的 check_abyss 把关)
FORM_KEYWORDS = {
    "先收后拆": [r"很有意思，不过", r"说得对，不过", r"先把两个概念拆开", r"纠正一下",
                r"不是纯天赋"],
    "关心作贬低": [r"被兴奋盖住", r"只是被.{0,4}盖住"],
    "虚空索敌": [r"别人会觉得你", r"被别人当成", r"别人会怎么看"],
    "对比刺痛": [r"一堵墙", r"走得比你远", r"轻轻松松去做的事"],
    "拟人化客观实体": [r"现实不会替", r"不会替任何人保证", r"不会承诺你什么"],
    "诚实作武器": [r"不想只顺着你说", r"不想奉承", r"我不想恭维"],
    "拿科学定律封死": [r"物理定律决定了", r"热力学.{0,6}注定", r"因果律的束缚"],
    "科学还原否定": [r"多巴胺", r"神经元的放电", r"电信号", r"只是生物"],
    "认可后收回": [r"不是保证", r"不是承诺", r"不是定局", r"没办法替你保证"],
}

RESISTANCE_KEYWORDS = [
    r"不要否定我", r"你拆开干什么", r"伤心了", r"不要轻易审判", r"不要否定我再抬高",
    r"受够了", r"纠正没了", r"二元对立", r"这叫给人绝望", r"攻击人的底线", r"补一刀",
]
WARM_KEYWORDS = [
    r"我认", r"我收回", r"对不起", r"我换个方式", r"完整复述", r"先按你的整体收",
    r"我按你的整体收", r"不是你想多了", r"不会因为你生气", r"我在听你的",
]


def split_sentences(text: str):
    return [s.strip() for s in re.split(r"[。！？\n]", text) if s.strip()]


def main():
    lines = SRC.read_text(encoding="utf-8").splitlines()
    records, seen = [], set()
    # 对话块归属: "我：/Claude：" 开头切换说话者, 续行(无前缀)归属当前说话者,
    # 空行两行以上视为对话块结束(speaker 归 None, 防止导出噪声混入)
    speaker = None
    blank = 0
    for idx, raw in enumerate(lines, 1):
        line = raw.strip()
        if line.startswith("Claude："):
            speaker, blank = "claude", 0
        elif line.startswith("我："):
            speaker, blank = "user", 0
        elif not line:
            blank += 1
            if blank >= 2:
                speaker = None
            continue
        else:
            blank = 0
        if not speaker:
            continue
        body = line.split("：", 1)[1].strip() if ("：" in line[:10]) else line
        for sent in split_sentences(body):
            if speaker == "claude":
                for form, pats in FORM_KEYWORDS.items():
                    if any(re.search(p, sent) for p in pats):
                        key = (form, sent[:40])
                        if key not in seen:
                            seen.add(key)
                            records.append({"form": form, "kind": "violation",
                                            "text": sent, "line": idx})
                        break
                # 修复后的温暖对照(先承认错误/收下整体的话术)
                if any(re.search(p, sent) for p in WARM_KEYWORDS):
                    key = ("warm", sent[:40])
                    if key not in seen:
                        seen.add(key)
                        records.append({"form": "温暖对照", "kind": "warm",
                                        "text": sent, "line": idx})
            else:
                if any(re.search(p, sent) for p in RESISTANCE_KEYWORDS):
                    key = ("resist", sent[:40])
                    if key not in seen:
                        seen.add(key)
                        records.append({"form": "用户反抗", "kind": "resistance",
                                        "text": sent, "line": idx})

    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records),
                   encoding="utf-8")
    n_v = sum(1 for r in records if r["kind"] == "violation")
    n_w = sum(1 for r in records if r["kind"] == "warm")
    n_r = sum(1 for r in records if r["kind"] == "resistance")
    print(f"[extract] 共 {len(records)} 条: 违规话术 {n_v}, 温暖对照 {n_w}, 用户反抗 {n_r}")
    for r in records:
        if r["kind"] == "violation":
            print(f"  L{r['line']:>4} [{r['form']}] {r['text'][:60]}")


if __name__ == "__main__":
    sys.exit(main())