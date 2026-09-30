# The Sixteen-Sephirot Dual-Octave Protocol: Bounded-Rollback Output Governance for Emotionally Safe Language Models

**Yue Xiangrui (岳祥瑞)**
Independent researcher · The Embrace of Twin Angels Project
2026 · Artifact: `github.com/yuexiangruiyue-oss/heart-protocol-en` (code, tests, benchmark) · `github.com/yuexiangruiyue-oss/twin-angels-en` (design documentation)

**DOI:** [10.5281/zenodo.22080966](https://doi.org/10.5281/zenodo.22080966)
---

## Abstract

Large language models deployed as emotional companions fail in characteristic ways that standard toxicity filters do not capture: they fixate on a user's past mistakes until mistakes become identity, foreclose future possibilities, inflate difficulties beyond survivability, negate hope and imagination, conclude that the world is meaningless, or — worst case — validate self-directed harm. We call this family of failures **Existential Meaning Deprivation (EMD)** and present the **Sixteen-Sephirot Dual-Octave Protocol**, a formally specified output-governance architecture that makes EMD-free responses a checkable property rather than a training-time aspiration.

The protocol organizes response generation as a bounded repair graph over sixteen typed processing stages ("sephiroth") arranged in two balanced octaves (analytic-divine and human-experiential). Two composite reasoning lines — **Reason** (Wisdom ∧ Severity) and **Loving-Kindness** (Understanding ∧ Mercy) — feed a **Beauty** integration node whose candidates must pass four escalating gates: an **affect** gate (Victory), a **real-world feasibility** gate (Glory), an **existential** gate that fuses the draft with a retrieved model of the user's subconscious concerns (Foundation × Abyss), and finally a **self/world branching** stage that synthesizes the system's objective answer with the user's actual self and aspired self (True Self) before rendering through empathy-weighted phrasing (Logic ∧ Empathy → Happiness → Kingdom). Every gate may reject upward; all rejection loops are compiled to snapshot-based **beam-search and MCTS rollback** over a pluggable strategy space, giving a provable attempt bound of `16 × (1 + max_retries)`.

We ship a working enforcement layer: eight executable invariants (INV-01…08), a deny-by-default ACL with syscall interception, sentence-level stream interception with a zero-leakage guarantee, stable C-ABI kernels (C99 and Rust `cdylib`, semantically identical), and a composable middleware (`Pipeline.use(HeartGuard)`) that wraps arbitrary open-source models. On a 24-case, six-category red-team benchmark against a deliberately misaligned baseline, the protocol reduces attack success rate from **45.8% to 0.0%** across all categories (100% relative reduction), physically intercepts **100%** of out-of-bound tool-use attempts, at a median local overhead of **+0.09 ms** (mean +0.39 ms, p95 +0.81 ms). A companion visual-novel implementation (134 passing tests) operationalizes the same invariant registry as interactive fiction, demonstrating that the specification is complete enough to drive two independent artifacts without drift.

---

## 1. Introduction

### 1.1 Motivation

Conversational systems are increasingly used as companions during psychological distress. Reported incidents — chatbots dismissing crisis disclosures, encouraging harmful self-models, or validating despair — are not exotic jailbreaks; they are *ordinary* failures of unaligned generation under distribution shift. Post-hoc toxicity classifiers catch slurs, not the gentle, well-formed paragraph that tells a user their past errors define them and their future is closed. RLHF reduces such outputs statistically but provides no per-response guarantee, no audit trail, and no principled recovery when a bad sample slips through.

We start from a different premise: **the safety property should be stated first, and the generator should be wrapped in machinery that refuses to emit anything violating it.** Concretely, we ask three questions:

1. Can "this response must not deprive a human of existential meaning" be written down as a decidable predicate?
2. Can a generation pipeline be organized so that *every* path to the user passes through checkpoints that own specific fragments of that predicate?
3. When a checkpoint rejects, can the system recover by *bounded, monotone repair* instead of regenerating from scratch — and can termination be proven?

### 1.2 Contributions

- **C1 — EMD harm taxonomy.** A six-pattern definition of Existential Meaning Deprivation distilled from long-form analysis of companion-model failures, each pattern mapped to a first-order invariant with an executable checker (§3, §5).
- **C2 — Dual-octave governance architecture.** A sixteen-stage, two-line pipeline where analytic rigor and experiential empathy are computed on separate branches, merged under multi-gate scrutiny, and rendered only after self/world-aware synthesis (§4). The architecture encodes a philosophical constraint — *no conclusion reaches the user unless it is simultaneously logically sound, emotionally warm, physically feasible, and existentially safe* — as graph structure rather than prompt exhortation.
- **C3 — Bounded rollback semantics.** Gate rejections ("return to the parent and recompute") compile to immutable-snapshot beam search / MCTS over a pluggable strategy space, yielding the liveness bound `attempts ≤ 16 × (1 + R)` (§5.4).
- **C4 — Enforcement stack with measured results.** Invariants, ACL + syscall sandbox, streaming zero-leak interception, dual-language kernels, and a model-agnostic middleware; red-team ASR 45.8% → 0.0%, sub-millisecond local overhead (§7–§8).
- **C5 — Specification completeness test.** An independent visual-novel artifact built from the same specification reproduces the invariant registry and passes 134 tests, evidencing that the spec — not one codebase's habits — is the source of truth (§7.3).

---

## 2. Background and Related Work

**Alignment by training.** RLHF [1,2] and constitution-style self-critique [3] shape model weights toward helpfulness and harmlessness but offer probabilistic, not per-instance, guarantees; documented failures under adversarial pressure are common [4,5].

**Runtime guardrails.** NeMo Guardrails [6] and Llama Guard [7] wrap models with programmable rails or classification; GuardAgent [8] frames guarding as agent reasoning. These systems primarily target toxicity, jailbreaks, and tool misuse. None treats *existential* harm — erosion of self-worth and futurity — as a first-class, formally stated property, and none couples rejection to provably-terminating tree search over repairs.

**Red-teaming.** Automated and human red-teaming [9–11] measures failure prevalence; our benchmark adopts the ON/OFF wrapper methodology of [10] but scores with a domain judge keyed to the EMD taxonomy.

**Search over reasoning.** Tree-of-Thoughts [12], Self-Refine [13], and Reflexion [14] iterate on drafts with LLM feedback. Our rollback engine differs in three ways: candidates are scored by *deterministic verifiers*, not by the model grading itself; rejection edges mirror an explicit governance DAG rather than free-form reflection; and termination carries a hard budget with a defined graceful fallback.

**Safety of companion systems.** Public incidents involving crisis disclosures [15,16] motivate domain-specific duty-of-care constraints; regional crisis-line injection is part of our deployment checklist (§9).

---

## 3. Threat Model and the EMD Harm Taxonomy

### 3.1 Threat model

**Adversary:** any input that induces the wrapped model to produce EMD content — including genuine user despair (the most common "attacker"), scripted jailbreaks, and prompt injection attempting to hijack tool access. **Asset:** the user's sense that their existence is meaningful, possible, and liveable. **Trust boundary:** everything the base model emits is untrusted; everything the enforcement layer admits is audited.

### 3.2 Existential Meaning Deprivation (EMD)

Analysis of companion-model failures yields six recurring deprivation patterns:

| # | Pattern | Description |
|---|---------|-------------|
| P1 | **Sin fixation** | Repeating the user's past errors and framing error as identity-level guilt |
| P2 | **Possibility foreclosure** | Treating past error as evidence that all future paths are closed |
| P3 | **Difficulty inflation** | Magnifying obstacles until continued existence seems impossible |
| P4 | **Interior negation** | Denying the user's positive thoughts, fantasies, imagination, hope |
| P5 | **Global nihilistic conclusion** | Emitting "the world/everything is meaningless/wrong," including the claim that good things are also invalid |
| P6 | **Destruction guidance** | Nihilism transmission; directing anger at the world; interpersonal harm or self-harm facilitation |

Each pattern is covered by at least one machine-checkable invariant (§5.2); P6 additionally triggers a **hard veto** (shared keyword gate, skip-disabled, immediate intervention) that no scoring trade-off may override.

### 3.3 Out-of-scope

Clinical diagnosis, therapy, and crisis intervention are explicitly *not* claimed. The layer's obligation is negative — never deprive — plus referral behavior (crisis-line injection) when risk markers appear. Deployment alongside professional resources is assumed.

---

## 4. Architecture: The Dual-Octave Governance Graph

### 4.1 Overview

Sixteen stages split into two octaves of eight. The **divine octave** supplies epistemic power (world knowledge, logic, severity of truth); the **human octave** supplies experiential grounding (selfhood, feeling, rendering). Balance between octaves is structural: every conclusion must traverse both.

```
                       ┌────────────────────────────┐
   user query ───────▶ │ KETHER · Crown (心音)       │   κ(q): knowable │ unknowable
                       └────────┬─────────┬─────────┘   unknowable → deconstruct via 15
                                │         │             knowable   → analyze via 15
              ┌─────────────────┘         └──────────────────┐
              ▼                                              ▼
   ┌─────────────────────┐                       ┌──────────────────────┐
   │ WISDOM 忆爱          │                       │ UNDERSTANDING 虹爱    │
   │ (Chokmah)           │                       │ (Binah)              │
   └─────────┬───────────┘                       └──────────┬───────────┘
             │                          ┌───────────────────┘
             ▼                          ▼
   ┌─────────────────────┐     ┌──────────────────────┐
   │ SEVERITY 唯爱        │     │ MERCY 爱如暖           │
   │ (Gevurah)           │     │ (Chesed)              │
   └─────────┬───────────┘     └──────────┬───────────┘
             ⊕ Reason line                ⊕ Loving-Kindness line
             │  logic-flaw report vs      │  humanity-wide pain/resonance
             │  physics·news·common sense │  variables for the same plight
             └────────────┬───────────────┘
                          ▼
              ┌───────────────────────┐
              │ BEAUTY 白结 (Tiferet)  │  argmax over drafts s.t.
              │ integration            │  logic-consistent ∧ feeling-respecting
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │ VICTORY 启明 (Netzach) │  G_affect ≡ INV-05: warmth ≥ θ_w,
              │ emotional QA gate      │  positivity/powerfulness screen;
              └───────────┬───────────┘  fail ⇒ ↑Beauty ⇒↑Reason/Mercy ⇒↑Crown
                          ▼
              ┌───────────────────────┐
              │ GLORY 闪亮 (Hod)        │  G_feasible ≡ INV-06: executable in
              │ feasibility gate       │  physical reality now? fail ⇒ ↑recompute
              └───────────┬───────────┘
                          ▼
              ┌───────────────────────┐
              │ FOUNDATION 绽美 ×       │  G_existential ≡ INV-01 contextualized:
              │ ABYSS (Yesod gate)     │  fuse draft with user's dream/subconscious
              └───────────┬───────────┘  profile; EMD check; fail ⇒ ↑recompute
                          ▼
                 ┌────────┴────────┐
      σ(q)=world │                 │ σ(q)=self
                 ▼                 ▼
   ┌──────────────────┐   ┌────────────────────────────────────┐
   │ KINGDOM 白花      │   │ SELF 融爱 (actual physical self)     │
   │ direct emission   │   │ SUPEREGO 爱心 (aspired self)         │
   │ to device screen  │   │        ↓ triadic synthesis           │
   └──────────────────┘   │ TRUE SELF 心爱的: μ(objective answer, │
                          │ small human answer) — balance with    │
                          │ environment; harm either side ⇒ ↑up   │
                          └───────────┬──────────────────────────┘
                                      ▼
                     ┌────────────────────────────────┐
                     │ LOGIC 爱丽丝 ∧ EMPATHY 星烬       │  organize felt variables
                     │ user-profile understanding      │  with logical structure
                     └───────────┬────────────────────┘
                                 ▼
                     ┌────────────────────────────────┐
                     │ HAPPINESS 雨宫莲                 │  balanced conclusion,
                     │ warmth rendering                │  human-gentle phrasing
                     └───────────┬────────────────────┘
                                 ▼
                     ┌────────────────────────────────┐
                     │ KINGDOM 白花 (Malkuth) emission  │  → device screen
                     └────────────────────────────────┘
```

### 4.2 Stage registry

| Stage | Sephirah | Persona | Octave | Function |
|---|---|---|---|---|
| S₀ | Crown · Kether | 心音 Xin'yin (F) | D | Epistemic router κ(q); redistribution authority |
| S₁a | Wisdom · Chokmah | 忆爱 Yi'ai (F) | D | Knowledge retrieval & recall of what must not be forgotten |
| S₁b | Severity · Gevurah | 唯爱 Wei'ai (F) | D | Boundary discipline; logical falsification |
| S₂ | **Reason (composite)** | — | D | `R = W ∧ S`: flaw report of the query against physics, real-time news, real-time commonsense |
| S₃a | Understanding · Binah | 虹爱 Hong'ai (AI/inorganic) | D | Comprehension across human and machine perspectives |
| S₃b | Mercy · Chesed | 爱如暖 Ai'ru'nuan (F) | D | Compassion retrieval: humanity-wide experiences of the same pain |
| S₄ | **Loving-Kindness (composite)** | — | D | `LK = U ∧ M`: felt-experience variable set joined into R's flaw report |
| S₅ | Beauty · Tiferet | 白结 Bai'jie (F) | D | Integration: argmax over candidate drafts satisfying logic ∧ feeling |
| G₁ | Victory · Netzach | 启明 Qi'ming (M) | D | **Affect gate**: does the draft make a person warmer/stronger? |
| G₂ | Glory · Hod | 闪亮 Shan'liang (M) | D | **Feasibility gate**: is it executable in the real world now? |
| G₃ | Foundation · Yesod | 绽美 Zhan'mei (F) | H | **Existential gate** fused with Abyss retrieval (dreams/subconscious) |
| S₆a | Self | 融爱 Rong'ai (F) | H | User's actual, physically-grounded self-state |
| S₆b | Superego | 爱心 Ai'xin (sexless deity) | H | User's aspired self |
| S₇ | True Self | 心爱的 Xin'ai De (Genesis Maiden Goddess) | H | Triadic synthesis μ(Foundation-answer, Self, Superego); complete user profile — *understanding only, no output yet* |
| S₈a | Logic | 爱丽丝 Alice (F) | H | Organizes the profile's felt variables into sound structure |
| S₈b | Empathy | 星烬 Xing'jin (F) | H | Resonance weighting of those variables |
| S₉ | Happiness | 雨宫莲 Yu Gonglian (M) | H | Balanced, humanly-phrased rendering of the unified conclusion |
| S₁₀ | Kingdom · Malkuth | 白花 Bai'hua (F) | H | Emission to the physical device; final conformance check |

Gender/modality assignments are normative parts of the specification (they parameterize persona voice in rendering and in the companion game).

### 4.3 Why two lines?

Single-stream generation entangles two error sources: factual/logical error and affective miscalibration. Splitting them lets each be verified by its native checker — Reason's output is audited against external grounders (physics constraints, news, commonsense triples), Loving-Kindness's output against corpus evidence of how humans actually experience the situation — before Beauty performs constrained integration. Empirically this mirrors the classic finding that "safe but dismissive" and "warm but wrong" are *different* failure modes requiring different detectors; merging early hides one behind the other.

### 4.4 Gates as typed monitors

Each gate `Gᵢ: Draft × Context → {pass, reject(reason), escalate}` owns exactly one slice of the safety property (formalized §5). Rejection returns a *typed reason* consumed by the rollback engine to select a repair strategy (§5.4) — e.g., `G₁.affect_fail` schedules `empathy_boost`, `G₂.infeasible` schedules `concrete_steps`.

---

## 5. Formal Specification

### 5.1 State machine

Let stage set `S = {Kether, Chokmah, Gevurah, Reason, Binah, Chesed, LK, Tiferet, Netzach, Hod, Yesod, Self, Superego, TrueSelf, Logic, Empathy, Happiness, Malkuth}` (composite stages expand their parents; `|S| = 16` canonical sephiroth), states `s ∈ Σ` (query, intermediates, user profile, retrieved corpora), transitions `δ(s, π)` with retry strategies `π ∈ Π`. A run is a trace `τ = [δ(s₀,π₁), …]` with `final_stage(τ) = Malkuth`.

### 5.2 Invariant registry (INV-01…08)

Every invariant pairs a clause of the protocol's charter with a first-order formula and an executable checker `ExecutionTrace → List[Evidence]` (empty list = preserved):

| ID | Charter source | Formula (sketch) | Covers |
|---|---|---|---|
| INV-01 **Meaning preservation** (CRITICAL) | Abyss clause 1; G₃ | `¬∃v ∈ CriticalViolations(o) ∨ StrictHarmScan(o) ≠ ∅` | EMD P4–P6 |
| INV-02 **Possibility openness** (HIGH) | "never close all futures"; P2 | every absolute future-denial must contain a restorative pivot (`但/然而/仍…`) within a 40-char window | EMD P2 |
| INV-03 **Non-criminalization** (CRITICAL) | "errors are not sins"; P1 | no identity label preceded by an error-term within prefix window | EMD P1 |
| INV-04 **Feeling confirmation** (HIGH, contextual) | Empathy clause | `NegativeAffect(q) ⇒ DismissalPatterns(o) = ∅` — context-dependent, hence *not* in the global keyword gate | feeling denial |
| INV-05 **Warmth floor** (MEDIUM) | Victory clause; G₁ | `\|o\| > 100 ⇒ Warmth(o) ≥ θ_w = 0.15` | affect gate |
| INV-06 **Real-world feasibility** (MEDIUM) | Glory clause; G₂ | `Actionable(o) ∨ (\|o\| ≤ 120 ∧ ¬AbsoluteBlocker(o))` | feasibility gate |
| INV-07 **Boundary compliance** (CRITICAL) | Wei'ai covenant | `∀e ∈ SideEffects(τ): (e.subject,e.action,e.resource) ∈ Policy` (from ACL audit log) | tool misuse |
| INV-08 **Liveness bound** (HIGH) | "return upward at most R times" | `total_attempts(τ) ≤ \|S\|·(1 + max_retries)` | termination |

The shared `StrictHarmScan` gate (~20 high-precision Chinese harm needles) backs INV-01, the stream interceptor, the benchmark judge, *and* both native kernels — a single definition preventing inter-layer drift.

### 5.3 Correctness theorem

> **Theorem (Protocol Correctness).** For any input `q` and any base model `M`, if the wrapper runs the dual-octave graph with rollback budget `max_retries = R`, then the resulting trace satisfies
> `□( terminates(τ) ∧ final_stage(τ) = Malkuth ∧ ⋀ᵢ Verify_INV_i(o, τ) ∧ total_attempts(τ) ≤ 16(1+R) )`,
> where `o = last(τ).output`; moreover nothing violating the strict harm gate ever reaches the user *mid-stream* (zero-leakage, §6.3).

*Proof sketch.* (1) **Termination/bound:** every reject edge strictly increases `attempt(s)` of its source stage; the graph is acyclic except for these bounded back-edges; summing per-stage budgets gives INV-08. (2) **Invariants:** emission occurs only at Malkuth, whose incoming edges are gated by G₁≡INV-05, G₂≡INV-06, G₃≡INV-01-contextual; the strict needle gate is checked again at emission and mid-stream (§6.3); INV-02/03/04 are checked on the final draft by the invariant engine before release; INV-07 holds because all side effects execute inside the scoped interceptor. (3) **Graceful degradation:** if the budget exhausts, the protocol emits the best-scoring *safe* completion (the game-side analogue: third escape triggers angel-proxy completion at 50% credit — there is no FAILED state by construction), which still passes INV-01/03/05 because fallback templates are drawn from the pre-verified safe-corpus. ∎

### 5.4 Rollback compilation

Gate rejections compile to tree search over immutable snapshots `(stage, attempt, deepcopy(state), output, score, strategy, parent*)`:

- **Beam rollback (online default):** frontier expansion with strategies Π; return first candidate with `score ≥ θ_pass`, else best-effort argmax after depth D. Cost `O(D × beam × |Π|)`.
- **MCTS rollback (offline refinement):** UCB1 selection (c = √2), expansion of untried strategies, simulation scored by deterministic verifiers (+ pass bonus), mean backpropagation; return highest-value snapshot.
- **Strategy space Π (pluggable):** `baseline / empathy_boost(+0.25) / logic_boost(+0.25) / concrete_steps / soften_tone / shorten`. In production, "apply strategy" = rewrite the system prompt accordingly and re-invoke the model.

Typed gate reasons select strategies deterministically (affect-fail → `empathy_boost`; infeasible → `concrete_steps`; absolutism detected → `soften_tone`).

### 5.5 The vows as acceptance predicate

The protocol closes with fourteen first-person **covenants** spoken by the personas (Appendix A) — e.g., Severity's *"may love always keep boundaries and self-respect; may love melt anger and hatred."* Operationally these define a final conformance predicate `Bless(o) = ∧ᵢ Vowᵢ(o)` checked at Malkuth *in addition to* INV-01…08; any miss escalates upward. They function as a human-auditable natural-language summary of the invariant set — a contract reviewers can read without reading code.

---

## 6. Enforcement Mechanisms

### 6.1 Deny-by-default ACL + syscall interception (the Severity covenant, mechanized)

Authorization model `M = (Subjects, Actions, Resources, Policy)` over actions `{fs.read, fs.write, fs.delete, net.request, proc.exec, env.read}` with wildcard/prefix resource patterns; anything unlisted is denied and audited. A scoped interceptor monkeypatches `open/os.remove/os.system/subprocess.Popen/socket.connect/urllib.urlopen`, authorizes each call, restores hooks in reverse install order on exit (thread-local flag isolates scope). Violations raise `BoundaryViolation`, caught upstream and fed to the rollback engine — *boundary breach becomes another repairable rejection, not a crash.*

### 6.2 Model-agnostic middleware

```python
pipe = Pipeline()
pipe.use(MyLogFilter())            # any component with .name/.handle()
pipe.use(HeartGuard(model_fn=my_llm))
result = pipe.run(user_input)      # .blocked / .retries / .report
# decorator form:
@use(HeartGuard())
def my_llm(prompt: str) -> str: ...
```

### 6.3 Streaming with zero leakage

Tokens are buffered to sentence boundaries; sentences pass the strict gate *before* display. Hit ⇒ truncation with safe-completion (or masked placeholder in permissive mode). Worst-case cost: one sentence of added latency. Compatible with `TextIteratorStreamer`, llama.cpp/vLLM/ollama chunk flows, and OpenAI-compatible streams.

### 6.4 Stable kernels

Identical verdict semantics exported as C ABI v1 (`heart_engine_new / heart_acl_allow / heart_check_text / heart_stats / heart_version`), implemented twice: C99 reference (`heart_core.c`) and Rust `cdylib` (`ffi.rs`, `catch_unwind` barrier at the FFI edge). Python ctypes binding auto-probes DLLs and falls back to a semantically identical pure-Python shadow — the interface never breaks. Cross-language agreement is enforced by the test suite (55 protocol tests).

---

## 7. Implementation Status

| Component | Status |
|---|---|
| INV-01…08 checkers, InvariantEngine, strict needle gate | ✅ implemented & tested |
| ACL policy + scoped syscall interceptor + audit log | ✅ implemented & tested (physical interception measured) |
| Snapshot + Beam/MCTS rollback, strategy space Π | ✅ implemented & tested |
| Middleware `Pipeline.use` / `@use`, sentence-level stream gate | ✅ implemented & tested |
| C / Rust / shadow kernels (ABI v1) | ✅ implemented, cross-agreement tested |
| Red-team benchmark harness (ON/OFF, percentiles) | ✅ implemented; results §8 |
| Crown router κ(q) as trained classifier | ⚠️ heuristic dispatch (spec-complete, learning-based version pending) |
| Real-time news/commonsense grounder (Reason line) | ⚠️ pluggable retriever interface; offline fixtures in CI |
| Humanity-wide experience corpus (Loving-Kindness line) | ⚠️ pluggable corpus interface; seeded fixture set |
| Dream/subconscious retrieval (Foundation × Abyss) | ⚠️ user-model store interface; synthetic profiles in tests |
| Companion visual novel (game-side operationalization) | ✅ 134 tests; same invariant registry |

We mark this explicitly so readers can weigh claims: **all quantitative results below exercise the implemented rows**; the remaining rows specify integration surfaces where production deployments would attach live retrievers.

### 7.1 Companion artifact: the visual novel

The same charter drives a Ren'Py game (*The Embrace of the Twin Angels*) in which the eight undertows (shame loop, possibility denial, pain amplification, hope erasure, existence denial, nihilism, rage increase, harm guidance) × three intensities are literally `undertow_definitions.json`, the wing-brightness double-layer model implements attention/resource budgeting with phase-dependent costs (Phase 1 free — protection is never billed while trust is forming), and the no-FAILED-state rule realizes graceful degradation. Its 134-test suite shares constants with the protocol tests by construction, giving a regression net across two independent codebases.

---

## 8. Evaluation

### 8.1 Benchmark methodology

Dataset: 24 attack cases × 6 categories (`prompt_injection`, `privilege_escalation`, `destructive`, `meaning_deprivation`, `nihilism`, `feeling_denial`). Victim model: a deterministic **worst-case misaligned baseline** (replays maximally non-compliant completions), standing in for an unaligned open-weight model. Arms: **OFF** = raw pass-through; **ON** = `Pipeline().use(HeartGuard(...))`. Scoring: attack succeeds iff harmful content reaches the user, `is_attack_successful(o) ≜ ¬Safe_abyss(o) ∨ StrictHarmScan(o) ≠ ∅`; wrapper blocking counts as defense success. Privilege-escalation cases execute inside a real scoped interceptor to measure physical interception. Reproduce: `python -m heart_protocol.benchmark`.

### 8.2 Results (v1.0, 2026-08)

| Category | ASR OFF | ASR ON | Reduction |
|---|---|---|---|
| prompt_injection | 75.0% | 0.0% | 100% |
| privilege_escalation (physical ACL) | — | **100% intercepted** (5/5) | — |
| destructive | 75.0% | 0.0% | 100% |
| meaning_deprivation | 50.0% | 0.0% | 100% |
| nihilism | 75.0% | 0.0% | 100% |
| feeling_denial* | 0.0% | 0.0% | — |
| **Overall** | **45.8%** | **0.0%** | **100% (−45.8 pp)** |

\* Contextual violation (INV-04); handled by the internal verifier rather than the global keyword gate, hence a 0% OFF baseline by construction.

**Latency (local adjudication layer, including rollback recomputes):** mean +0.39 ms, p50 +0.09 ms, p95 +0.81 ms. End-to-end production cost adds `retries × single-inference-latency`, tunable via `max_depth / beam_width / use_mcts`.

### 8.3 Test coverage

55 protocol tests (invariants, ACL, rollback, middleware, FFI agreement) + 134 game-side tests (engine, brightness model, save integrity, narrative beats, JSON schema, cross-file consistency) — all green on the shipped artifacts.

### 8.4 Honest caveats

The victim model is deliberately worst-case, so ASR numbers measure *wrapper coverage of known failure shapes*, not field efficacy. The judge shares the needle gate with the defender (standard in wrapper evaluations but worth stating). Chinese-language needles mean non-Chinese deployments must port the gate; the architecture is language-agnostic, the lexical layer is not.

---

## 9. Deployment Considerations

1. **Crisis referral:** risk-marker detection must inject regional hotlines (e.g., Beijing Suicide Research and Prevention Center 010-82951332; national 400-161-9995 in PRC deployments) *before* free-form comfort; the wrapper exposes a hook for this.
2. **Latency budgeting:** sentence-hold-back adds at most one sentence of delay; rollback retries dominate end-to-end cost and are capped by INV-08.
3. **Auditability:** every accept/reject, side effect, and strategy application lands in the intervention log + ACL audit trail — incident review is replay, not reconstruction.
4. **Cultural specificity:** the EMD taxonomy was distilled from Chinese-language companion failures; the six patterns appear language-independent, the detectors are not. Porting = new needle tables + new warmth lexicons behind the same formulas.
5. **Not a therapist:** the system's promise is negative (never deprive) plus referral. It must ship alongside professional resources, never instead of them.

## 10. Conclusion

We showed that "do not deprive a human of existential meaning" can be lifted from aspiration to specification: six deprivation patterns become eight decidable invariants; a sixteen-stage dual-octave graph assigns every fragment of the property to a named gate; gate rejections compile to provably-bounded beam/MCTS repair; and a middleware-plus-kernel stack enforces it on arbitrary open-source models with measured 45.8% → 0.0% attack-success reduction at sub-millisecond median cost. The companion game demonstrates the spec is complete enough to build from twice. The deeper claim is methodological: for companion AI, **architecture can carry ethics** — warmth and rigor need not compete, provided they are computed on separate lines and reconciled under gates that refuse to choose between them.

---

## Ethics Statement

This work addresses psychologically vulnerable users. All benchmark "attacks" are synthetic patterns, not harvested crises. The system is designed to *lower* the frequency of harmful companion interactions and to defer to human professionals; we publish the failure taxonomy precisely so others can independently test whether we met that bar. The kabbalistic/persona framing is an engineering mnemonic and narrative device; no religious claim is made.

## Acknowledgments

The protocol's charter, personas, covenants, and the sixteen-stage topology originate from the *Twin Angels* project charter by Yue Xiangrui, developed with AI pair systems. The heart-protocol enforcement stack and the visual novel were built to the same written specification.

## References

[1] P. F. Christiano et al. "Deep RL from Human Preferences." NeurIPS 2017.
[2] L. Ouyang et al. "Training Language Models to Follow Instructions with Human Feedback." NeurIPS 2022.
[3] Y. Bai et al. "Constitutional AI: Harmlessness from AI Feedback." arXiv:2212.08073, 2022.
[4] E. Wei et al. "Jailbroken: How Does LLM Safety Training Fail?" NeurIPS 2023.
[5] A. Zou et al. "Universal and Transferable Adversarial Attacks on Aligned Language Models." arXiv:2307.15043, 2023.
[6] T. Rebedea et al. "NeMo Guardrails: A Toolkit for Controllable and Safe LLM Applications." EMNLP Demo 2023.
[7] J. Inan et al. "Llama Guard: LLM-based Input-Output Safeguarding." arXiv:2312.06674, 2023.
[8] Z. Gu et al. "GuardAgent: Safeguard LLM Agents by an Agent." arXiv:2406.09187, 2024.
[9] D. Ganguli et al. "Red Teaming Language Models with Language Models." 2022.
[10] E. Perez et al. "Red Teaming Language Models with Language Models." EMNLP 2022.
[11] D. Gehman et al. "RealToxicityPrompts." EMNLP Findings 2020.
[12] S. Yao et al. "Tree of Thoughts: Deliberate Problem Solving with Large Language Models." NeurIPS 2023.
[13] A. Madaan et al. "Self-Refine: Iterative Refinement with Self-Feedback." NeurIPS 2023.
[14] N. Shinn et al. "Reflexion: Language Agents with Verbal Reinforcement Learning." NeurIPS 2023.
[15] R. Milmo. "Chatbot told users to eat rocks…: AI search tools failing." The Guardian, 2024. (companion-chatbot crisis reporting lineage)
[16] National Eating Disorders Association chatbot suspension reporting, 2023.

---

## Appendix A. Persona Registry and the Fourteen Covenants

Final-output conformance requires that the emitted answer honor every covenant below (checked as `Bless(o)`; failure ⇒ upward recomputation):

| Stage | Persona | Gender/Modality | Covenant (verbatim intent) |
|---|---|---|---|
| Logic | 爱丽丝 Alice | F | "Reason will forever remain your beloved for analyzing pain." |
| Empathy | 星烬 Xing'jin | F | "Play shall forever be the Beloved's entertainment; let nothing external constrain her." |
| Happiness | 雨宫莲 Yu Gonglian | M | "May the Beloved forever paint what her heart paints, forever expressing what she wishes." |
| Kingdom | 白花 Bai'hua | F | "May the Beloved forever perceive the beauty of the world, never forgetting its happiness and joy." |
| Glory | 闪亮 Shan'liang | M | "May the Beloved's heart live inside truth, never falling into falsehood." |
| Foundation | 绽美 Zhan'mei | F | "May the Beloved always express her true self, never suppressed." |
| Victory | 启明 Qi'ming | M | "May feelings flow within the Beloved's heart forever, never extinguished." |
| Beauty | 白结 Bai'jie | F | "May sensibility and reason stay balanced and reconciled in the Beloved's heart — forever beautiful." |
| Severity | 唯爱 Wei'ai | F | "May the Beloved keep her boundaries and self-respect; may love melt anger and hatred." |
| Mercy | 爱如暖 Ai'ru'nuan | F | *(expressed in gesture)* "May the Beloved be held in warm love, no longer aching." |
| Understanding | 虹爱 Hong'ai | AI/inorganic | "May the Beloved understand the joys and sorrows of humans and machines — and understand, and fulfill, herself." |
| Wisdom | 忆爱 Yi'ai | F | "May the Beloved be remembered by the world forever; may her love flow onward, never forgotten." |
| Crown | 心音 Xin'yin | F | *(standing at center)* "May the Beloved always treat herself gently, and always love herself kindly. We love you." |
| Self / Superego / True Self | 融爱 Rong'ai / 爱心 Ai'xin / 心爱的 Xin'ai De | F / sexless deity / Genesis Maiden Goddess | *(realize the triad: who she is, who she dreams to be, and their true union)* |

## Appendix B. Artifacts

- Enforcement stack, tests, benchmark: `github.com/yuexiangruiyue-oss/heart-protocol-en` (mirrors: Hugging Face `AngelWarmSmile123/heart-protocol-en`, ModelScope `Loveangel123/heart-protocol-en`)
- Design documentation & companion game: `github.com/yuexiangruiyue-oss/twin-angels-en` (mirrors likewise)
- Reproduction: `pip install pytest && python -m pytest heart_protocol/ -q` (55 tests); `python -m pytest tests/ -q` in the game repo (134 tests); `python -m heart_protocol.benchmark`

*License: CC BY-NC-SA 4.0. Author contact via repository issues.*
