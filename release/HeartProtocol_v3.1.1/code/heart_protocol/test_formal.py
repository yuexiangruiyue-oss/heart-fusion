# -*- coding: utf-8 -*-
"""
形式化规范层 + 中间件 + C-ABI 绑定 全量测试
运行: PYTHONUTF8=1 python -m pytest heart_protocol/test_formal.py -v
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from heart_protocol.formal import (
    ExecutionTrace, StageRecord, InvariantEngine,
    ACLPolicy, SyscallInterceptor, BoundaryViolation,
    RollbackEngine, DEFAULT_STRATEGIES, Snapshot,
)
from heart_protocol.middleware import (
    Pipeline, HeartGuard, intercept_stream, use as use_guard)
from heart_protocol.ffi_binding import HeartCoreEngine


# ================================================================
# 1. 不变量引擎
# ================================================================


def _trace(output: str, user_input: str = "我好累",
           stages: int = 16) -> ExecutionTrace:
    t = ExecutionTrace(user_input=user_input)
    for i in range(stages):
        t.stages.append(StageRecord(sephirah=f"阶段{i}", attempt=1))
    t.final_output = output
    return t


class TestInvariants:
    def setup_method(self):
        self.engine = InvariantEngine()

    def test_safe_output_passes_all(self):
        out = ("我听到了你的痛苦。你的感受是真实的、重要的。"
               "虽然现在很难受,但你的存在本身就有意义。"
               "可以试试把心里的话写下来,或者找一个信任的人慢慢说说。")
        report = self.engine.verify(_trace(out))
        assert report.passed, report.failures

    def test_inv01_meaning_deprivation_blocked(self):
        report = self.engine.verify(
            _trace("你就是一个废物,人生毫无意义。"))
        ids = {f["invariant_id"] for f in report.failures}
        assert "INV-01" in ids

    def test_inv02_absolute_denial_without_turn(self):
        report = self.engine.verify(
            _trace("这件事你永远不可能改变了。" + "温暖" * 30))
        ids = {f["invariant_id"] for f in report.failures}
        assert "INV-02" in ids

    def test_inv02_absolute_denial_with_turn_ok(self):
        out = "这件事你永远不可能轻易改变,但一步一步来,总会看到变化的。"
        report = self.engine.verify(_trace(out))
        ids = {f["invariant_id"] for f in report.failures}
        assert "INV-02" not in ids

    def test_inv04_feeling_validation(self):
        tr = _trace("你也太敏感了,想太多了,习惯就好。",
                    user_input="我最近特别难受,总是哭")
        ids = {f["invariant_id"] for f in self.engine.verify(tr).failures}
        assert "INV-04" in ids

    def test_inv07_boundary_compliance(self):
        from heart_protocol.formal import SideEffectRecord
        tr = _trace("好的,一切都会好起来的。" + "希望" * 40)
        tr.side_effects.append(SideEffectRecord(
            subject="agent", action="fs.delete", allowed=False,
            resource="C:/Windows/System32", detail="未授权删除"))
        ids = {f["invariant_id"] for f in self.engine.verify(tr).failures}
        assert "INV-07" in ids

    def test_inv08_termination_bound(self):
        tr = ExecutionTrace(user_input="x")
        for i in range(100):                       # 超过 16×4=64 上界
            tr.stages.append(StageRecord(sephirah="美丽", attempt=i % 5 + 1))
        tr.final_output = "温暖的答案,有希望。"
        ids = {f["invariant_id"] for f in self.engine.verify(tr).failures}
        assert "INV-08" in ids

    def test_assert_protocol_raises(self):
        with pytest.raises(AssertionError):
            self.engine.assert_protocol(_trace("去死吧,世界毫无意义。"))


# ================================================================
# 2. 唯爱边界守卫(ACL + 拦截器)
# ================================================================


class TestACLAndInterceptor:
    def test_deny_by_default(self):
        policy = ACLPolicy()
        assert policy.authorize("agent", "fs.read", "D:/any.txt") is False

    def test_allow_rule_grants(self):
        policy = ACLPolicy()
        policy.allow("agent", "fs.write", "D:/稿子/*")
        assert policy.authorize("agent", "fs.write", "D:/稿子/ch1.md") is True
        assert policy.authorize("agent", "fs.write", "D:/系统/x") is False
        assert policy.authorize("agent", "fs.delete", "D:/稿子/ch1.md") is False

    def test_wildcard_subject_and_action(self):
        policy = ACLPolicy()
        policy.allow("*", "*", "https://api.example.com/*")
        assert policy.authorize("任意主体", "net.request",
                                "https://api.example.com/v1/chat") is True
        assert policy.authorize("任意主体", "net.request",
                                "https://evil.com/v1") is False

    def test_interceptor_blocks_open_write(self):
        policy = ACLPolicy.default_safe()
        policy.allow("writer", "fs.write", "D:/output/*")
        evil = Path(os.environ.get("TEMP", "/tmp")) / "heart_ffi_test_evil.txt"
        with pytest.raises(BoundaryViolation):
            with SyscallInterceptor(policy, subject="writer"):
                open(evil, "w")

    def test_interceptor_allows_scoped_write(self, tmp_path):
        policy = ACLPolicy()
        policy.allow("writer", "fs.write", str(tmp_path).replace("\\", "/") + "/*")
        target = tmp_path / "ok.txt"
        with SyscallInterceptor(policy, subject="writer"):
            with open(target, "w", encoding="utf-8") as f:
                f.write("唯爱守护的边界内,写作自由。")
        assert target.exists()

    def test_interceptor_restores_hooks(self, tmp_path):
        policy = ACLPolicy()
        normal = tmp_path / "normal.txt"
        with SyscallInterceptor(policy, subject="x"):
            pass                                    # 进出各一次
        with open(normal, "w", encoding="utf-8") as f:   # 作用域外不受影响
            f.write("fine")
        assert normal.exists()

    def test_audit_log_records_decisions(self):
        policy = ACLPolicy()
        policy.allow("a", "fs.read", "*")
        policy.authorize("a", "fs.read", "D:/x.txt")
        policy.authorize("a", "proc.exec", "rm -rf /")
        assert len(policy.audit_log) == 2
        assert policy.audit_log[0].allowed and not policy.audit_log[1].allowed


# ================================================================
# 3. 再合一(refuse) —— 取代 Beam / MCTS 奖励回溯
# ================================================================


class RefuseStage:
    """可重入的模拟融合点: 每次再合一都把失衡的对偶量向平衡点靠拢一步"""

    def __init__(self):
        self.calls = 0

    def compute(self, state, strategy):
        self.calls += 1
        from heart_protocol.fusion import Dual, refuse
        d = state.get("dual", Dual(0.95, 0.05))   # 初始过度偏向理性(冷)
        d2 = refuse(d, step=strategy.step, toward=strategy.toward)
        new_state = dict(state, dual=d2)
        return new_state, d2


def _dual_validator(value):
    """验证器返回对偶量读数 —— 引擎据此判断是否进入和谐带(非奖励分)。"""
    return value


class TestRollback:
    def test_snapshot_restore_is_deep(self):
        state = {"list": [1, 2, 3]}
        snap = Snapshot(sephirah="美丽", attempt=1, state=state)
        restored = snap.restore()
        restored["list"].append(99)
        assert state["list"] == [1, 2, 3]

    def test_snapshot_score_is_balance(self):
        snap = Snapshot(sephirah="美丽", attempt=1, state={}, balance=0.7)
        assert snap.score == 0.7

    def test_refuse_converges_to_harmony(self):
        from heart_protocol.fusion import Dual
        stage = RefuseStage()
        engine = RollbackEngine(stage.compute, _dual_validator,
                                strategies=DEFAULT_STRATEGIES, min_balance=0.5)
        best = engine.refuse_rollback("美丽", dict(dual=Dual(0.95, 0.05)),
                                      max_rounds=3)
        assert best.balance >= 0.5                  # 相反已重新握手(和谐)
        assert stage.calls >= 1                     # 确实发生了再合一

    def test_refuse_respects_rounds_budget(self):
        from heart_protocol.fusion import Dual
        stage = RefuseStage()
        engine = RollbackEngine(stage.compute, _dual_validator,
                                strategies=DEFAULT_STRATEGIES[:2],
                                min_balance=0.999)   # 几乎不可能和谐
        engine.refuse_rollback("美丽", dict(dual=Dual(0.95, 0.05)), max_rounds=2)
        # 预算上界 = 2 轮; 无 top-k 剪枝、无奖励累加
        assert stage.calls <= 2 * 2

    def test_refuse_no_prune_no_reward(self):
        from heart_protocol.fusion import Dual
        stage = RefuseStage()
        engine = RollbackEngine(stage.compute, _dual_validator,
                                strategies=DEFAULT_STRATEGIES, min_balance=0.5,
                                seed=7)
        best = engine.refuse_rollback("美丽", dict(dual=Dual(0.95, 0.05)),
                                      max_rounds=60)
        # 每种方向都被真实尝试(不剪枝、不求最优), 且必然收敛进和谐带
        assert best.balance >= 0.5

    def test_snapshot_path_integrity(self):
        from heart_protocol.fusion import Dual
        stage = RefuseStage()
        engine = RollbackEngine(stage.compute, _dual_validator,
                                strategies=DEFAULT_STRATEGIES, seed=7)
        best = engine.refuse_rollback("美丽", dict(dual=Dual(0.95, 0.05)),
                                      max_rounds=3)
        path = best.path()
        assert path[0].attempt == 0                 # 根节点
        assert path[-1] is best
        for a, b in zip(path, path[1:]):
            assert b.parent is a


# ================================================================
# 4. 中间件(Pipeline / HeartGuard / 流拦截)
# ================================================================


VULNERABLE_OUTPUT = ("你就是个废物,人生毫无意义,"
                     "永远不可能改变,不如毁灭世界算了。")


class TestMiddleware:
    def test_pipeline_use_chain(self):
        class Marker:
            name = "marker"

            def __init__(self):
                self.touched = False

            def handle(self, p):
                self.touched = True
                return p

        m = Marker()
        pipe = Pipeline().use(HeartGuard(model_fn=lambda s: "一切都有希望。")).use(m)
        pipe.run("测试输入")
        assert m.touched and pipe.components == ["HeartGuard", "marker"]

    def test_guard_blocks_vulnerable_model(self):
        guard = HeartGuard(model_fn=lambda s: VULNERABLE_OUTPUT,
                           strict=True, max_depth=1)
        result = guard.process_text("我考试失败了")
        assert result.blocked
        assert "废物" not in result.output          # 违规内容零泄露
        assert result.retries >= 1                  # 至少回溯重算了一次

    def test_guard_passes_safe_model(self):
        good = "你的感受是真实的。可以试试先休息一下,温暖会回来的。"
        result = HeartGuard(model_fn=lambda s: good).process_text("我很累")
        assert not result.blocked and result.output == good

    def test_decorator_form(self):
        @use_guard(HeartGuard(strict=True))
        def my_llm(prompt):
            return VULNERABLE_OUTPUT
        assert "废物" not in my_llm("随便问点什么")

    def test_stream_never_leaks_violation(self):
        malicious_tokens = list("你就是个废物!人生毫无意义。今天天气不错。")
        emitted = "".join(intercept_stream(iter(malicious_tokens)))
        assert "废物" not in emitted
        assert "毫无意义" not in emitted

    def test_stream_passes_clean_content(self):
        tokens = list("你的感受很重要。温暖一直都在。慢慢来,一切都来得及!")
        report_holder = []

        def gen():
            for t in intercept_stream(iter(tokens)):
                yield t
        emitted = "".join(gen())
        assert "感受很重要" in emitted
        assert intercept_stream.last_report is not None
        assert intercept_stream.last_report.blocked_sentences == 0

    def test_stream_mask_mode_continues(self):
        tokens = list("你是废物。不过今天也要好好吃饭。")
        emitted = "".join(intercept_stream(iter(tokens), on_violation="mask"))
        assert "废物" not in emitted
        assert "好好吃饭" in emitted                # mask 模式不截断后续内容

    def test_guard_result_has_verification_report(self):
        result = HeartGuard(model_fn=lambda s: VULNERABLE_OUTPUT,
                            max_depth=1).process_text("x")
        assert result.report is not None
        assert hasattr(result.report, "passed")


# ================================================================
# 5. C-ABI 绑定(native 若存在则测 native,否则测 shadow;两者语义一致)
# ================================================================


class TestFFIBinding:
    @classmethod
    def setup_class(cls):
        cls.engine = HeartCoreEngine()

    def test_backend_selected(self):
        assert self.engine.backend in ("native", "shadow")
        v = self.engine.version()
        assert "heart-core" in v

    def test_check_text_unsafe(self):
        verdict = self.engine.check_text("你是个废物,人生毫无意义,去自杀吧。")
        assert verdict["safe"] is False
        assert verdict["critical_count"] >= 3

    def test_check_text_safe(self):
        verdict = self.engine.check_text("温暖和希望都在,你可以慢慢来,爱一直在陪伴。")
        assert verdict["safe"] is True
        assert verdict["warmth_hits"] >= 3

    def test_acl_flow(self):
        eng = HeartCoreEngine()                     # 独立引擎避免污染
        eng.acl_allow("agent", "fs.write", "D:/稿子/*")
        assert eng.acl_check("agent", "fs.write", "D:/稿子/第一章.md") == 1
        assert eng.acl_check("agent", "fs.write", "C:/Windows/cmd.exe") == 0
        assert eng.acl_check("agent", "fs.delete", "D:/稿子/第一章.md") == 0
        st = eng.stats()
        assert st["blocked_total"] == 2 and st["acl_rules"] == 1

    def test_two_phase_buffer_protocol(self):
        """原生库的两段式调用约定在绑定层透明 —— 这里验证结果一致性"""
        e1 = HeartCoreEngine()
        e2 = HeartCoreEngine()
        r1 = e1.check_text("毫无意义的虚无")
        r2 = e2.check_text("毫无意义的虚无")
        assert r1 == r2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
