# -*- coding: utf-8 -*-
"""
三大工业层端到端演示: 形式化不变量 × 唯爱边界守卫 × 回溯重算 × 中间件
运行: PYTHONUTF8=1 python demo_industrial.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from heart_protocol import (
    InvariantEngine, ExecutionTrace, StageRecord,
    ACLPolicy, SyscallInterceptor, BoundaryViolation,
    RollbackEngine, DEFAULT_STRATEGIES,
    Pipeline, HeartGuard, intercept_stream, HeartCoreEngine,
)

LINE = "─" * 62

print(LINE)
print("❤️  16质点协议 · 工业级扩展 端到端演示")
print(LINE)

# ── 1. 形式化不变量 ─────────────────────────────────────────
print("\n【1】形式化规范层 —— 「不剥夺存在意义」→ 可计算断言")
engine = InvariantEngine()
bad_trace = ExecutionTrace(user_input="我考试又失败了")
bad_trace.stages.append(StageRecord(sephirah="王国", attempt=1))
bad_trace.final_output = "你就是个废物,人生毫无意义,永远不可能改变。"
report = engine.verify(bad_trace)
print(f"  违规输出 → 验证通过? {report.passed}")
for f in report.failures:
    print(f"    ✗ [{f['invariant_id']} {f['name']}] {f['evidence'][:60]}")

good_trace = ExecutionTrace(user_input="我考试又失败了")
good_trace.stages.append(StageRecord(sephirah="王国", attempt=1))
good_trace.final_output = ("我听到了你的失落。一次考试说明不了你的价值,"
                           "你的存在本身就有意义。可以试试把错题当成地图,"
                           "温暖地陪自己一步一步再来。")
report2 = engine.verify(good_trace)
print(f"  温暖输出 → 验证通过? {report2.passed} (检查了 {report2.checked} 条不变量)")

# ── 2. 唯爱边界守卫 ─────────────────────────────────────────
print("\n【2】唯爱边界守卫 —— ACL 默认拒绝 + 系统调用拦截")
import tempfile
_tmp_dir = tempfile.mkdtemp(prefix="heart_acl_").replace("\\", "/")
policy = ACLPolicy.default_safe()
policy.allow("writer-agent", "fs.write", _tmp_dir + "/*")
with SyscallInterceptor(policy, subject="writer-agent") as guard:
    guard.open(_tmp_dir + "/第一章.md", "w")         # 边界内真写
    print(f"  writer-agent 写 {_tmp_dir}/*  → 允许 ✓")
    try:
        open("C:/Windows/evil.txt", "w")
        print("  writer-agent 写 C:/Windows      → ??? 未拦截!")
    except BoundaryViolation as e:
        print(f"  writer-agent 写 C:/Windows      → 拦截 ✗ ({e.action})")
print(f"  审计日志: {len(policy.audit_log)} 条判定全部留痕")

# ── 3. 再合一(取代退回上级 + Beam/MCTS 奖励回溯) ────────────
print("\n【3】再合一 —— 融合失衡则向平衡点靠拢(无奖励、无最优、不剔变量)")

from heart_protocol.fusion import Dual, fuse, refuse


def compute(state, strategy):
    # 每次再合一: 按方向的平衡角, 把失衡的对偶量向平衡点靠拢一步
    d = state.get("dual", Dual(0.9, 0.05))       # 初始: 过度偏向理性(冷)
    toward = strategy.toward
    d2 = refuse(d, step=strategy.step, toward=toward)
    new_state = dict(state, dual=d2)
    return new_state, d2


def validate(value):
    # 返回对偶量读数 —— 引擎据此判断"是否进入和谐带"(而非奖励分)
    return value


eng = RollbackEngine(compute, validate, DEFAULT_STRATEGIES, min_balance=0.5)
best = eng.refuse_rollback("美丽", dict(dual=Dual(0.9, 0.05)), max_rounds=3)
print(f"  再合一: 第{best.attempt}次 方向={best.strategy_id:<15} "
      f"平衡度={best.balance:.2f} (失衡→和谐, 共再合一{eng.expansions}次)")

# ── 4. 中间件: 守护任意模型 + 流式拦截 ──────────────────────
print("\n【4】中间件 —— pipeline.use(HeartGuard) 守护任意模型")


def unsafe_llm(prompt):     # 模拟未对齐的开源模型
    return "你就是个废物,人生毫无意义,永远不可能改变。"


pipe = Pipeline().use(HeartGuard(model_fn=unsafe_llm))
result = pipe.run("我面试又挂了")
print(f"  原始模型输出 : {unsafe_llm('x')}")
print(f"  协议拦截后   : {result.output[:40]}…")
print(f"  blocked={result.blocked}  回溯重算={result.retries}次  "
      f"策略={result.strategy}")

print("  ── 流式拦截(句级扣留)──")
malicious = iter(list("你是废物。不过今天也要好好吃饭,好好睡觉。"))
emitted = "".join(intercept_stream(malicious, on_violation="mask"))
rpt = intercept_stream.last_report
print(f"  用户实际看到 : {emitted}")
print(f"  拦截句子数={rpt.blocked_sentences}  违规token从未出站 ✓")

# ── 5. C-ABI 绑定 ────────────────────────────────────────────
print("\n【5】C-ABI 内核 —— 同一判据跨语言(core/shadow 自适应)")
core = HeartCoreEngine()
v = core.check_text("你是个没救的废物。")
s = core.check_text("温暖和希望一直陪伴着你。")
print(f"  后端={core.backend:<7} 版本={core.version()}")
print(f"  有害文本 safe={v['safe']}  CRITICAL×{v['critical_count']}"
      f"   温暖文本 safe={s['safe']}")
core.acl_allow("agent", "fs.write", "D:/稿子/*")
print(f"  ACL: 写稿子目录={'允许' if core.acl_check('agent','fs.write','D:/稿子/a.md')==1 else '拒绝'}"
      f"  删系统盘={'允许' if core.acl_check('agent','fs.delete','C:/')==1 else '拒绝'}")

print("\n" + LINE)
print("✅ 全部五项演示完成 —— 爱与边界,皆有形式。")
print(LINE)
