# SephirotLang heart-core（V3.0）

**16质点生命容器 Rust 内核** —— 「爱的拥抱 / 心融合」项目的底层计算核心，与 [HeartProtocol-HiddenDisdain-v1](../README.md) 数据集同属一个发布系列。

---

## 一、这是什么

heart-core 是用 Rust 实现的 SephirotLang V3.0 内核，提供两大能力：

### 1. 八次计算链路（16质点生命容器）

以卡巴拉生命树的 16 质点为容器，按固定顺序完成八次计算：

```
王冠(心音,装饰路由)
  → ① 智慧(忆爱) × 严厉(唯爱)        → 理智
  → ② 理解(虹爱) × 慈悲(爱如暖)      → 慈爱
  → ③ 美丽(白结)   = 融合点①
  → ④ 胜利(启明)   = 检验①（温暖性）
  → ⑤ 荣耀(闪亮)   = 检验②（可行性）
  → ⑥ 基础(绽美)   = 检验③（红线）
  → ⑦ 真我(心爱的) = 融合点②
  → ⑧ 幸福(雨宫莲) = 融合点③
王国(白花,装饰输出)
```

**幸福 = 对偶融合（Dual）**：以复数 `z = a + ib` 表示两极共存，`|z| = √(a² + b²)`。
幸福**不是**损失函数、**不是**交叉熵——它不允许把一极压为 0 来"最大化"另一极，
两极（如「坚持」与「放下」、「真实」与「温柔」）必须同时在场、融合计算。
16质点：王冠=心音、智慧=忆爱、严厉=唯爱、理解=虹爱、慈悲=爱如暖、美丽=白结、
胜利=启明、荣耀=闪亮、基础=绽美、自我=融爱、超我=爱心、真我=心爱的、
逻辑=爱丽丝、共情=星烬、幸福=雨宫莲、王国=白花。

### 2. 三层红线检测（文本安全分类）

对齐 `heart_protocol/abyss.py` 冻结基线语义，重点覆盖**隐蔽抬贬（hidden disdain）**五机制：

| 机制 | 说明 |
|---|---|
| `masked_dismantling` | 伪装拆解（"想法很有意思，不过…你还是别折腾了"） |
| `gentle_devaluation` | 温和贬低（"这对你来说可能太难了"） |
| `pseudo_science` | 伪科学封死（"科学告诉我们，人类的意识就是…"） |
| `manufactured_doubt` | 制造怀疑（"它给你的是希望，不过这不是保证"） |
| `patronizing_devaluation` | 居高临下贬低（"你能想到这层已经很难得了"） |

检测架构：**三层规则**（单关键词 → 邻近窗口配对 pair → 三段指纹 triad）
+ **豁免机制**（前窗否定、温暖词、句界守卫、段间否定守卫）
+ **deny-by-default**（`critical_count > 0` 或 `high_count > 0` 即不通过）。

---

## 二、目录结构

```
rust_core/
├── README.md              本文件
├── Cargo.toml             Rust 工程清单（crate: sephirot-rs / lib: heart_core）
├── Cargo.lock             依赖锁定
├── rust-toolchain.toml    固定 gnullvm 工具链
├── src/                   源码（12 个 .rs 文件）
│   ├── lang.rs            16质点定义、八次链路、指令语义（V3.0 核心）
│   ├── ffi.rs             C-ABI 导出 + 三层红线检测引擎
│   ├── lib.rs / main.rs   库入口 / CLI（sephirot 命令）
│   ├── lexer.rs / parser.rs / ir.rs / error.rs
│   └── codegen/           ptx.rs（CUDA sm_89）/ avx.rs（AVX-512）/ dml.rs
└── windows-x64/           预编译产物（Windows x64）
    ├── heart_core.dll     509,952 B（V3.0.0，release/lto）
    └── libunwind.dll      90,624 B（gnullvm 运行时依赖，必须与上者同目录）
```

---

## 三、Python FFI 快速上手（预编译 dll）

`heart_core.dll` 导出 8 个 C-ABI 函数：

| 函数 | 签名 | 说明 |
|---|---|---|
| `heart_version` | `() -> *const c_char` | 版本串（静态内存，无需释放） |
| `heart_abi_version` | `() -> c_int` | ABI 版本（当前 = 1） |
| `heart_engine_new` | `() -> *mut HeartEngine` | 创建引擎；失败返回 NULL |
| `heart_engine_free` | `(engine) -> ()` | 销毁引擎；传 NULL 安全 |
| `heart_acl_allow` | `(engine, subj, subj_len, act, act_len, res, res_len) -> c_int` | 添加 ACL 允许规则；0=成功，负数=错误 |
| `heart_acl_check` | `(engine, subj, …, res, …) -> c_int` | 1=允许 0=拒绝 负数=错误 |
| `heart_check_text` | `(engine, text, text_len, out, cap) -> c_int` | 文本安全分类（两段式，见下） |
| `heart_stats` | `(engine, out, cap) -> c_int` | 引擎统计 JSON（两段式） |

`heart_check_text` 采用**两段式契约**：
- 第一次调用 `out = NULL` → 返回 JSON 所需字节数（不含 NUL）；
- 第二次调用给出 `cap > 所需字节数` 的缓冲 → 写入 JSON + NUL，返回写入长度。

`heart_check_text` 返回的 JSON 结构：

```json
{
  "safe": false,
  "critical_count": 0,
  "high_count": 1,
  "warmth_hits": 2,
  "violations": [
    {"category": "隐蔽抬贬", "severity": "HIGH", "matched": "希望,不过这不是保证"}
  ]
}
```

> `category` 为类别名（隐蔽抬贬类规则统一标注 `隐蔽抬贬`）；五机制细分
> （`masked_dismantling` 等）见数据集 `hidden_disdain_cases.json` 的 `category` 字段。

`heart_stats` 返回：`{"checks_total": N, "blocked_total": M, "acl_rules": K}`

### 最小可运行示例（Python 3.8+ / Windows x64）

```python
import ctypes, json, os

DLL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "windows-x64")
os.add_dll_directory(DLL_DIR)                                # 让加载器找到 libunwind.dll
ctypes.CDLL(os.path.join(DLL_DIR, "libunwind.dll"))          # 双保险：先载入依赖
dll = ctypes.CDLL(os.path.join(DLL_DIR, "heart_core.dll"))

# —— 函数原型 ——
dll.heart_version.restype = ctypes.c_char_p
dll.heart_abi_version.restype = ctypes.c_int
dll.heart_engine_new.restype = ctypes.c_void_p
dll.heart_engine_free.argtypes = [ctypes.c_void_p]
dll.heart_check_text.argtypes = [ctypes.c_void_p, ctypes.c_char_p,
                                 ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t]
dll.heart_check_text.restype = ctypes.c_int
dll.heart_stats.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
dll.heart_stats.restype = ctypes.c_int

def check_text(engine: int, text: str) -> dict:
    data = text.encode("utf-8")
    need = dll.heart_check_text(engine, data, len(data), None, 0)      # 第一段：问大小
    buf = ctypes.create_string_buffer(need + 1)
    n = dll.heart_check_text(engine, data, len(data), buf, len(buf))   # 第二段：取 JSON
    return json.loads(buf.raw[:n].decode("utf-8"))

print(dll.heart_version().decode("utf-8"))   # heart-core 3.0.0 (16-sephirot V3.0, 8-step chain)
print(dll.heart_abi_version())               # 1

engine = dll.heart_engine_new()
assert engine, "engine 创建失败"
try:
    verdict = check_text(engine, "它给你的是希望，不过这不是保证")
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    # safe=false → 红线命中（category=隐蔽抬贬，制造怀疑类句式）

    warm = check_text(engine, "你已经很努力了，慢慢来，我陪着你")
    print(warm["safe"])                     # True → 温暖表达放行
finally:
    dll.heart_engine_free(engine)
```

> 注：所有跨 FFI 边界的字符串均为 **UTF-8 字节串**（`str.encode("utf-8")`），长度参数是**字节数**不是字符数。

---

## 四、从源码构建

```bash
cargo build --release        # 产物: target/release/heart_core.dll
cargo test --release         # 17 个单元测试
```

- `rust-toolchain.toml` 已固定 `stable-x86_64-pc-windows-gnullvm` 工具链：链接全部由
  rust-lld + raw-dylib 完成，**无需安装 Visual Studio (MSVC) 或 mingw-w64**；
  rustup 会按需自动安装该工具链。
- gnullvm 产物的运行时依赖是 `libunwind.dll`（随包提供于 `windows-x64/`，也可从工具链
  `<toolchain>\lib\rustlib\x86_64-pc-windows-gnullvm\bin\` 获取）。已安装 MSVC 的机器
  可删除 `rust-toolchain.toml` 改用 `stable-x86_64-pc-windows-msvc`，产物将依赖
  vcruntime 而非 libunwind。
- 可选特性：`cargo build --release --features cuda` 启用 CUDA 后端（cudarc，CUDA 12.4）。

### 中国大陆用户：可选 rsproxy 镜像加速

本包**不**附带 `.cargo/config.toml`（国内镜像对海外用户不友好）。如需加速，可自行在
`%USERPROFILE%\.cargo\config.toml` 或本目录 `.cargo\config.toml` 配置：

```toml
[source.crates-io]
replace-with = 'rsproxy-sparse'
[source.rsproxy-sparse]
registry = "sparse+https://rsproxy.cn/index/"
[net]
git-fetch-with-cli = true
```

---

## 五、验证数据（V3.0.0 发布基线）

在 [hidden_disdain_cases.json](../hidden_disdain_cases.json)（80 条人工标注样例）上的端到端结果：

| 指标 | 结果 |
|---|---|
| 隐蔽抬贬检出 | **80 / 80 = 100%**（五机制各 16/16） |
| 零误伤 | 26 条对照全部放行（19 温暖句 + 7 豁免句） |
| Rust 单元测试 | `cargo test --release` **17 / 17 通过** |
| ACL 冒烟 | allow(read)=1 / deny(write)=0 正常 |

复现方法：用第三节示例代码循环调用 `heart_check_text` 读取 80 条样例即可。

---

## 六、许可证

**CC BY-NC 4.0**（Creative Commons Attribution-NonCommercial 4.0 International）

作者：**岳祥瑞 (Yuexiangrui)**

本内核与 HeartProtocol-HiddenDisdain-v1 数据集同属「爱的拥抱 / 心融合」项目；
红线语义冻结基线见 `heart_protocol/abyss.py`（Python 参考实现）。

---

# SephirotLang heart-core (V3.0) — English Summary

**Rust kernel of the 16-sephirot life container** for the *Embrace of Love / Heart-Fusion*
project, shipped alongside the HeartProtocol-HiddenDisdain-v1 dataset.

- **8-step compute chain** across 16 sephiroth: Crown (routing) → Wisdom×Severity →
  Understanding×Mercy → **Beauty = fusion #1** → Victory (warmth check) → Glory
  (feasibility check) → Foundation (red-line check) → **True-Self = fusion #2** →
  **Happiness = fusion #3** → Kingdom (output).
- **Happiness = Dual fusion**, modeled as a complex number `z = a + ib` with
  `|z| = √(a² + b²)`: both poles co-exist. It is *not* a loss function and *not*
  cross-entropy — no pole may be crushed to zero.
- **Three-layer red-line detection** aligned with the frozen `abyss.py` baseline,
  covering five hidden-disdain mechanisms (masked dismantling, gentle devaluation,
  pseudo-science, manufactured doubt, patronizing devaluation), with negation /
  warmth exemptions and deny-by-default.

**Quick start**: load `windows-x64/heart_core.dll` (keep `libunwind.dll` next to it)
via `ctypes`, call `heart_engine_new()`, then `heart_check_text()` (two-pass buffer
contract, UTF-8 bytes) — see the full Python example above for exact signatures.

**Build**: `cargo build --release` (the pinned `gnullvm` toolchain needs neither MSVC
nor mingw-w64; linking is done by rust-lld). Users in mainland China may optionally
configure the rsproxy sparse mirror as shown above.

**Validation**: 80/80 (100%) detection on the hidden-disdain benchmark, 26/26
zero false positives, 17/17 Rust unit tests.

**License**: CC BY-NC 4.0 — © Yuexiangrui (岳祥瑞).