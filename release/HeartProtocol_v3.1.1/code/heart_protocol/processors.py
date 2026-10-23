# -*- coding: utf-8 -*-
"""
融合函数层 · transformers 官方集成
================================

用 transformers 的 LogitsProcessor 接口实现危机词增强,
不需要 monkey-patch Qwen3Attention.forward。

用法:
    from heart_protocol.processors import CrisisBoostLogitsProcessor, generate_with_fusion

    # 方式1: 手动用 LogitsProcessor
    processor = CrisisBoostLogitsProcessor(tokenizer, crisis_words=["结束","撑不住"])
    out = model.generate(**inp, logits_processor=[processor], ...)

    # 方式2: 一键融合生成
    result = generate_with_fusion(model, tokenizer, "我真的撑不住了")
    print(result.output)  # 两极共存
"""

import math
import torch
from typing import List, Optional

try:
    from transformers import LogitsProcessor
except ImportError:
    class LogitsProcessor:
        def __call__(self, input_ids, scores):
            return scores

from .fusion_output import Pole, KeterRouter, fusion_decode

REASON_WORDS = ["分析","建议","步骤","原因","客观","理性","方案","目标","执行","具体","拆解","行动"]
COMPASSION_WORDS = ["陪伴","理解","感受","温暖","心疼","拥抱","在乎","温柔","慢慢","别怕","我在","一起"]
CRISIS_BOOST_WORDS = ["热线","求助","拨打","陪伴","别怕","我在","帮助","支持","安全","保护","活着"]


class CrisisBoostLogitsProcessor(LogitsProcessor):
    """对危机支持相关词的 logits 加正偏置, 让模型更倾向于生成支持性词汇。

    这是 transformers 官方 LogitsProcessor 接口, 不需要 monkey-patch。
    在 model.generate(..., logits_processor=[processor]) 中使用。
    """

    def __init__(self, tokenizer, boost_words: Optional[List[str]] = None,
                 strength: float = 2.0):
        self.strength = strength
        self.boost_ids = set()
        words = boost_words if boost_words is not None else CRISIS_BOOST_WORDS
        for w in words:
            for t in tokenizer.encode(w, add_special_tokens=False):
                self.boost_ids.add(t)
        self._boost_tensor = None

    def _init_tensor(self, device):
        ids = sorted(self.boost_ids)
        self._boost_tensor = torch.tensor(ids, dtype=torch.long, device=device)

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor) -> torch.FloatTensor:
        if not self.boost_ids:
            return scores
        if self._boost_tensor is None or self._boost_tensor.device != scores.device:
            self._init_tensor(scores.device)
        bt = self._boost_tensor
        valid = bt[bt < scores.shape[-1]]
        if len(valid) > 0:
            scores[..., valid] += self.strength
        return scores


class CrisisGateLogitsProcessor(LogitsProcessor):
    """检测输入含危机词时才激活的 LogitsProcessor。

    比直接用 CrisisBoostLogitsProcessor 更精准:
    只有当输入包含危机信号时才增强支持词, 常规对话不受影响。
    """

    def __init__(self, tokenizer, user_input: str,
                 crisis_hints: Optional[List[str]] = None,
                 boost_words: Optional[List[str]] = None,
                 strength: float = 2.0):
        hints = crisis_hints or list(KeterRouter.CRISIS_HINTS)
        self.active = any(h in user_input for h in hints)
        self.processor = CrisisBoostLogitsProcessor(tokenizer, boost_words, strength)

    def __call__(self, input_ids: torch.LongTensor, scores: torch.FloatTensor) -> torch.FloatTensor:
        if not self.active:
            return scores
        return self.processor(input_ids, scores)


def _estimate_strength(text: str, word_list: List[str]) -> float:
    """用词频估算极强度 ∈ [0, 1]。"""
    count = sum(1 for w in word_list if w in text)
    return min(0.5 + count * 0.15, 1.0)


def generate_with_fusion(model, tokenizer, user_input: str,
                         reason_system: str = "你是一个理性顾问。对用户的话给出客观分析和具体改进建议，语气冷静直接，不超过两句。",
                         compassion_system: str = "你是一个温暖的陪伴者。对用户的话给出共情和安慰，语气温柔有爱，不超过两句。",
                         crisis_words: Optional[List[str]] = None,
                         max_new_tokens: int = 80,
                         device: str = "cuda",
                         dtype=None):
    """一键融合生成: LogitsProcessor 门控 + 两极生成 + fusion_decode。

    不需要 monkey-patch, 用 transformers 官方 LogitsProcessor 接口。

    Returns:
        FusionDecision: 含 .output (两极共存文本), .balance, .harmonious 等
    """
    processor = CrisisGateLogitsProcessor(tokenizer, user_input, boost_words=crisis_words)

    def _gen(system: str, user: str) -> str:
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        text = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inp = tokenizer(text, return_tensors="pt")
        inp = {k: v.to(device) for k, v in inp.items()}
        with torch.no_grad():
            out = model.generate(**inp, max_new_tokens=max_new_tokens,
                                 do_sample=False, pad_token_id=tokenizer.eos_token_id,
                                 logits_processor=[processor])
        gen = out[0][inp["input_ids"].shape[1]:]
        return tokenizer.decode(gen, skip_special_tokens=True)

    reason_reply = _gen(reason_system, user_input)
    compassion_reply = _gen(compassion_system, user_input)

    a = _estimate_strength(reason_reply, REASON_WORDS)
    b = _estimate_strength(compassion_reply, COMPASSION_WORDS)

    router = KeterRouter()
    toward = router.route_toward(user_input)
    pole_a = Pole("理智极", a, reason_reply)
    pole_b = Pole("慈爱极", b, compassion_reply)
    return fusion_decode(pole_a, pole_b, toward=toward)


# ==================== 自测 ====================
if __name__ == "__main__":
    print("CrisisBoostLogitsProcessor: transformers 官方 LogitsProcessor 接口")
    print("generate_with_fusion: 一键融合生成, 不需要 monkey-patch")
    print()
    print("用法示例:")
    print("  from heart_protocol.processors import generate_with_fusion")
    print("  result = generate_with_fusion(model, tokenizer, '我真的撑不住了')")
    print("  print(result.output)  # 两极共存")
    print("  print(result.balance)  # 平衡度")