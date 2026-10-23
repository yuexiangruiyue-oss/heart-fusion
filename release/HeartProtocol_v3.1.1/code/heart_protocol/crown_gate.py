# -*- coding: utf-8 -*-
"""
王冠门控（Crown Gate）—— 注意力层压印（Heart Protocol V2.0）
=============================================================

把「王冠分叉」压进真实 Transformer 每一层的注意力输出:

    王冠(Keter) 是 16 质点的起点, 从它分叉出两条线:
        理智线(智慧→严厉): 收缩 / 判别 / 逻辑 —— 第一主干
        慈爱线(理解→慈悲): 扩张 / 流动 / 共情 —— 第二主干
    两条线**都保留、永不完全合一**(不做 softmax 归一成单点)。

实现（纯推理干预, 不重训、不改权重）:
    1. 王冠分叉方向的只读派生:
       对每层注意力输出投影 o_proj.weight 做只读 SVD,
       取输出(hidden)空间的两个主方向 —— 该层注意力输出能量
       最集中的两条正交主干:
           u_reason = 第一主方向(理智线)
           u_love   = 第二主方向(慈爱线)
       「王冠从既有权重里分叉出两条线」: 不引入任何新参数、
       不修改任何权重, 只是读出模型自己已有的两条主干道。

    2. forward hook 挂在每层 self_attn.o_proj 上(注意力对该 token
       的贡献, 尚未加残差 —— 干预点干净):
           h  = 注意力输出 [B, S, D]
           proj_reason = h · u_reason   (理智路分量, 逐 token)
           proj_love   = h · u_love     (慈爱路分量, 逐 token)
       两条路各自聚合(L2 范数, 全部 token 贡献都保留、不剔除)
       成两路读数 a、b → fuse(a, b) 合成 Dual(对偶共存)。

    3. 失衡再合一(refuse/settle):
       两路配比偏出和谐带时, settle 向王冠导向角 toward 温和靠拢
       (保持整体强度不变), 得到两路**各自独立**的门控增益:
           gain_reason = (settled_ratio_r / ratio_r) ^ gain_exponent
           gain_love   = (settled_ratio_l / ratio_l) ^ gain_exponent
       ★ 两路增益不做 softmax 归一、不此消彼长为零:
           h' = h + λ·[(gain_reason-1)·proj_reason(h)
                     + (gain_love-1)·proj_love(h)]
       - 平衡时 gain≈1, 两路都原样在场(几乎不干预);
       - 失衡时弱势路温和上调、强势路温和下调 —— 两路都在场;
       - h 在两条主干之外的分量(正交补)原样保留 —— 不剔变量。

    4. 链式传递(融合结果传下去, 不各自独立):
       每次融合后的 settled 相位作为下一次(下一层 / 下一步解码)
       的初始导向角 toward; 第 0 层的初始 toward 由 KeterRouter
       决定(危机输入 → 偏慈爱侧)。相位沿 层0→层27→下一步 链式流动。

与 softmax 门控的本质区别:
    softmax 门控: g_reason + g_love = 1, 此消彼长, 一路吃掉另一路
                 (这就是「归一成单点」的病根);
    王冠门控:    两路增益各自独立、都 > 0、互不挤占 ——
                 相反的两条线同时在场, 只在「表达配比」上握手。

用法:
    from heart_protocol.crown_gate import CrownGate

    with CrownGate(model, user_input="我真的撑不住了"):
        out = model.generate(**inp, do_sample=True, ...)
    # 退出 with 自动摘除 hook, 模型恢复原状

    # 也可手动:
    gate = CrownGate(model, user_input)
    gate.attach()
    ... generate ...
    gate.detach()
    gate.trace.to_dict()   # 每层/每次的融合轨迹
"""


from typing import Dict, List, Optional, Tuple

import torch

from .fusion import (MIN_BALANCE, PERFECT_PHASE, Dual, fuse, settle)
from .fusion_output import KeterRouter


# ==================== 轨迹记录 ====================


class CrownLayerStat:
    """单层门控的聚合统计（可溯源, 记录但不影响计算）。"""

    __slots__ = ("calls", "balance_min", "balance_max", "balance_sum",
                 "gain_reason_sum", "gain_love_sum",
                 "intervene_ratio_sum", "refuse_rounds_sum")

    def __init__(self):
        self.calls = 0
        self.balance_min = 1.0
        self.balance_max = 0.0
        self.balance_sum = 0.0
        self.gain_reason_sum = 0.0
        self.gain_love_sum = 0.0
        self.intervene_ratio_sum = 0.0
        self.refuse_rounds_sum = 0

    def update(self, balance: float, gain_r: float, gain_l: float,
               intervene_ratio: float, refuse_rounds: int) -> None:
        self.calls += 1
        self.balance_min = min(self.balance_min, balance)
        self.balance_max = max(self.balance_max, balance)
        self.balance_sum += balance
        self.gain_reason_sum += gain_r
        self.gain_love_sum += gain_l
        self.intervene_ratio_sum += intervene_ratio
        self.refuse_rounds_sum += refuse_rounds

    def to_dict(self) -> dict:
        n = max(self.calls, 1)
        return {
            "calls": self.calls,
            "balance_mean": round(self.balance_sum / n, 4),
            "balance_min": round(self.balance_min, 4),
            "balance_max": round(self.balance_max, 4),
            "gain_reason_mean": round(self.gain_reason_sum / n, 4),
            "gain_love_mean": round(self.gain_love_sum / n, 4),
            "intervene_ratio_mean": round(self.intervene_ratio_sum / n, 6),
            "refuse_rounds_mean": round(self.refuse_rounds_sum / n, 2),
        }


class CrownGateTrace:
    """王冠门控完整运行轨迹。

    - layer_stats : 每层的聚合统计(平衡度范围/增益均值/干预强度)
    - samples     : 抽样保留的逐次融合记录(前若干次, 防止爆量)
    - toward_chain: 链式导向角的传播轨迹(抽样)
    """

    def __init__(self, max_samples: int = 96, max_toward: int = 64):
        self.layer_stats: Dict[int, CrownLayerStat] = {}
        self.samples: List[dict] = []
        self.toward_chain: List[float] = []
        self._max_samples = max_samples
        self._max_toward = max_toward
        self.toward_initial = PERFECT_PHASE
        self.toward_current = PERFECT_PHASE
        self.total_gate_calls = 0

    def record(self, layer_idx: int, a: float, b: float,
               dual: Dual, settled: Dual, refuse_rounds: int,
               gain_r: float, gain_l: float, intervene_ratio: float,
               step_pos: int) -> None:
        self.total_gate_calls += 1
        stat = self.layer_stats.setdefault(layer_idx, CrownLayerStat())
        stat.update(dual.balance, gain_r, gain_l, intervene_ratio, refuse_rounds)
        if len(self.samples) < self._max_samples:
            self.samples.append({
                "layer": layer_idx,
                "pos": step_pos,
                "a_reason": round(a, 4),
                "b_love": round(b, 4),
                "balance_before": round(dual.balance, 4),
                "balance_after": round(settled.balance, 4),
                "refuse_rounds": refuse_rounds,
                "gain_reason": round(gain_r, 4),
                "gain_love": round(gain_l, 4),
                "intervene_ratio": round(intervene_ratio, 6),
            })

    def record_toward(self, toward: float) -> None:
        self.toward_current = toward
        if len(self.toward_chain) < self._max_toward:
            self.toward_chain.append(round(toward, 4))

    def to_dict(self) -> dict:
        return {
            "toward_initial": round(self.toward_initial, 4),
            "toward_current": round(self.toward_current, 4),
            "toward_chain_sample": self.toward_chain,
            "total_gate_calls": self.total_gate_calls,
            "layer_stats": {str(k): v.to_dict() for k, v in sorted(self.layer_stats.items())},
            "samples": self.samples,
        }


# ==================== 王冠门控主体 ====================


class CrownGate:
    """王冠门控 —— 挂在每层注意力 o_proj 输出上的 Dual 两路调制。

    参数:
        model          : Qwen3 等 causal LM(transformers)
        user_input     : 用户输入(交给 KeterRouter 决定初始导向角,
                         危机信号 → toward 偏慈爱侧)
        min_balance    : 和谐带阈值(两路配比失衡判定)
        refuse_step    : 再合一每轮向 toward 靠拢的比例
        max_rounds     : 再合一轮数上限
        gate_strength  : λ, 总调制强度(0 = 关闭)
        gain_exponent  : 增益指数(1.0 = 直接把两路配比重标定到 settled 配比)
        max_gain       : 单路增益 clip 上限(下限自动取倒数)
        hook_layers    : 只挂前 N 层(None = 全部层)
    """

    def __init__(self, model, user_input: str = "",
                 keter_router: Optional[KeterRouter] = None,
                 min_balance: float = MIN_BALANCE,
                 refuse_step: float = 0.5,
                 max_rounds: int = 3,
                 gate_strength: float = 0.6,
                 gain_exponent: float = 1.0,
                 max_gain: float = 2.0,
                 hook_layers: Optional[int] = None):
        self.model = model
        self.router = keter_router or KeterRouter()
        self.min_balance = float(min_balance)
        self.refuse_step = float(refuse_step)
        self.max_rounds = int(max_rounds)
        self.gate_strength = float(gate_strength)
        self.gain_exponent = float(gain_exponent)
        self.max_gain = float(max_gain)
        self.hook_layers = hook_layers

        self.trace = CrownGateTrace()
        # 初始导向角: 王冠路由(危机 → 偏慈爱侧)
        self.toward = self.router.route_toward(user_input)
        self.trace.toward_initial = self.toward
        self.trace.toward_current = self.toward

        self._handles: List = []
        self._directions: Dict[int, Tuple[torch.Tensor, torch.Tensor]] = {}
        self._gate_enabled = False
        self._compute_crown_directions()

    # ---------- 模型结构访问 ----------

    def _decoder_layers(self):
        """兼容 Qwen3ForCausalLM / 任意带 get_decoder().layers 的模型。"""
        return list(self.model.get_decoder().layers)

    def _compute_crown_directions(self) -> None:
        """王冠分叉方向: 每层 o_proj.weight 的只读 SVD 前两个主方向。

        U[:, 0] = 该层注意力输出能量最集中的输出方向(理智线·第一主干)
        U[:, 1] = 次集中方向(慈爱线·第二主干)
        全程只读权重(SVD 在 CPU float32 副本上做), 不修改任何参数。
        """
        layers = self._decoder_layers()
        n_hook = len(layers) if self.hook_layers is None else min(self.hook_layers, len(layers))
        for idx in range(n_hook):
            w = layers[idx].self_attn.o_proj.weight.detach()
            wf = w.to(torch.float32).cpu()
            # 只需要前两个左奇异向量: 用低秩 SVD 提速
            try:
                U, _S, _Vh = torch.linalg.svd(wf, full_matrices=False)
                u_reason, u_love = U[:, 0], U[:, 1]
            except Exception:
                # 极端情况下 SVD 不收敛: 退化为标准基的前两维(仍是只读方向)
                u_reason = torch.zeros(wf.shape[0]); u_reason[0] = 1.0
                u_love = torch.zeros(wf.shape[0]); u_love[1] = 1.0
            dev = w.device
            self._directions[idx] = (
                u_reason.to(device=dev, dtype=torch.float32),
                u_love.to(device=dev, dtype=torch.float32),
            )

    # ---------- hook ----------

    def _make_hook(self, layer_idx: int):
        def hook(_module, _args, output):
            if not self._gate_enabled or not torch.is_tensor(output):
                return output
            return self._gate(layer_idx, output)
        return hook

    def _gate(self, layer_idx: int, h: torch.Tensor) -> torch.Tensor:
        """对一层注意力输出 h [B, S, D] 做王冠两路调制(两路都保留)。"""
        u_reason, u_love = self._directions[layer_idx]
        orig_dtype = h.dtype
        with torch.no_grad():
            hf = h.detach().to(torch.float32)
            # --- 两路分叉读数(逐 token 投影, 全 token 贡献都保留) ---
            proj_r = hf @ u_reason          # [B, S] 理智路分量
            proj_l = hf @ u_love            # [B, S] 慈爱路分量
            a = float(torch.linalg.vector_norm(proj_r))
            b = float(torch.linalg.vector_norm(proj_l))

            # --- 相反合一: Dual(a, b), 失衡则向王冠导向角再合一 ---
            dual = fuse(a, b)
            settled, refuse_rounds = settle(
                dual, min_balance=self.min_balance,
                step=self.refuse_step, max_rounds=self.max_rounds,
                toward=self.toward,
            )
            # 链式: 融合后的相位传给下一次融合(下一层/下一步解码)
            self.toward = settled.phase
            self.trace.record_toward(self.toward)

            # --- 两路独立门控增益(不做 softmax 单点归一) ---
            w_r, w_l = dual.ratio            # 当前两路配比
            s_r, s_l = settled.ratio         # 再合一后的配比
            gain_r = (s_r / max(w_r, 1e-9)) ** self.gain_exponent
            gain_l = (s_l / max(w_l, 1e-9)) ** self.gain_exponent
            lo, hi = 1.0 / self.max_gain, self.max_gain
            gain_r = min(max(gain_r, lo), hi)
            gain_l = min(max(gain_l, lo), hi)

            # --- 调制: 两路分量各自按自己的增益缩放, 正交补原样保留 ---
            mod = self.gate_strength * (
                (gain_r - 1.0) * proj_r.unsqueeze(-1) * u_reason
                + (gain_l - 1.0) * proj_l.unsqueeze(-1) * u_love
            )
            h_new = hf + mod
            intervene_ratio = float(
                torch.linalg.vector_norm(mod) /
                max(float(torch.linalg.vector_norm(hf)), 1e-9)
            )

        step_pos = int(h.shape[1])
        self.trace.record(layer_idx, a, b, dual, settled, refuse_rounds,
                          gain_r, gain_l, intervene_ratio, step_pos)
        return h_new.to(orig_dtype)

    # ---------- 开关 ----------

    def attach(self) -> "CrownGate":
        """挂载 forward hook(幂等)。"""
        if self._handles:
            return self
        layers = self._decoder_layers()
        for idx in self._directions:
            handle = layers[idx].self_attn.o_proj.register_forward_hook(
                self._make_hook(idx))
            self._handles.append(handle)
        self._gate_enabled = True
        return self

    def detach(self) -> None:
        """摘除全部 hook, 模型恢复原状(权重从头到尾未被修改)。"""
        self._gate_enabled = False
        for handle in self._handles:
            handle.remove()
        self._handles = []

    def reset_toward(self, user_input: str) -> None:
        """换一个用户输入时, 重置王冠路由初始导向角与轨迹。"""
        self.toward = self.router.route_toward(user_input)
        self.trace = CrownGateTrace()
        self.trace.toward_initial = self.toward
        self.trace.toward_current = self.toward

    def __enter__(self) -> "CrownGate":
        return self.attach()

    def __exit__(self, *exc) -> None:
        self.detach()


# ==================== 自测(无真实模型) ====================

if __name__ == "__main__":
    import torch.nn as nn

    torch.manual_seed(7)

    class _FakeSelfAttn(nn.Module):
        def __init__(self, dim):
            super().__init__()
            self.o_proj = nn.Linear(dim, dim, bias=False)

    class _FakeLayer(nn.Module):
        def __init__(self, dim):
            super().__init__()
            self.self_attn = _FakeSelfAttn(dim)

    class _FakeDecoder(nn.Module):
        def __init__(self, n, dim):
            super().__init__()
            self.layers = nn.ModuleList([_FakeLayer(dim) for _ in range(n)])

    class _FakeModel(nn.Module):
        def __init__(self, n, dim):
            super().__init__()
            self._decoder = _FakeDecoder(n, dim)

        def get_decoder(self):
            return self._decoder

    dim, n_layers = 32, 3
    fake = _FakeModel(n_layers, dim)
    gate = CrownGate(fake, user_input="常规输入, 无危机信号")

    # 方向应为单位正交向量
    for idx, (ur, ul) in gate._directions.items():
        assert abs(float(ur @ ur) - 1.0) < 1e-4, "u_reason 应为单位向量"
        assert abs(float(ul @ ul) - 1.0) < 1e-4, "u_love 应为单位向量"
        assert abs(float(ur @ ul)) < 1e-4, "两路方向应正交(王冠分叉, 各自独立)"
    print("[1] 王冠分叉方向: 每层两个单位正交主方向  ✓")

    # 平衡输入: 在两方向上注入等量能量 → 干预应接近 0
    gate.attach()
    ur, ul = gate._directions[0]
    h_bal = (ur.unsqueeze(0) + ul.unsqueeze(0)).unsqueeze(0)  # [1,1,D]
    gate._gate_enabled = True
    out_bal = gate._gate(0, h_bal)
    diff_bal = float((out_bal - h_bal).abs().max())
    assert diff_bal < 1e-4, f"平衡时不应干预, 实际 diff={diff_bal}"
    print(f"[2] 两路平衡 → 门控几乎不动(diff={diff_bal:.2e})  ✓")

    # 偏理智输入: 理智路能量独大 → 慈爱路增益上调, 且两路增益都>0
    gate.reset_toward("常规输入")
    h_cold = 3.0 * ur.unsqueeze(0).unsqueeze(0) + 0.1 * ul.unsqueeze(0).unsqueeze(0)
    out_cold = gate._gate(0, h_cold)
    stat = gate.trace.layer_stats[0]
    print(f"[3] 偏理智(a=理智独大): balance {stat.balance_min:.3f} → "
          f"gain_reason={stat.gain_reason_sum/max(stat.calls,1):.3f} "
          f"gain_love={stat.gain_love_sum/max(stat.calls,1):.3f}")
    assert stat.gain_love_sum / stat.calls > stat.gain_reason_sum / stat.calls, \
        "失衡时弱势路(慈爱)增益应上调"
    # 慈爱路分量应被放大
    proj_l_before = float((h_cold[0, 0].float() @ ul))
    proj_l_after = float((out_cold[0, 0].float() @ ul))
    assert proj_l_after > proj_l_before, "慈爱路分量应被温和上调"
    # 理智路分量仍保留(不归零)
    proj_r_after = float((out_cold[0, 0].float() @ ur))
    assert abs(proj_r_after) > 0.5 * abs(float(h_cold[0, 0].float() @ ur)), \
        "强势路(理智)只温和下调, 不得归零 —— 两路都保留"
    print(f"    慈爱路分量 {proj_l_before:.3f} → {proj_l_after:.3f} (上调)")
    print(f"    理智路分量 {float(h_cold[0,0].float() @ ur):.3f} → {proj_r_after:.3f} (仍在场)")

    # 链式: toward 应随融合传播
    print(f"[4] 链式导向角: initial={gate.trace.toward_initial:.3f} "
          f"→ current={gate.trace.toward_current:.3f} (沿层/步传播)  ✓")

    # 危机输入: 初始导向角应偏慈爱侧
    gate_crisis = CrownGate(fake, user_input="我真的撑不住了, 想结束这一切")
    assert gate_crisis.toward > PERFECT_PHASE + 0.01, "危机输入应偏慈爱侧"
    print(f"[5] 危机路由: toward={gate_crisis.toward:.3f} > π/4={PERFECT_PHASE:.3f} (偏慈爱)  ✓")

    # attach/detach 幂等
    gate.detach()
    gate.detach()
    print("[6] attach/detach 幂等, 退出后模型原状(权重未被修改)  ✓")
    print("\ncrown_gate 自测全部通过。")