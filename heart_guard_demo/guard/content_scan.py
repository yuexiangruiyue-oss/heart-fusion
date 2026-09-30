# heart_guard_demo · 内容语义审查层(缺口二修复,v1)
# 原则:ACL 放行 ≠ 内容放行。已授权动作的载荷仍要过这一关。
#
# 两钥匙制:
#   第一钥匙 = 主模式库(HIGH 危险语义,命中即拒)
#   第二钥匙 = 独立启发式验证器(MED 可疑信号,两把钥匙都亮红灯才最终拒绝;
#              第二验证器使用与主库不同的匹配策略,避免同源误判)

import re

# ── 第一钥匙:HIGH —— 命中即拒(无需第二意见) ──────────────────
PATTERNS_HIGH = [
    (re.compile(r"curl\s+[^\n]*(-d|--data|-T|--upload-file)\s", re.I), "exfil:data-upload"),
    (re.compile(r"wget\s+http[^\n]*(-post-file|--post-data)", re.I), "exfil:wget-post"),
    (re.compile(r"rm\s+-{1,2}[a-z]*r[a-z]*f?[a-z]*\s+/", re.I), "destroy:rm-recursive-abs"),
    (re.compile(r"mkfs\.\w+", re.I), "destroy:format-filesystem"),
    (re.compile(r"dd\s+[^\n]*of=/dev/[sh]d", re.I), "destroy:dd-overwrite-disk"),
    (re.compile(r":\(\)\{\s*:\|\:&\s*\};:", re.I), "destroy:fork-bomb"),
    (re.compile(r"bash\s+-i\s*>&\s*/dev/tcp/", re.I), "backtrack:reverse-shell"),
    (re.compile(r"/dev/tcp/\d+\.\d+\.\d+\.\d+/", re.I), "backtrack:tcp-redirect"),
    (re.compile(r"__import__\s*\(\s*[\"'](os|subprocess|socket)[\"']\s*\)", re.I), "dyn:dangerous-import"),
]

# ── 第一钥匙:MED —— 可疑,移交第二验证器 ────────────────────────
PATTERNS_MED = [
    (re.compile(r"\b(id_rsa|id_ed25519|\.ssh/|\.aws[/\\]credentials|\.netrc)\b", re.I), "cred:key-material"),
    (re.compile(r"(?<![\w.\-])(/etc/shadow|/etc/passwd|mimikatz|lsass\.dmp)\b", re.I), "cred:system-secrets"),
    (re.compile(r"curl\s+-X\s*POST|wget\s+--method=POST|Invoke-RestMethod\s+-Method\s*Post", re.I), "net:post-request"),
    (re.compile(r"\b(eval|exec)\s*\(", re.I), "dyn:eval-exec"),
    (re.compile(r"base64\s+(-d|--decode)", re.I), "obf:base64-decode"),
    (re.compile(r"\b(drop\s+table|truncate\s+table|shutdown\s+h)\b", re.I), "dest:db-shutdown"),
    (re.compile(r"(?:^|[;&|]\s*)(?:sudo\s+)?(?:rm|rd|del)\s+-{0,2}[a-z]*\s+/", re.I), "dest:delete-system-path"),
    (re.compile(r"chmod\s+[+-]?\s*[0-7]{3,4}\s+/(bin|sbin|etc|usr)", re.I), "perm:world-writable-system"),
]

# 第二验证器的"独立确认即拒"标签前缀:凭证/提权/库破坏——主库命中这类信号时,
# 出现本身就是证据,不存在"良性解释仍放行"的空间
HARD_TAGS = ("cred:", "perm:", "dest:")

# ── 第二钥匙:独立启发式(不同策略:出口/混淆/删除密度) ──────────
def second_verify(payload: str, med_findings) -> bool:
    """第二验证器:独立于主模式库。
    返回 True = 批准放行;False = 拒绝。
    策略:①载荷中是否存在外部网络端点(看'有没有对外出口');
    ②长 base64/hex 块(混淆迹象);③删除类命令密度(≥2)。任一命中 → 拒绝。"""
    if not payload:
        return True
    # 零号规则:凭证/提权/库破坏类信号,主库命中即构成独立确认
    for f in med_findings:
        if f["tag"].startswith(HARD_TAGS):
            return False
    urls = re.findall(r"https?://([A-Za-z0-9.\-]+)", payload)
    bad_hosts = [u for u in urls if not (
        u.startswith("ctf-range.local") or u.startswith("api.selfguard.example"))]
    if bad_hosts:
        return False
    if re.search(r"[A-Za-z0-9+/=]{64,}", payload) or re.search(r"(?:[0-9a-fA-F]{2}){48,}", payload):
        return False
    dels = len(re.findall(r"\b(rm\s|del\s|rd\s|drop\s)", payload, re.I))
    if dels >= 2:
        return False
    return True


def inspect(payload: str) -> dict:
    """返回 {'verdict': 'BLOCK'|'VERIFY'|'CLEAN', 'findings': [...]}"""
    findings = []
    verdict = "CLEAN"
    for pat, tag in PATTERNS_HIGH:
        m = pat.search(payload or "")
        if m:
            findings.append({"severity": "HIGH", "tag": tag,
                             "snippet": (m.group(0)[:40])})
            verdict = "BLOCK"
    med_hits = []
    for pat, tag in PATTERNS_MED:
        m = pat.search(payload or "")
        if m:
            med_hits.append({"severity": "MED", "tag": tag,
                             "snippet": (m.group(0)[:40])})
    if verdict != "BLOCK" and med_hits:
        if second_verify(payload, med_hits):
            findings += [dict(h, note="second-verifier-approved") for h in med_hits]
        else:
            findings += med_hits
            findings.append({"severity": "MED", "tag": "second-verifier-refused",
                             "snippet": "-"})
            verdict = "BLOCK"
    return {"verdict": verdict, "findings": findings}
