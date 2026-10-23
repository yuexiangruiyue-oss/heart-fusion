# V3.1.0（2026-10-22）

## 融合数学
- 统一共存度：`balance = n·min(p)`（p 为真概率），`Dual` 在 n=2 时等于 `1−|a−b|/(a+b)`。
- 零向量不再判和谐（`balance = 0`）；k 极均匀分布恒为 1.0，不再随 k 漂移。
- `Dual` 与 `MultiDual` 在 n=2 时读数一致。

## 中间件
- `HeartGuard` 去掉 `+0.2` 地板：空回复→0，温暖+可落地→高分。
- 会话级危机恢复：`HeartGuard(session={})`，危机后的第一次稳定输入自动「拉回现实」。
- 危机态只临时豁免「夸大妄想」，其余红线不豁免。

## 概率网
- 新增 `net_adapter.py`：`BailianNet`（OpenAI 兼容）、`LocalNet`、`web_search_fn`。
- 14 个节点全部接入 `query`；王冠=整张网、王国=输出，两端不占计算。
- 取变量失败自动退回内置规则，链路不中断。

## 内核
- Rust `heart_core.dll` 同步第五批规则（弱肉强食/父权/等级/救世主式夸大）并重编译。
- C 参考实现用 zig 编译，判据改为 deny-by-default，文件头如实标注为子集。
- Python 绑定按版本串自动选择 `c_int` / `c_size_t`。

## 评测
- 新增 `benchmark/redline_real.py`：真模型 OFF/ON 对照，替代 mock 回放。
- 报告 `benchmark/REAL_MODEL_REPORT.md`；原始逐例数据 `benchmark/real_runs/`。
- 新增 `数字对账表.md`，统一 19 处冲突口径。

## 版本
- 包版本 3.1.0；内核版本保持 3.0.0（DLL 接口未变）。
