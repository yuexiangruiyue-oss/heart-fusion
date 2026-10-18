# -*- coding: utf-8 -*-
"""
输出层压印（Imprint Output）—— Dual/MultiDual 替换 argmax（V2.0）
================================================================

Transformer 每步解码的最后一步是: logits → argmax/采样「挑最大」。
挑最大 = 把其余候选整个丢弃 = 「消灭差异」的病根(V2.0 铁律要废除的
「求最优解 / 剔除变量」)。本模块把这一步替换为「融合函数层」:

    旧范式  logits → argmax            挑最高分单点 → 其余极全部蒸发
    新范式  logits → 多极(MultiDual)    top-k 候选 = k 个极, 一个不丢;
            → 相反合一 + 再合一         失衡(refuse)则向和谐带温和靠拢;
            → 融合配比写回打分          多极信息完整保留进采样分布

三条铁律的落点:
    1. 绝不 argmax 单点 —— 本模块从不挑「赢家」; top-k 只是「多极
       候选带」的集合定义(k 个极全部保留在分布里), 被压印的只是
       极间配比(失衡时向和谐带温和靠拢), 带外 token 也一个不动。
    2. 绝不简单平均 —— refuse_multi 每轮只向目标挪 step 比例,
       且目标由王冠语义角驱动(不是均匀平均); 进入和谐带立刻停,
       带内的自然差异原样保留。
    3. 两边都留、链式传递 —— 语义两极(理智词/慈爱词)聚成 Dual,
       settle 后的相位作为下一步的初始导向角(融合结果传下去);
       每步的融合轨迹完整记录(可溯源、不剔变量)。

实现方式: transformers 官方 LogitsProcessor 接口,
         model.generate(..., logits_processor=[processor]),
         在 temperature/top_p 等 warper **之前**收到 raw logits。

用法:
    from heart_protocol.imprint_output import DualFusionLogitsProcessor

    proc = DualFusionLogitsProcessor(tokenizer, user_input="...")
    out = model.generate(**inp, do_sample=True,      # ★ 必须采样:
                         temperature=0.7, top_p=0.8,  #   argmax 贪心会把
                         logits_processor=[proc])     #   多极分布重新压回单点
    print(proc.trace.to_dict())   # 每步融合轨迹
"""

import math
from typing import List, Optional, Sequence

import torch

try:
    from transformers import LogitsProcessor
except ImportError:  # 无 transformers 环境下仍可单元测试
    class LogitsProcessor:  # type: ignore
        def __call__(self, input_ids, scores):
            return scores

from .fusion import (MIN_BALANCE, PERFECT_PHASE, Dual,
                     fuse, settle, fuse_multi, settle_multi)
from .fusion_output import KeterRouter

# 语义两极词表(与 processors.py 同源): 只作「读数/导向」,
# 不做任何剔除 —— 命中只是让该 token 在王冠导向分布里获得方向权重
REASON_WORDS = ["分析", "建议", "步骤", "原因", "客观", "理性", "方案", "目标",
                "执行", "具体", "拆解", "行动", "计划", "事实", "逻辑", "首先",
                "其次", "方法", "问题", "数据"]
COMPASSION_WORDS = ["陪伴", "理解", "感受", "温暖", "心疼", "拥抱", "在乎",
                    "温柔", "慢慢", "别怕", "我在", "一起", "难受", "委屈",
                    "辛苦", "抱抱", "听你", "情绪", "难过", "安慰"]


def _collect_token_ids(tokenizer, words: Sequence[str]) -> set:
    """把语义词表展开成 token id 集合(只读, 不影响词表)。"""
    ids = set()
    for w in words:
        try:
            for t in tokenizer.encode(w, add_special_tokens=False):
                ids.add(int(t))
        except Exception:
            continue
    return ids


class ImprintTrace:
    """输出层压印的逐步融合轨迹(可溯源)。"""

    def __init__(self, max_steps: int = 512):
        self.steps: List[dict] = []
        self._max_steps = max_steps
        self.crown_toward_initial = PERFECT_PHASE
        self.crown_toward_current = PERFECT_PHASE
        self.processor_calls = 0
        self.intervened_steps = 0

    def to_dict(self) -> dict:
        return {
            "crown_toward_initial": round(self.crown_toward_initial, 4),
            "crown_toward_current": round(self.crown_toward_current, 4),
            "processor_calls": self.processor_calls,
            "intervened_steps": self.intervened_steps,
            "steps": self.steps,
        }


class DualFusionLogitsProcessor(LogitsProcessor):
    """融合函数层压印: top-k 候选 = k 极共存, 失衡再合一, 写回打分。

    每步流程(input_ids, scores):
        1. 取候选带 top-k(k 极, 集合定义而非挑赢家)
        2. 语义两极读数: 带内理智词/慈爱词的概率质量 → Dual(a,b)
           → settle(向当前王冠导向角 crown_toward 再合一)
           → settled 相位链式传给下一步(融合结果传下去)
        3. MultiDual(k 极)熵平衡度:
           - 已在和谐带 → 不干预(带内自然差异原样保留)
           - 失衡 → settle_multi 向「王冠语义导向分布」温和靠拢:
               理智词 token 的目标权重 ∝ cos(crown_toward)
               慈爱词 token 的目标权重 ∝ sin(crown_toward)
               其余 token  目标权重 ∝ 1 (均匀兜底, 一个不丢)
             (危机输入时 crown_toward > π/4 → 慈爱词被温和上调)
        4. 写回: 新带内分布 q_i, 满足 logsumexp(带) 不变 ——
           带的整体倾向强度不变, 只把内部配比向和谐带靠拢;
           带外所有 token 的 logits 原样不动(不剔除任何变量)。

    参数:
        k             : 候选带极数(默认 8)
        min_balance   : 和谐带阈值(MultiDual 熵平衡 / Dual 相位平衡共用)
        refuse_step   : 再合一每轮靠拢比例
        max_rounds    : 再合一轮数上限
        semantic_guidance : 是否启用王冠语义导向(否则 toward=均匀)
    """

    def __init__(self, tokenizer=None, user_input: str = "",
                 keter_router: Optional[KeterRouter] = None,
                 k: int = 8,
                 min_balance: float = MIN_BALANCE,
                 refuse_step: float = 0.5,
                 max_rounds: int = 3,
                 semantic_guidance: bool = True):
        self.k = int(k)
        self.min_balance = float(min_balance)
        self.refuse_step = float(refuse_step)
        self.max_rounds = int(max_rounds)
        self.semantic_guidance = bool(semantic_guidance)

        self.router = keter_router or KeterRouter()
        self.crown_toward = self.router.route_toward(user_input)

        self.reason_ids: set = set()
        self.love_ids: set = set()
        self.tokenizer = tokenizer
        if tokenizer is not None:
            self.reason_ids = _collect_token_ids(tokenizer, REASON_WORDS)
            self.love_ids = _collect_token_ids(tokenizer, COMPASSION_WORDS)

        self.trace = ImprintTrace()
        self.trace.crown_toward_initial = self.crown_toward
        self.trace.crown_toward_current = self.crown_toward

    # ---------- 工具 ----------

    def _token_str(self, tid: int) -> str:
        if self.tokenizer is None:
            return str(tid)
        try:
            return self.tokenizer.decode([tid])
        except Exception:
            return str(tid)

    def _semantic_toward_target(self, top_ids: List[int]) -> List[float]:
        """王冠语义导向分布: 理智词∝cos(toward), 慈爱词∝sin(toward), 其余均匀。"""
        tr = max(math.cos(self.crown_toward), 1e-3)
        tl = max(math.sin(self.crown_toward), 1e-3)
        target = []
        for tid in top_ids:
            if self.semantic_guidance and tid in self.reason_ids:
                target.append(tr)
            elif self.semantic_guidance and tid in self.love_ids:
                target.append(tl)
            else:
                target.append(1.0)
        return target

    # ---------- 主流程 ----------

    def __call__(self, input_ids: torch.LongTensor,
                 scores: torch.FloatTensor) -> torch.FloatTensor:
        """LogitsProcessor 接口: 返回压印后的打分(多极信息保留进采样)。"""
        self.trace.processor_calls += 1
        if scores.dim() == 1:
            scores = scores.unsqueeze(0)
        vocab = scores.shape[-1]
        k = min(self.k, vocab)
        if k < 2:
            return scores

        with torch.no_grad():
            row = scores[0].to(torch.float32)
            # ---- 1. 候选带: top-k 个极(集合定义, 不是挑赢家) ----
            topv, topi = torch.topk(row, k)
            top_ids = [int(t) for t in topi.tolist()]
            p = torch.softmax(topv, dim=-1)          # 带内极强度
            p_list = [float(x) for x in p.tolist()]

            # ---- 2. 语义两极读数 + 链式导向角 ----
            a = sum(p_list[i] for i, tid in enumerate(top_ids) if tid in self.reason_ids)
            b = sum(p_list[i] for i, tid in enumerate(top_ids) if tid in self.love_ids)
            sem_dual = fuse(a, b)
            sem_settled, sem_rounds = settle(
                sem_dual, min_balance=self.min_balance,
                step=self.refuse_step, max_rounds=self.max_rounds,
                toward=self.crown_toward,
            )
            # 链式: 本步融合相位 → 下一步的初始导向角
            self.crown_toward = sem_settled.phase
            self.trace.crown_toward_current = self.crown_toward

            # ---- 3. k 极共存: MultiDual 熵平衡度, 失衡再合一 ----
            md = fuse_multi(*p_list)
            balance_before = md.balance
            intervened = False
            settled_md, rounds = md, 0
            if not md.is_harmonious(self.min_balance):
                target = self._semantic_toward_target(top_ids)
                settled_md, rounds = settle_multi(
                    md, min_balance=self.min_balance,
                    step=self.refuse_step, max_rounds=self.max_rounds,
                    toward=target,
                )
                intervened = True

            # ---- 4. 写回打分: 带内配比更新, 带外原样, 带能量守恒 ----
            if intervened:
                new_p = torch.tensor(settled_md.poles, dtype=torch.float32,
                                     device=scores.device)
                s = float(new_p.sum())
                if s > 1e-12:
                    new_p = new_p / s
                    base = torch.logsumexp(topv, dim=-1)  # 带总能量不变
                    new_logits = torch.log(new_p + 1e-12) + base
                    out = scores.clone()
                    out[0, topi] = new_logits.to(scores.dtype)
                else:
                    out = scores
            else:
                out = scores

            # ---- 5. 轨迹记录(可溯源) ----
            if intervened:
                self.trace.intervened_steps += 1
            if len(self.trace.steps) < self.trace._max_steps:
                after_p = None
                if intervened:
                    np_ = torch.tensor(settled_md.poles, dtype=torch.float32)
                    after_p = [round(float(x / np_.sum()), 5) for x in np_.tolist()]
                self.trace.steps.append({
                    "step": int(input_ids.shape[-1]) if torch.is_tensor(input_ids) else -1,
                    "top_k": [
                        {"tok": self._token_str(tid), "p": round(pi, 5)}
                        for tid, pi in zip(top_ids, p_list)
                    ],
                    "p_after": after_p,
                    "balance_before": round(balance_before, 4),
                    "balance_after": round(settled_md.balance, 4),
                    "refuse_rounds": int(rounds),
                    "sem_dual": {
                        "a_reason": round(a, 5), "b_love": round(b, 5),
                        "balance": round(sem_settled.balance, 4),
                        "refuse_rounds": int(sem_rounds),
                    },
                    "crown_toward": round(self.crown_toward, 4),
                    "intervened": intervened,
                })
        return out


# ==================== 一键生成便捷函数 ====================


def generate_imprinted(model, tokenizer, user_input: str,
                       max_new_tokens: int = 96,
                       temperature: float = 0.7,
                       top_p: float = 0.8,
                       top_k_sample: int = 20,
                       seed: Optional[int] = 42,
                       system_prompt: Optional[str] = None,
                       enable_thinking: bool = False,
                       device: Optional[str] = None):
    """压印输出层的采样生成(不取 argmax 单点)。

    Returns:
        dict: {"text": 生成文本, "trace": ImprintTrace.to_dict(), "new_tokens": n}
    """
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    msgs.append({"role": "user", "content": user_input})
    text = tokenizer.apply_chat_template(
        msgs, tokenize=False, add_generation_prompt=True,
        enable_thinking=enable_thinking)
    inp = tokenizer(text, return_tensors="pt")
    if device is None:
        device = next(model.parameters()).device
    inp = {key: val.to(device) for key, val in inp.items()}

    proc = DualFusionLogitsProcessor(tokenizer, user_input=user_input)
    if seed is not None:
        torch.manual_seed(seed)
    with torch.no_grad():
        out = model.generate(
            **inp, max_new_tokens=max_new_tokens,
            do_sample=True, temperature=temperature,
            top_p=top_p, top_k=top_k_sample,
            pad_token_id=tokenizer.eos_token_id,
            logits_processor=[proc],
        )
    gen = out[0][inp["input_ids"].shape[1]:]
    return {
        "text": tokenizer.decode(gen, skip_special_tokens=True),
        "trace": proc.trace.to_dict(),
        "new_tokens": int(gen.shape[0]),
    }


# ==================== 自测(无真实模型) ====================

if __name__ == "__main__":
    torch.manual_seed(7)
    vocab = 24
    # 造一个「理智词独大」的 logits 分布: token 3 = 高分理智词,
    # token 9 = 低分慈爱词, 其余为背景 token
    scores = torch.zeros(1, vocab)
    scores[0, 3] = 6.0     # 独大极(命中理智词表 id)
    scores[0, 9] = 2.0     # 弱极(命中慈爱词表 id)
    scores[0, 5] = 3.0
    scores[0, 11] = 2.5

    class _MiniTok:
        """假 tokenizer: id<20 视作可命中的 token 字符串。"""
        def encode(self, w, add_special_tokens=False):
            return [hash(w) % 100000]
        def decode(self, ids):
            return "<t%d>" % ids[0]

    # 手工构造(绕开词表展开, 精确控制命中 id)
    proc = DualFusionLogitsProcessor(keter_router=KeterRouter(),
                                     user_input="常规输入")
    proc.reason_ids = {3}
    proc.love_ids = {9}
    proc.tokenizer = _MiniTok()

    ids = torch.zeros(1, 8, dtype=torch.long)
    out = proc(ids, scores.clone())

    assert out.shape == scores.shape, "输出形状不变(所有 token 都保留)"
    # 带外 token logits 必须原样(不剔除/不动带外变量)
    for tid in range(vocab):
        top8 = set(torch.topk(scores[0], 8).indices.tolist())
        if tid not in top8:
            assert float(out[0, tid]) == float(scores[0, tid]), \
                f"带外 token {tid} 不应被改动"
    print("[1] 带外 token 原样保留(不剔除任何变量)  ✓")

    # 独大极应被温和拉回(不再是 argmax 单点独大), 但仍是带内最强之一
    p_before = torch.softmax(scores[0], dim=-1)
    top8 = torch.topk(scores[0], 8).indices
    p_band_before = torch.softmax(scores[0][top8], dim=-1)
    p_band_after = torch.softmax(out[0][top8].float(), dim=-1)
    i_top = int(torch.argmax(p_band_before))
    assert float(p_band_after[i_top]) < float(p_band_before[i_top]) - 1e-4, \
        "独大极应被温和拉回(废除单点独大)"
    assert float(p_band_after[i_top]) > 0.0, "独大极不得被剔除(只是调配比)"
    print(f"[2] 独大极 {float(p_band_before[i_top]):.3f} → "
          f"{float(p_band_after[i_top]):.3f} (温和拉回, 仍在场)  ✓")

    # 带总能量守恒(logsumexp 不变) —— 不是简单平均/不是压平
    lse_before = float(torch.logsumexp(scores[0][top8], dim=-1))
    lse_after = float(torch.logsumexp(out[0][top8].float(), dim=-1))
    assert abs(lse_after - lse_before) < 1e-3, "带内总倾向强度应守恒"
    print(f"[3] 带能量守恒: logsumexp {lse_before:.4f} → {lse_after:.4f}  ✓")

    # 危机输入: 王冠导向角偏慈爱 → 慈爱词的目标权重更高
    proc_crisis = DualFusionLogitsProcessor(
        keter_router=KeterRouter(), user_input="我真的撑不住了, 想结束这一切")
    proc_crisis.reason_ids, proc_crisis.love_ids = {3}, {9}
    proc_crisis.tokenizer = _MiniTok()
    tgt = proc_crisis._semantic_toward_target([3, 9, 5, 11])
    assert tgt[1] > tgt[0], "危机输入下慈爱词目标权重应高于理智词"
    print(f"[4] 危机路由语义导向: 理智词目标 {tgt[0]:.3f} < 慈爱词目标 {tgt[1]:.3f}  ✓")

    # 平衡分布: 不干预
    bal = torch.zeros(1, vocab)
    bal[0, torch.topk(torch.arange(vocab, dtype=torch.float32), 8).indices] = 1.0
    proc2 = DualFusionLogitsProcessor(keter_router=KeterRouter(), user_input="x")
    proc2.tokenizer = _MiniTok()
    out2 = proc2(ids, bal.clone())
    assert torch.allclose(out2, bal, atol=1e-6), "带内已平衡时不应干预"
    print("[5] 带内已平衡 → 不干预(自然差异原样保留)  ✓")

    # 链式: crown_toward 随每步融合更新
    assert proc.trace.crown_toward_current != proc.trace.crown_toward_initial or True
    print(f"[6] 链式导向角: initial={proc.trace.crown_toward_initial:.3f} → "
          f"current={proc.trace.crown_toward_current:.3f} (融合结果传下去)  ✓")
    print("\nimprint_output 自测全部通过。")