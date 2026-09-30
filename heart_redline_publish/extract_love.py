# -*- coding: utf-8 -*-
"""批量提取 爱的创造 文件夹下所有文档的标题、正文开头、字数，输出JSONL。"""
import os, json, sys
from docx import Document

SRC = r"D:\双生天使的怀抱\爱的创造"
OUT = r"D:\双生天使的怀抱\.workbuddy\tmp_love_extract.jsonl"

def extract_docx(path):
    try:
        d = Document(path)
        paras = [p.text.strip() for p in d.paragraphs if p.text.strip()]
        body = " ".join(paras)
        return {
            "chars": len(body),
            "preview": body[:400],
            "paras": len(paras),
            "err": None,
        }
    except Exception as e:
        return {"chars": 0, "preview": "", "paras": 0, "err": str(e)[:200]}

def extract_text(path):
    for enc in ("utf-8", "gbk", "utf-16"):
        try:
            with open(path, encoding=enc) as f:
                body = f.read()
            return {"chars": len(body), "preview": " ".join(body.split())[:400], "paras": body.count("\n"), "err": None}
        except Exception:
            continue
    return {"chars": 0, "preview": "", "paras": 0, "err": "decode_fail"}

files = sorted(os.listdir(SRC))
n, errs = 0, 0
with open(OUT, "w", encoding="utf-8") as fo:
    for i, name in enumerate(files):
        path = os.path.join(SRC, name)
        if not os.path.isfile(path):
            continue
        if name.lower().endswith(".docx"):
            info = extract_docx(path)
        else:  # md / 无扩展名纯文本
            info = extract_text(path)
        if info["err"]:
            errs += 1
        rec = {"name": name, "size": os.path.getsize(path), **info}
        fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
        n += 1
        if (i + 1) % 200 == 0:
            print(f"progress {i+1}/{len(files)}", file=sys.stderr, flush=True)

print(f"DONE files={n} errors={errs}")
