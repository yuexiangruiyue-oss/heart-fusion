# -*- coding: utf-8 -*-
"""爱的创造 1177篇 全文提取 → tmp_love_full.jsonl"""
import os, json, sys
from docx import Document

SRC = r"D:\双生天使的怀抱\爱的创造"
OUT = r"D:\双生天使的怀抱\.workbuddy\tmp_love_full.jsonl"
from datetime import datetime

def ex_docx(p):
    d = Document(p)
    return " ".join(x.text.strip() for x in d.paragraphs if x.text.strip())

def ex_text(p):
    for enc in ("utf-8", "gbk"):
        try:
            with open(p, encoding=enc) as f: return f.read()
        except Exception: continue
    return ""

files = sorted(os.listdir(SRC))
n = 0
with open(OUT, "w", encoding="utf-8") as fo:
    for name in files:
        p = os.path.join(SRC, name)
        if not os.path.isfile(p): continue
        try:
            body = ex_docx(p) if name.lower().endswith(".docx") else ex_text(p)
        except Exception as e:
            body = f"__ERR__{e}"
        fo.write(json.dumps({
            "name": name, "chars": len(body), "body": body,
            "mtime": datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m"),
        }, ensure_ascii=False) + "\n")
        n += 1
        if n % 300 == 0: print(f"{n}/{len(files)}", file=sys.stderr, flush=True)
print(f"DONE {n}")
