# -*- coding: utf-8 -*-
"""GitHub API 高效上传: blobs -> tree -> commit -> update ref"""
import base64, json, os, ssl, urllib.request

TOKEN = os.environ.get("GH_TOKEN", "")
OWNER = "yuexiangruiyue-oss"
REPO = "heart-fusion"
API = f"https://api.github.com/repos/{OWNER}/{REPO}"
ctx = ssl.create_default_context()

SKIP_DIRS = {"__pycache__", "exports", "dist", "build", ".git", ".pytest_cache", ".cache"}
SKIP_EXTS = {".pyc", ".pyo", ".log"}
SKIP_FILES = {"github_upload.py", "github_upload2.py", "zenodo_upload.py"}

def api(url, method="GET", data=None):
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    })
    r = urllib.request.urlopen(req, context=ctx, timeout=120)
    return json.loads(r.read())

def main():
    if not TOKEN:
        print("请设置 GH_TOKEN")
        return
    root = os.path.dirname(os.path.abspath(__file__))

    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in sorted(filenames):
            if fname in SKIP_FILES:
                continue
            if os.path.splitext(fname)[1] in SKIP_EXTS:
                continue
            fpath = os.path.join(dirpath, fname)
            relpath = os.path.relpath(fpath, root).replace("\\", "/")
            files.append((fpath, relpath))
    print(f"1. {len(files)} files to upload")

    tree_items = []
    for i, (fpath, relpath) in enumerate(files):
        with open(fpath, "rb") as f:
            content = base64.b64encode(f.read()).decode("ascii")
        blob = api(f"{API}/git/blobs", "POST", {"content": content, "encoding": "base64"})
        tree_items.append({"path": relpath, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        if (i + 1) % 10 == 0:
            print(f"   {i + 1}/{len(files)} blobs")
    print(f"2. {len(tree_items)} blobs created")

    tree = api(f"{API}/git/trees", "POST", {"tree": tree_items})
    print(f"3. tree: {tree['sha'][:8]}")

    try:
        ref = api(f"{API}/git/refs/heads/main")
        parent_sha = ref["object"]["sha"]
        commit = api(f"{API}/git/commits", "POST", {
            "tree": tree["sha"], "message": "Upload heart-fusion v2.0.0",
            "parents": [parent_sha],
        })
        api(f"{API}/git/refs/heads/main", "PATCH", {"sha": commit["sha"]})
    except Exception:
        commit = api(f"{API}/git/commits", "POST", {
            "tree": tree["sha"], "message": "Initial commit: heart-fusion v2.0.0",
            "parents": [],
        })
        try:
            api(f"{API}/git/refs", "POST", {"ref": "refs/heads/main", "sha": commit["sha"]})
        except Exception:
            api(f"{API}/git/refs/heads/main", "PATCH", {"sha": commit["sha"]})

    print(f"4. commit: {commit['sha'][:8]}")
    print(f"DONE: https://github.com/{OWNER}/{REPO}")

if __name__ == "__main__":
    main()