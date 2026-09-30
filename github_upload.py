# -*- coding: utf-8 -*-
"""GitHub API 批量上传文件到仓库"""
import base64, json, os, ssl, sys, urllib.request

TOKEN = os.environ.get("GH_TOKEN", "")
OWNER = "yuexiangruiyue-oss"
REPO = "heart-fusion"
BASE = f"https://api.github.com/repos/{OWNER}/{REPO}/contents"
ctx = ssl.create_default_context()

SKIP_DIRS = {"__pycache__", "exports", "dist", "build", ".git", ".pytest_cache", ".cache"}
SKIP_EXTS = {".pyc", ".pyo", ".log", ".egg-info"}
SKIP_FILES = {".gitignore"}

def upload_file(local_path, repo_path):
    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("ascii")
    body = json.dumps({"message": f"Add {repo_path}", "content": content}).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/{repo_path}", data=body, method="PUT", headers={
        "Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    })
    try:
        r = urllib.request.urlopen(req, context=ctx, timeout=60)
        return True
    except Exception as e:
        if "422" in str(e):
            return True  # already exists
        return False

def main():
    if not TOKEN:
        print("请设置 GH_TOKEN")
        return
    root = os.path.dirname(os.path.abspath(__file__))
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if fname in SKIP_FILES:
                continue
            ext = os.path.splitext(fname)[1]
            if ext in SKIP_EXTS:
                continue
            fpath = os.path.join(dirpath, fname)
            relpath = os.path.relpath(fpath, root).replace("\\", "/")
            print(f"  {relpath}", end=" ")
            if upload_file(fpath, relpath):
                print("OK")
                count += 1
            else:
                print("FAIL")
    print(f"\n上传完成: {count} 个文件")

if __name__ == "__main__":
    main()