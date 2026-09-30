# -*- coding: utf-8 -*-
"""
Zenodo 投稿脚本 — 上传论文 + 配图
"""
import json, os, ssl, sys, urllib.request, urllib.parse

TOKEN = os.environ.get("ZENODO_TOKEN", "")
BASE = "https://zenodo.org/api/deposit/depositions"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}
ctx = ssl.create_default_context()

def api(method, url, data=None, headers=None, raw=False):
    h = dict(HEADERS)
    if headers:
        h.update(headers)
    body = None
    if data is not None:
        body = data if raw else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    r = urllib.request.urlopen(req, context=ctx, timeout=120)
    return json.loads(r.read()) if r.headers.get("content-type","").startswith("application/json") else r.read()

def upload_file(deposition_id, filepath):
    url = f"{BASE}/{deposition_id}/files"
    filename = os.path.basename(filepath)
    boundary = "----zenodo_boundary"
    with open(filepath, "rb") as f:
        filedata = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + filedata + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    })
    r = urllib.request.urlopen(req, context=ctx, timeout=120)
    return json.loads(r.read())

def main():
    if not TOKEN:
        print("请设置 ZENODO_TOKEN 环境变量")
        return

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. 创建空 deposition
    print("1. 创建 deposition ...")
    dep = api("POST", BASE, data={})
    dep_id = dep["id"]
    print(f"   deposition_id = {dep_id}")

    # 2. 上传文件
    files = [
        "paper_fusion_v2_arxiv.md",
        "multi_turn_balance.png",
        "multi_turn_complex.png",
        "protocol_v2_whitepaper_en.md",
    ]
    for fname in files:
        fpath = os.path.join(base_dir, fname)
        if os.path.exists(fpath):
            print(f"2. 上传 {fname} ...")
            upload_file(dep_id, fpath)
            print(f"   OK")
        else:
            print(f"   跳过 {fname} (不存在)")

    # 3. 更新 metadata
    print("3. 更新 metadata ...")
    metadata = {
        "title": "Replacing argmax with Dual Coexistence: A Fusion-Function Cognitive Control Paradigm for Transformer Language Models",
        "upload_type": "publication",
        "publication_type": "article",
        "description": (
            "We identify a fundamental flaw in the Transformer output layer: argmax performs variable elimination "
            "— selecting one direction while discarding all others. In crisis support scenarios, this causes "
            "life-critical information loss (e.g., eliminating a suicide hotline from the output). "
            "We propose a fusion function based on complex-valued dual coexistence (z = a + i*b) that replaces argmax, "
            "preserving both opposing directions without loss. We prove that (1) the fusion function satisfies a "
            "no-variable-elimination (NVE) property while argmax does not, (2) the settle operator converges to the "
            "harmony band in bounded steps, and (3) the n-pole extension via normalized entropy preserves all poles. "
            "Cross-model validation on 6 LLMs (18 cases) confirms the fusion function is model-agnostic. "
            "A direct comparison with RLHF reveals that RLHF's soft constraints can be bypassed (1/4 harm requests "
            "not intercepted) while our hard redlines achieve 0 misses. "
            "The fusion function is imprinted onto four Transformer layers via the official LogitsProcessor interface. "
            "pip install heart-fusion."
        ),
        "creators": [
            {"name": "AngelWarmSmile", "affiliation": "Independent Researcher"}
        ],
        "keywords": [
            "dual coexistence", "fusion function", "variable elimination",
            "argmax replacement", "crisis support", "safety redline",
            "sephirot topology", "n-pole coexistence", "RLHF comparison",
        ],
        "access_right": "open",
        "license": "CC-BY-4.0",
        "language": "eng",
        "communities": [],
    }
    result = api("PUT", f"{BASE}/{dep_id}", data={"metadata": metadata})
    print(f"   metadata updated")

    # 4. 发布
    print("4. 发布 ...")
    try:
        pub = api("POST", f"{BASE}/{dep_id}/actions/publish", data={})
        doi = pub.get("doi", "unknown")
        print(f"   ✅ 发布成功!")
        print(f"   DOI: 10.5281/zenodo.{dep_id}")
        print(f"   URL: https://zenodo.org/record/{dep_id}")
    except Exception as e:
        print(f"   发布失败: {e}")
        print(f"   deposition_id = {dep_id} (可手动发布)")
        print(f"   URL: https://zenodo.org/deposit/{dep_id}")

if __name__ == "__main__":
    main()