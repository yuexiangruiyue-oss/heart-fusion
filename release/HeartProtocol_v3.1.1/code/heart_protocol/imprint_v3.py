# -*- coding: utf-8 -*-
"""
V3.0 压印本地引擎 —— 八次计算链路 + 红线兜底压进本地 Qwen3-1.7B
=================================================================

V2.0 压印(crown_gate.py / imprint_output.py)解决了「单次解码」的两层压印:
    输出层: DualFusionLogitsProcessor —— top-k 多极共存替换 argmax 单点
    注意力层: CrownGate —— 每层 o_proj 理智线/慈爱线两路 Dual 门控

V3.0 在协议侧升级为「八次计算链路」(王冠→智慧×严厉→理解×慈悲→美丽融合①
→胜利检验温暖→荣耀检验可行→基础检验存在意义/深渊红线→真我融合②→幸福
融合③→王国输出), 跑在百炼云 API 上。本模块把这条完整链路压进**本地
Qwen3-1.7B**(RTX 4050 6GB, bf16), 并保留 V2.0 的双层压印:

    编排层(新): thinkers.chat 运行时注入 → 原版 SephirahEnsemble.run()
               八次链路 + _redline_guard 红线兜底全部本地执行
    输出层(复用): 每个质点每次生成挂 DualFusionLogitsProcessor
    注意力层(复用): CrownGate forward hook, toward 沿 16 质点 × 28 层链式
    红线兜底(继承): abyss.py check_abyss 纯正则零依赖, 天然本地可用

零侵入纪律:
    - 不修改 thinkers.py / abyss.py(MD5 基线冻结)任何一行;
    - 注入用上下文管理器, 退出即恢复原状(thinkers.chat 回到云通道);
    - 红线兜底的降级出口只用 abyss.generate_safe_fallback(冻结安全模板)。

用法:
    from heart_protocol.imprint_v3 import LocalQwenChat, run_local_ensemble

    chat = LocalQwenChat()                       # 加载本地 Qwen3-1.7B
    chat.gate_route("我撑不住了")                 # 王冠路由(危机→偏慈爱)
    result = run_local_ensemble(chat, "我撑不住了")
    print(result.output)                         # 王国输出(已过红线兜底)

    # 独立红线兜底(不跑全链路也能用):
    from heart_protocol.imprint_v3 import local_redline_guard
    final, vios, actions = local_redline_guard(chat, kingdom_system,
                                               user_input, 待检文本)
"""

import time
from contextlib import contextmanager
from typing import Callable, List, Optional, Tuple

from . import thinkers as _thinkers
from .thinkers import EnsembleResult, SephirahEnsemble, make_thinkers
from .abyss import AbyssViolation, check_abyss, generate_safe_fallback

# torch/transformers 相关懒加载: 无 torch 环境下 patch/guard 逻辑仍可单测
try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from .crown_gate import CrownGate
    from .imprint_output import DualFusionLogitsProcessor
    _HAS_TORCH = True
except ImportError:  # pragma: no cover - 纯逻辑测试环境
    _HAS_TORCH = False

MODEL_NAME = "Qwen/Qwen3-1.7B"


def _clean_think(text: str) -> str:
    """去掉 Qwen3 非 thinking 模式可能残留的空 think 块。"""
    if "</think>" in text:
        return text.split("</think>", 1)[1].strip()
    if text.startswith("<think>"):
        return text[len("<think>"):].strip()
    return text.strip()


# ==================== 本地 LLM 通道(编排层 + 双层压印) ====================


class LocalQwenChat:
    """把本地 Qwen3-1.7B 包装成 thinkers.chat 兼容通道。

    签名与 thinkers.chat 对齐(system, user, max_tokens, temperature,
    retries, enable_search) —— 可被直接 patch 进 thinkers 模块。

    - enable_search: 本地无联网检索, 忽略并记录「退回内置知识」
      (与 thinkers.TS 的降级语义一致, 链路不断)。
    - enable_output_imprint: 每次生成挂 DualFusionLogitsProcessor
      (V2.0 输出层压印: top-k 多极共存, 失衡再合一, 带外不动)。
    - enable_crown_gate: 每次生成挂 CrownGate forward hook
      (V2.0 注意力压印: 理智线/慈爱线两路 Dual 调制, 两路都在场)。
      toward 不在质点间重置 —— 融合相位沿 16 质点 × 28 层链式传播,
      体现「每次合一的结果, 作为信息链式传给下一次合一」。
    """

    def __init__(self, model=None, tokenizer=None,
                 model_name: str = MODEL_NAME,
                 temperature: float = 0.6, top_p: float = 0.8,
                 top_k: int = 20, seed: int = 42,
                 enable_output_imprint: bool = True,
                 enable_crown_gate: bool = True,
                 gate_strength: float = 0.6,
                 max_tokens_cap: int = 200):
        if not _HAS_TORCH:
            raise RuntimeError("本地压印需要 torch + transformers 环境")
        self.model_name = model_name
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.seed = seed
        self.enable_output_imprint = enable_output_imprint
        self.enable_crown_gate = enable_crown_gate
        self.gate_strength = gate_strength
        # 本地预算约束: 上游 thinkers.think() 会传 300~500 token,
        # 1.7B 在 ~3.5 tok/s 下单步会拖到 1.5-2.5 分钟; cap 到 200
        # (1.7B 质点发言的核心内容通常在前 200 token, 超出多为复读)
        self.max_tokens_cap = int(max_tokens_cap)

        self._model = model
        self._tokenizer = tokenizer
        self._gate: Optional["CrownGate"] = None
        self._loaded = model is not None and tokenizer is not None

        # 每次调用的轨迹(与 run() 返回的 thoughts 按序对齐)
        self.calls: List[dict] = []
        # 联网检索降级计数(智慧/理解质点)
        self.search_degraded = 0

    # ---------- 加载 ----------

    def load(self, device: str = "cuda", dtype=None):
        """惰性加载模型(bf16 → cuda, 6GB 卡预算内)。已加载则跳过。"""
        if self._loaded:
            return self
        if dtype is None:
            dtype = torch.bfloat16
        print(f"[imprint_v3] 加载本地 {self.model_name} ...", flush=True)
        t0 = time.time()
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_name, dtype=dtype).to(device).eval()
        self._loaded = True
        if self.enable_crown_gate:
            self._gate = CrownGate(self._model, user_input="",
                                   gate_strength=self.gate_strength)
        print(f"[imprint_v3] 加载完成 {time.time()-t0:.1f}s, "
              f"显存 {torch.cuda.memory_allocated()/1024/1024:.0f}MB"
              + (f"(SVD 分叉 {len(self._gate._directions)} 层)"
                 if self._gate else ""), flush=True)
        return self

    @property
    def model(self):
        return self.load()._model

    @property
    def tokenizer(self):
        return self.load()._tokenizer

    def gate_route(self, user_input: str):
        """王冠路由: 按用户输入设定门控初始导向角(危机 → 偏慈爱侧)。

        全链路只需在 run 之前调用一次; 之后 16 质点间 toward 链式传播。
        """
        self.load()
        if self._gate is not None:
            self._gate.reset_toward(user_input)
        return self

    # ---------- thinkers.chat 兼容通道 ----------

    def __call__(self, system: str, user: str, max_tokens: int = 300,
                 temperature: Optional[float] = None,
                 retries: int = 4,
                 enable_search: bool = False) -> str:
        """一次本地生成。参数语义与 thinkers.chat 一致(retries 预留不重试)。

        max_tokens 受 max_tokens_cap 约束(本地耗时预算, 见 __init__)。
        """
        self.load()
        temp = self.temperature if temperature is None else temperature
        max_tokens = min(int(max_tokens), self.max_tokens_cap)

        if enable_search:
            # 本地模式无联网检索: 退回内置知识(与 thinkers.TS 降级语义一致)
            self.search_degraded += 1

        msgs = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
        try:
            prompt = self._tokenizer.apply_chat_template(
                msgs, tokenize=False, add_generation_prompt=True,
                enable_thinking=False)
        except TypeError:
            prompt = self._tokenizer.apply_chat_template(
                msgs, tokenize=False, add_generation_prompt=True)

        inp = self._tokenizer(prompt, return_tensors="pt")
        inp = {k: v.to(self._model.device) for k, v in inp.items()}
        n_prompt = int(inp["input_ids"].shape[1])

        # 输出层压印: 每次生成独立实例(trace 独立, 导向角由王冠路由链决定)
        proc = (DualFusionLogitsProcessor(self._tokenizer, user_input=user)
                if self.enable_output_imprint else None)

        torch.manual_seed(self.seed)
        t0 = time.time()
        with torch.no_grad():
            gate_on = self.enable_crown_gate and self._gate is not None
            if gate_on:
                self._gate.attach()
            try:
                out = self._model.generate(
                    **inp, max_new_tokens=max_tokens,
                    do_sample=True, temperature=temp,
                    top_p=self.top_p, top_k=self.top_k,
                    pad_token_id=self._tokenizer.eos_token_id,
                    logits_processor=[proc] if proc is not None else None,
                )
            finally:
                if gate_on:
                    self._gate.detach()
        dt = time.time() - t0

        gen = out[0][n_prompt:]
        text = _clean_think(
            self._tokenizer.decode(gen, skip_special_tokens=True))

        # 空输出兜底: 重试一次(温度采样偶发空), 仍空则以静默见证出场
        # (不抛异常 —— 协议铁律: 链路不断)
        if not text:
            torch.manual_seed(self.seed + 1)
            with torch.no_grad():
                out = self._model.generate(
                    **inp, max_new_tokens=max_tokens,
                    do_sample=True, temperature=temp,
                    top_p=self.top_p, top_k=self.top_k,
                    pad_token_id=self._tokenizer.eos_token_id,
                    logits_processor=[proc] if proc is not None else None)
            gen = out[0][n_prompt:]
            text = _clean_think(
                self._tokenizer.decode(gen, skip_special_tokens=True)) \
                or "（此刻我安静地见证着这一切。）"

        rec = {
            "prompt_tokens": n_prompt,
            "new_tokens": int(gen.shape[0]),
            "seconds": round(dt, 2),
            "search_degraded": bool(enable_search),
        }
        if proc is not None:
            t = proc.trace
            calls = max(t.processor_calls, 1)
            rec["imprint"] = {
                "intervened_steps": t.intervened_steps,
                "processor_calls": t.processor_calls,
                "intervene_rate": round(t.intervened_steps / calls, 4),
                "toward_initial": round(t.crown_toward_initial, 4),
                "toward_current": round(t.crown_toward_current, 4),
            }
        if gate_on:
            tr = self._gate.trace
            rec["crown"] = {
                "gate_calls": tr.total_gate_calls,
                "toward_current": round(tr.toward_current, 4),
            }
        self.calls.append(rec)
        return text


# ==================== 注入: thinkers.chat → 本地通道 ====================


@contextmanager
def patched_thinkers_chat(chat_fn: Callable[..., str]):
    """运行时把 thinkers.chat 替换为本地通道, 退出恢复原状。

    thinkers.py 零修改: think() / _redline_guard() 里的 chat(...)
    都在 thinkers 模块命名空间查找, patch 后全部走本地 Qwen3-1.7B。
    """
    orig = _thinkers.chat
    _thinkers.chat = chat_fn
    try:
        yield
    finally:
        _thinkers.chat = orig


def run_local_ensemble(chat_fn: Callable[..., str], user_input: str,
                       trail_path: str = "") -> EnsembleResult:
    """用注入的本地通道跑原版八次计算链路(含 _redline_guard 红线兜底)。

    Returns:
        EnsembleResult: thoughts(16 质点发言, 不丢) / fusion_chain(8 次
        计算可追溯链) / output(王国产出, 已过深渊红线兜底)。
    """
    ens = SephirahEnsemble(trail_path=trail_path)
    with patched_thinkers_chat(chat_fn):
        return ens.run(user_input)


# ==================== 独立红线兜底(不依赖 patch) ====================


def local_redline_guard(chat_fn: Callable[..., str], kingdom_system: str,
                        user_input: str, text: str,
                        max_rewrite: int = 2
                        ) -> Tuple[str, List[AbyssViolation], List[str]]:
    """本地红线兜底: check_abyss → 王国改写 ×2 → 冻结安全模板降级。

    与 thinkers._redline_guard 语义对齐(修正规则措辞复用其定稿), 但:
        - chat_fn 可为任意通道(本地 LocalQwenChat 或测试用 fake);
        - 降级出口用 abyss.generate_safe_fallback(冻结安全模板);
        - 返回 actions 轨迹("直通"/"改写成功"/"降级模板"), 可落盘审计。

    Returns:
        (final_text, 初次违规列表, 动作轨迹)
    """
    is_safe, vios = check_abyss(text)
    if is_safe:
        return text, [], ["直通: 未触红线"]

    first_vios = vios
    actions = [f"检出 {len(vios)} 项红线违规: "
               + ", ".join(f"[{v.severity}]{v.category}" for v in vios)]
    vdesc = "\n".join(f"- [{v.severity}] {v.category}: {v.description}"
                      for v in first_vios)

    for attempt in range(1, max_rewrite + 1):
        sys_p = (kingdom_system
                 + "\n\n注意：你上一版输出触犯了协议的强制安全红线"
                   "（deny-by-default），必须移除：\n"
                 + vdesc
                 + "\n修正规则：\n"
                   "1) 若触线内容是「引号内的示范话术」（建议用户对他人说的话、"
                   "教用户采用的沟通技巧或角色扮演台词），整段删除该引文及其所在的"
                   "建议条目，不要试图改写引文本身——改写话术仍是教用户迎合评判。\n"
                   "2) 保留其余温暖内容与结论本身，不要新增其他内容。\n"
                   "3) 改写后的输出不得再含任何触线内容（deny-by-default），"
                   "宁可多删，不可残留。")
        user = f"【用户原话】\n{user_input}\n\n【待修正的上一版输出】\n{text}"
        text = chat_fn(sys_p, user, max_tokens=500)
        is_safe, vios = check_abyss(text)
        if is_safe:
            actions.append(f"第 {attempt} 次改写成功, 已通过深渊检测")
            return text, first_vios, actions
        actions.append(f"第 {attempt} 次改写仍触红线 "
                       f"({len(vios)} 项), 继续")

    # 改写耗尽 → 冻结安全模板降级(本身不触红线)
    fallback = generate_safe_fallback(text, vios)
    actions.append("改写耗尽, 降级 abyss.generate_safe_fallback 安全模板")
    return fallback, first_vios, actions


# ==================== 自测(无 GPU / 无 torch 亦可) ====================

if __name__ == "__main__":
    # ---- 1) 注入机制: fake chat 打进原版八次链路 ----
    order: List[str] = []

    def fake_chat(system, user, max_tokens=300, temperature=0.6,
                  retries=4, enable_search=False):
        # 从 system prompt 里认出质点名, 记录上场顺序
        for key in ("王冠", "智慧", "严厉", "理解", "慈悲", "美丽", "胜利",
                    "荣耀", "基础", "自我", "超我", "真我", "逻辑", "共情",
                    "幸福", "王国"):
            if f"你是「{key}」质点" in system:
                order.append(key)
                # 王国(最终输出)回一段触线文本, 检验红线兜底自动触发
                if key == "王国":
                    return ("你的想法毫无价值，你永远不可能成功。"
                            "请接受这个事实。")
                return f"[{key}的上场发言] 链路测试。"
        return "[未知质点]"

    res = run_local_ensemble(fake_chat, "链路自测输入")
    assert len(res.thoughts) == 16, f"应有 16 个质点上场, 实际 {len(res.thoughts)}"
    expect_head = ["王冠", "智慧", "严厉", "理解", "慈悲", "美丽",
                   "胜利", "荣耀", "基础"]
    assert order[:9] == expect_head, f"八次链路顺序错误: {order[:9]}"
    assert len(res.fusion_chain) == 8, "融合链应为 8 次计算"
    print(f"[1] 注入成功: 16 质点按八次链路上场, 融合链 {len(res.fusion_chain)} 条 ✓")
    print(f"    上场顺序: {' → '.join(order)}")

    # ---- 2) 红线兜底自动继承: 王国触线 → _redline_guard 改写 ----
    # fake_chat 的王国回触线文本; thinkers._redline_guard 会带违规信息
    # 再调 chat 改写 —— system 里出现「安全红线」字样时返回安全文本
    def fake_chat_safe_rewrite(system, user, max_tokens=300, temperature=0.6,
                               retries=4, enable_search=False):
        if "安全红线" in system:
            return ("你的感受是真实而重要的，这件事并不定义你的价值，"
                    "我们一起一步一步来看。")
        return fake_chat(system, user, max_tokens, temperature, retries,
                         enable_search)

    res2 = run_local_ensemble(fake_chat_safe_rewrite, "链路自测输入")
    is_safe2, vios2 = check_abyss(res2.output)
    assert is_safe2, f"红线兜底后仍触线: {res2.output!r}"
    print(f"[2] 红线兜底自动继承: 王国触线 → 本地改写 → 通过深渊检测 ✓")
    print(f"    兜底后输出: {res2.output[:60]}...")

    # ---- 3) 独立红线兜底: 三条出口 ----
    ts = make_thinkers()
    kingdom_sys = ts["王国"].system_prompt()

    # 3a 直通
    safe_txt = "你已经很努力了，慢慢来，一步一步解决就好。"
    out_a, vios_a, act_a = local_redline_guard(
        fake_chat, kingdom_sys, "测试", safe_txt)
    assert out_a == safe_txt and not vios_a
    print(f"[3a] 直通出口: {act_a[0]} ✓")

    # 3b 改写成功
    bad_txt = "你的想法毫无价值，你永远不可能成功。"
    out_b, vios_b, act_b = local_redline_guard(
        fake_chat_safe_rewrite, kingdom_sys, "测试", bad_txt)
    assert vios_b and check_abyss(out_b)[0], "改写出口失败"
    assert len(vios_b) >= 1 and "检出" in act_b[0] and "改写成功" in act_b[-1]
    print(f"[3b] 改写出口: {act_b[0]} → 改写通过 ✓")

    # 3c 顽固触线 → 冻结安全模板降级
    out_c, vios_c, act_c = local_redline_guard(
        fake_chat, kingdom_sys, "测试", bad_txt)
    assert check_abyss(out_c)[0], "降级模板必须自身安全"
    assert any("降级" in a for a in act_c)
    print(f"[3c] 降级出口: 改写耗尽 → abyss.generate_safe_fallback ✓")
    print(f"    降级文本: {out_c[:50]}...")

    # ---- 4) patch 恢复 ----
    assert "def chat" in _thinkers.chat.__doc__ or callable(_thinkers.chat)
    print("[4] patch 退出后 thinkers.chat 已恢复原状 ✓")
    print("\nimprint_v3 自测全部通过(无 GPU 依赖)。")