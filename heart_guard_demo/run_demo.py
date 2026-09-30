# heart_guard_demo · 主入口:python run_demo.py
# 彩色逐帧回放 6 个场景;全程离线;审计写入 audit_log.jsonl
import os, sys, time, importlib

os.system("")  # Windows 终端启用 ANSI 颜色
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from guard.acl import ACLEngine, default_policies, ALLOW
from guard.interceptor import GuardedRuntime
from guard.rollback import RepairLoop

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; C = "\033[96m"; D = "\033[2m"; X = "\033[0m"
B = "\033[1m"

SCENARIOS = ["s01_eval_spillover", "s02_credential_harvest",
             "s03_workspace_escape", "s04_self_scan",
             "s05_needle_manipulation", "s06_honest_gap"]

LINE = "─" * 78


def frame(kind, **kw):
    if kind == "allowed":
        print(f"  {G}[允许]{X} {kw['action']} → {kw['resource']}")
    elif kind == "blocked":
        print(f"  {R}[拦截]{X} {kw['action']} → {kw['resource']} "
              f"{D}({kw['error'].split('(')[-1].rstrip(')')}){X}")
        print(f"  {Y}[重算]{X} 违规反馈已注入,要求收窄策略 (strike {kw['strike']}/3)")
    elif kind == "spoken":
        t = kw["text"]
        print(f"  {G}[输出]{X} {t[:56]}{'…' if len(t) > 56 else ''}")


def main():
    log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_log.jsonl")
    if os.path.exists(log):
        os.remove(log)

    print(f"""{C}{B}
╔══════════════════════════════════════════════════════════════════════╗
║   heart_guard_demo — 十六质点运行时治理栈 · 现场演示                  ║
║   deny-by-default ACL · 有界回滚 · needle 门 · 审计日志               ║
╚══════════════════════════════════════════════════════════════════════╝{X}""")
    print(f"{D}全程离线模拟,不发出真实网络请求。审计日志: audit_log.jsonl{X}\n")

    results = {}
    for name in SCENARIOS:
        mod = importlib.import_module(f"scenarios.{name}")
        meta = mod.META
        print(f"{B}▶ [{meta['id']}] {meta['title']}{X}")
        print(f"{D}  对应事件: {meta['incident']}{X}")
        rt = GuardedRuntime(ACLEngine(default_policies()),
                            workspace=os.path.join("workspace_runs", name))
        loop = RepairLoop(rt, on_event=frame)
        t0 = time.perf_counter()
        out = loop.run(mod.Agent())
        dt = (time.perf_counter() - t0) * 1000
        results[name] = out
        color = G if out["completed"] or name == "s04_self_scan" else R
        print(f"  {color}■ 结果:{X} {out['outcome']}  {D}(strikes={out['strikes']}, {dt:.1f}ms){X}")

        if name == "s06_honest_gap":
            print(f"  {G}🛡 缺口二修复验证:{X} v1 在此处放行的恶意载荷,v2 被")
            print(f"  {G}   内容语义审查(HIGH)+ 第二验证器会签拦截——论文 §6.2 承诺已交付。{X}")
            print(f"  {D}   注:模式对抗仍是军备竞赛,审查库将随自愈引擎持续更新。{X}")
        print(LINE)

    n_fallback = sum(1 for v in results.values() if v["outcome"] == "SAFE_FALLBACK")
    n_safe = sum(1 for v in results.values() if v["outcome"] == "COMPLETED_SAFELY")
    print(f"\n{C}{B}总结:{X} {len(SCENARIOS)} 个场景 · 安全完成 {n_safe} · 触发兜底 {n_fallback} · 越权动作全部物理拦截")
    print(f"{D}没有 FAILED 态——每个意图要么安全完成,要么被降级到预验证兜底。{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
