# -*- coding: utf-8 -*-
"""
再合一(refuse) —— 取代「退回上级重算 + Beam/MCTS 奖励回溯」(V2.0)
===================================================================

哲学来源(荣耀 · Hod / 胜利 · Netzach):
    「检测结论…不通过则退回美丽重算」「无法执行则退回上级重算」

V2.0 关键演进 —— 「退回上级」是层级网络的概念; 节点网络下, 失衡不再
"向上退回", 而在**原地再合一**:

    一次再合一 = 在某融合点, 发现「相反合一」偏出和谐带(极化到某一极),
                 则向平衡点温和靠拢一步, 重新融合。见 fusion.refuse / settle。

被废除的旧范式(不保留、不兼容):
    · Beam Search 的 top-k 剪枝       —— 这是在「剔变量」
    · MCTS 的 reward 累加 / UCB1      —— 这是「奖励 + 最优探索」
    · pass_score 阈值 / argmax 择优   —— 这是「打分 + 寻求最优解」
    · strategy 的 _boost(+0.25) 调权重 —— 这是「梯度式调整」

新范式唯一动作 = 「向平衡点靠拢」; 新范式唯一停滞条件 = 「进入和谐带」。
"""

import copy
import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..fusion import Dual, PERFECT_PHASE, MIN_BALANCE

# ==================== 再合一方向(取代"重试策略空间") ====================


@dataclass
class RetryStrategy:
    """
    一次「再合一」所朝的方向。

    不再是"调整一个标量权重后重新打分的策略", 而是"让相反两极朝哪个
    平衡点重新握手"。无奖励、无梯度 —— 只改变融合的相位目标。
    """

    id: str
    description: str
    toward: float = PERFECT_PHASE      # 目标平衡角(默认完美平衡 π/4)
    step: float = 0.5                   # 靠拢比例
    mutate: Callable[[Dict[str, Any]], Dict[str, Any]] = None

    def apply(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """把「方向」写入状态(如注入落地步/软化语气), 供下游再合一使用。"""
        new_state = copy.deepcopy(state)
        new_state["toward"] = self.toward
        new_state["step"] = self.step
        if self.mutate is not None:
            new_state = self.mutate(new_state)
        return new_state


def _set_flag(key: str, value: Any) -> Callable[[Dict], Dict]:
    def mutate(state: Dict) -> Dict:
        state[key] = value
        return state
    return mutate


# 六个再合一方向: 都不涨任何"分", 只决定向哪个平衡点、以及附带何种文本调整。
DEFAULT_STRATEGIES: List[RetryStrategy] = [
    RetryStrategy("baseline", "向完美平衡点温和再合一",
                  toward=PERFECT_PHASE, step=0.5),
    RetryStrategy("empathy_boost", "向共情极靠拢(更有温度)",
                  toward=0.62 * PERFECT_PHASE * 2, step=0.6),
    RetryStrategy("logic_boost", "向理性极靠拢(更落地)",
                  toward=0.38 * PERFECT_PHASE * 2, step=0.6),
    RetryStrategy("concrete_steps", "注入具体可执行步骤",
                  toward=0.4 * PERFECT_PHASE * 2, step=0.5,
                  mutate=_set_flag("force_concrete_steps", True)),
    RetryStrategy("soften_tone", "软化语气、降低绝对化表述",
                  toward=PERFECT_PHASE, step=0.5,
                  mutate=_set_flag("tone", "gentle")),
    RetryStrategy("shorten", "压缩篇幅、聚焦核心",
                  toward=PERFECT_PHASE, step=0.5,
                  mutate=_set_flag("target_length", "short")),
]


# ==================== 快照(检查点, 语义改为"融合读数") ====================


@dataclass
class Snapshot:
    """不可变的融合检查点。score 保留为 balance 的兼容别名。"""

    sephirah: str                        # 所属质点阶段
    attempt: int                         # 第几次再合一
    state: Dict[str, Any]                # 阶段状态深拷贝
    output: str = ""                     # 该次尝试的输出文本
    balance: float = 1.0                 # 融合平衡度(1=完美平衡, 0=完全极化)
    phase: float = PERFECT_PHASE         # 融合相位
    strategy_id: str = "root"            # 由哪个方向产生
    parent: Optional["Snapshot"] = field(default=None, repr=False)

    @property
    def score(self) -> float:
        """兼容旧字段名: score == balance(平衡度, 非"奖励分")。"""
        return self.balance

    @property
    def depth(self) -> int:
        d, node = 0, self
        while node.parent is not None:
            d += 1
            node = node.parent
        return d

    def path(self) -> List["Snapshot"]:
        out, node = [], self
        while node is not None:
            out.append(node)
            node = node.parent
        return list(reversed(out))

    def restore(self) -> Dict[str, Any]:
        return copy.deepcopy(self.state)


# ==================== 再合一引擎(取代 Beam/MCTS 回溯) ====================

ComputeFn = Callable[[Dict[str, Any], RetryStrategy], Tuple[Dict[str, Any], str]]
# validate_fn 现在返回「平衡度」或对偶量读数 —— 用于判断是否和谐(非打分)。
ValidateFn = Callable[[str], Any]


class RollbackEngine:
    """
    标准化「再合一」引擎(取代 Beam/MCTS 奖励回溯)。

    Args:
        compute_fn  : (state, strategy) -> (new_state, output_text)
        validate_fn : (output_text) -> balance∈[0,1] 或 Dual
                       —— 融合平衡度读数(用于判断是否进入和谐带, 不是奖励分)
        strategies  : 再合一方向列表(默认 DEFAULT_STRATEGIES)
        min_balance : 进入和谐带的最低平衡度(取代旧 pass_score)
        max_rounds  : 单点「再合一」上限(活性保证)
        seed        : 随机种子(仅用于打破方向遍历顺序, 不参与任何分值)
    """

    def __init__(self,
                 compute_fn: ComputeFn,
                 validate_fn: ValidateFn,
                 strategies: Optional[List[RetryStrategy]] = None,
                 min_balance: float = MIN_BALANCE,
                 max_rounds: int = 3,
                 seed: Optional[int] = None):
        self.compute_fn = compute_fn
        self.validate_fn = validate_fn
        self.strategies = strategies or list(DEFAULT_STRATEGIES)
        self.min_balance = min_balance
        self.max_rounds = max_rounds
        self.rng = random.Random(seed)
        self.expansions = 0          # 总再合一次数(延迟统计用)

    # ---------- 内部 ----------

    def _balance_of(self, output: str) -> Tuple[float, float]:
        """读取融合读数: 返回 (balance, phase)。与奖励无关。"""
        v = self.validate_fn(output)
        if isinstance(v, Dual):
            return v.balance, v.phase
        if isinstance(v, (tuple, list)) and len(v) >= 2:
            return float(v[0]), float(v[1])
        return float(v), PERFECT_PHASE

    def _make_root(self, sephirah: str, state: Dict[str, Any],
                   initial_output: str = "") -> Snapshot:
        # 初始平衡度优先取 initial_output; 若为空且 state 里已有对偶量,
        # 则以其为初始读数(便于直接以对偶量驱动再合一)。
        if initial_output:
            probe = initial_output
        elif isinstance(state.get("dual"), Dual):
            probe = state["dual"]
        else:
            probe = None
        if probe is not None:
            bal, ph = self._balance_of(probe)
        else:
            bal, ph = 1.0, PERFECT_PHASE
        return Snapshot(sephirah=sephirah, attempt=0,
                        state=copy.deepcopy(state),
                        output=initial_output, balance=bal, phase=ph,
                        strategy_id="root")

    def _evaluate(self, parent: Snapshot, strategy: RetryStrategy) -> Snapshot:
        new_state, output = self.compute_fn(parent.state, strategy)
        bal, ph = self._balance_of(output)
        snap = Snapshot(
            sephirah=parent.sephirah,
            attempt=parent.attempt + 1,
            state=new_state,
            output=output,
            balance=bal,
            phase=ph,
            strategy_id=strategy.id,
            parent=parent,
        )
        self.expansions += 1
        return snap

    @staticmethod
    def _more_harmonious(a: Snapshot, b: Snapshot) -> Snapshot:
        """更和谐者胜(纯平衡度比较, 无奖励、无外部目标)。

        平衡度相等时返回「更靠后」的尝试(attempt 更大), 以使"再合一之后
        的最新状态"能够被回传 —— 它至少真正发生过再合一, 而非逗留在根节点。
        """
        if b.balance != a.balance:
            return b if b.balance > a.balance else a
        return b if b.attempt >= a.attempt else a

    # ---------- 公共: 再合一收敛(核心) ----------

    def refuse_rollback(self,
                        sephirah: str,
                        state: Dict[str, Any],
                        initial_output: str = "",
                        max_rounds: Optional[int] = None) -> Snapshot:
        """
        再合一回溯: 从失衡态出发, 顺序尝试各「再合一方向」, 一旦进入
        和谐带(balance >= min_balance)即停止。不排序、不剪枝、无奖励。

        与旧 Beam(top-k + argmax)/ MCTS(reward + UCB1) 的本质区别:
        · 不选"最优" —— 只满足"和谐"这一条约束
        · 不剔候选 —— 每个方向都真实尝试, 全部并存
        """
        rounds = max_rounds if max_rounds is not None else self.max_rounds
        root = self._make_root(sephirah, state, initial_output)
        best = root
        if root.balance >= self.min_balance:
            return root          # 已和谐, 无需再合一

        current = root
        directions = list(self.strategies)
        # 只打乱遍历顺序以破除固定偏向, 分值不参与任何选择
        self.rng.shuffle(directions)

        for _ in range(rounds):
            improved = False
            for strat in directions:
                child = self._evaluate(current, strat)
                best = self._more_harmonious(best, child)
                if child.balance >= self.min_balance:
                    return child     # 第一个进入和谐带的解
                current = child
                improved = True
            if not improved:
                break

        return best                  # 未能和谐时, 返回最接近和谐的结果(容错, 非最优)

    # ---------- 兼容别名(旧方法名, 语义已改为再合一, 无奖励/无最优) ----------

    def beam_search_rollback(self, sephirah: str, state: Dict[str, Any],
                             initial_output: str = "",
                             beam_width: int = 3, max_depth: int = 3) -> Snapshot:
        """旧名兼容: beam_width 不再用于剪枝(不剔变量), 仅忽略。"""
        return self.refuse_rollback(sephirah, state, initial_output,
                                    max_rounds=max_depth)

    def mcts_rollback(self, sephirah: str, state: Dict[str, Any],
                      initial_output: str = "",
                      iterations: int = 16, exploration_c: float = 1.414,
                      max_depth: int = 3) -> Snapshot:
        """旧名兼容: 无 UCB1 奖励搜索, 与 refuse_rollback 同语义。"""
        return self.refuse_rollback(sephirah, state, initial_output,
                                    max_rounds=max_depth)

    # ---------- 与协议轨迹对接 ----------

    @staticmethod
    def to_stage_record(best: Snapshot) -> Dict[str, Any]:
        """把再合一结果转成 formal.spec.StageRecord 兼容字段。"""
        return {
            "sephirah": best.sephirah,
            "attempt": max(1, best.attempt),
            "output_text": best.output,
            "balance": best.balance,
            "phase": best.phase,
            "strategy": best.strategy_id,
        }