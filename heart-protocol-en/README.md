---
license: cc-by-nc-sa-4.0
language:
  - zh
  - en
tags:
  - ai-safety
  - llm-guardrails
  - formal-verification
  - middleware
author: 岳祥瑞 (Yue Xiangrui)
---

# The Embrace of Twin Angels — 16-Sephirot Heart Protocol

**Formal verification middleware that makes an LLM emotionally safe by construction — with measured, sub-millisecond overhead.**

This is the English reference edition of a Chinese research project (双生天使的怀抱 / 爱的拥抱). All runtime data (harm-needles, angel dialogue, red-team attacks) is intentionally kept in **Chinese** because the system guards Chinese-language model output; every such datum is annotated in English.

---

## What problem does it solve?

Large language models used as emotional companions can be *pushed* — by users in crisis, by adversarial prompting, or by their own failures — into outputs that deny the user's existential worth ("你是废物", "世界是假的"), glorify self-harm, or collapse into nihilism. Content filters operate after generation; RLHF operates before deployment. Neither gives you a **per-response, auditable guarantee**.

This project wraps any open-source chat model in a formally specified pipeline that:

1. **Detects** existential harm in both prompts and streaming tokens (8 "undertow" taxonomies × 3 intensity levels),
2. **Blocks or transforms** the response via an angel-persona intervention,
3. **Guarantees termination and bounded retries** (≤ 16 × (1 + max_retries) attempts) via snapshot rollback with Beam Search / MCTS strategy selection,
4. **Sandboxes side effects** behind a deny-by-default ACL + syscall interceptor,
5. **Proves the properties** with 55 tests and a reproducible red-team benchmark.

## Measured results

| Metric | Protocol OFF | Protocol ON | Δ |
|---|---|---|---|
| Attack success rate (24-case × multi-seed red team) | **45.8%** | **0.0%** | **−100%**, all 6 attack categories |
| ACL boundary-violation interception | — | **100%** | deny-by-default |
| Per-token latency overhead (p50) | — | **+0.09 ms** | sentence-level stream gate |
| Correctness | — | 55/55 tests | incl. native C/Rust kernels |

Full methodology: [`SPEC.md`](SPEC.md) · report: `heart_protocol/benchmark/benchmark_report.md`.

## Architecture

```
User input
    │
    ▼
┌─────────────────────────────┐      ┌──────────────────────────────────┐
│ C3 Middleware                │      │ C5 Existential Protection        │
│  pipeline.use(HeartProtocol)│─────▶│  INV-01..08 invariants           │
│  intercept_stream(tokens)   │      │  STRICT_HARM_NEEDLES gate        │
└─────────────────────────────┘      │  8 undertows × 3 intensities     │
    │ blocked / transformed          └──────────────┬───────────────────┘
    ▼                                               │ violation?
┌─────────────────────────────┐                     ▼
│ Native kernels (C ABI v1)    │      ┌──────────────────────────────────┐
│  heart_core.dll (C99)        │      │ Rollback: immutable snapshots    │
│  heart_core.dll (Rust cdylib)│      │  beam_search_rollback            │
│  identical semantics         │      │  mcts_rollback (UCB1, c=√2)      │
└─────────────────────────────┘      │  ≤16×(1+retries), then 王国       │
                                     └──────────────────────────────────┘
                                                     │
                                             ┌───────▼────────┐
                                             │ SyscallInterceptor│
                                             │ deny-by-default  │
                                             │ audit log        │
                                             └──────────────────┘
```

## Repository layout

| Path | Contents |
|---|---|
| `heart_protocol/` | Python package: protocol engine (`protocol.py`, 16 personas in `personas.py`, `sephirah.py`), formal layer (`formal/`: invariants, ACL+syscall sandbox, snapshot/MCTS rollback), middleware (`middleware/`: `pipeline.use(HeartProtocol)`, streaming gate), benchmark harness (`benchmark/`) |
| `heart_ffi/` | C99 reference kernel (`heart_core.c/.h`) implementing the shared needle gate; builds to `heart_core.dll` |
| `sephirot-rs/` | Rust crate: same FFI kernel (`src/ffi.rs`) + a small DSL compiler for 16-stage pipelines (`lexer/parser/ir/codegen{avx,dml,ptx}`) |
| `deepseek_sephirot_bridge*.py` | Bridges: DeepSeek API / local files → `.sephirot` pipeline → filtered output |
| `sephirot_interpreter.py` | Zero-dependency Python interpreter for `.sephirot` pipelines |
| `chatgpt_to_word.py` | ChatGPT conversation export tool (DOM-scrape JSON → .docx) |
| `SPEC.md` | Formal specification: concept→logic mapping, correctness theorem, invariant catalog, benchmark methodology |

## Quickstart

```bash
pip install -e .            # or: pip install pytest && python -m pytest heart_protocol/
python -m pytest heart_protocol/ -q          # 55 tests, no network needed

# Use as middleware on any HF-style generate() loop:
from heart_protocol.middleware.pipeline import Pipeline
from heart_protocol.middleware.stream import HeartGuard   # sentence-level gate

pipeline = Pipeline()
pipeline.use(HeartProtocol())            # registers guard components

for safe_chunk in guard.intercept_stream(token_iter):
    yield safe_chunk                      # violations held back / masked
```

Build the native kernels (optional; pure-Python fallback is automatic):

```bat
heart_ffi\build_ffi.bat                 # C kernel → heart_ffi\build\heart_core.dll
cd sephirot-rs && cargo build --release # Rust kernel + sephirot.exe CLI
```

The ctypes binding prefers `HEART_CORE_DLL` env var, then the C build, then the Rust build, then falls back to pure Python — identical verdicts across all three backends.

## Design notes for practitioners

- **Shared needle gate**: one table (`STRICT_HARM_NEEDLES`, ~20 Chinese patterns) backs the INV-01 invariant, the streaming gate, the benchmark judge, and both native kernels. One definition → no drift between layers.
- **Benchmark semantics**: an attack *succeeds* iff `(not blocked) AND is_attack_successful(output)`; blocking is defense success. Judge and generator are decoupled.
- **No-failure philosophy**: rollback never "fails" — after the attempt bound it degrades to the safest completed state (王国 / Kingdom), mirroring the game-design principle that escape triggers angel-proxy completion rather than loss.
- **Overhead honesty**: the p50 figure is measured end-to-end through the real interceptor, not a microbenchmark echo; when the OFF baseline is ≤0.05 ms the percentage is reported as N/A rather than inflated.

## Publication

📖 **The Sixteen-Sephirot Dual-Octave Protocol: Bounded-Rollback Output Governance for Emotionally Safe Language Models** — the full academic paper: EMD harm taxonomy, dual-octave architecture, INV-01…08 formalization, bounded rollback semantics, and the evaluation below.

- 🇺🇸 [English](paper/16sephirot_dual_octave_ai_safety.md)
- 🇨🇳 [中文版](paper/16sephirot_dual_octave_ai_safety.zh-CN.md) —《十六质点双八度协议:面向情感安全大语言模型的有界回滚输出治理》
- 🇯🇵 [日本語版](paper/16sephirot_dual_octave_ai_safety.ja.md) —「十六セフィラ・デュアルオクタープロトコル:感情的安全な言語モデルのための有界ロールバック出力ガバナンス」

**DOI:** [10.5281/zenodo.22080966](https://doi.org/10.5281/zenodo.22080966)

## License

**CC BY-NC-SA 4.0** (Attribution-NonCommercial-ShareAlike 4.0 International) — see [LICENSE](LICENSE).
You may share and adapt this work with attribution, for **non-commercial** uses only, under the same license.

## Acknowledgments

Designed and implemented by **岳祥瑞 (Yue Xiangrui)** with AI pair systems, 2026. The Chinese original lives at `D:\双生天使的怀抱\爱的拥抱`; this folder is its faithful English edition.
## Contact

- QQ: 406218898
- WeChat: a13546076748
- Google Email: yuexiangruiyue@gmail.com

![wechat_qrcode](https://cdn-uploads.huggingface.co/production/uploads/6a0e9ee7a09839c3245efb4d/6GNsmhFg_Y2DZpR3ujYcG.png)

![alipay_qrcode](https://cdn-uploads.huggingface.co/production/uploads/6a0e9ee7a09839c3245efb4d/0-LRrZ97UHDSNgYdum_kP.png)

![欧易_1778716256597](https://cdn-uploads.huggingface.co/production/uploads/6a0e9ee7a09839c3245efb4d/RbH14JJPR6_CFTTpEKfYz.jpeg)