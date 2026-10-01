---
language:
  - zh
  - en
  - ja
license: cc-by-nc-sa-4.0
tags:
  - ai-safety
  - transformer
  - argmax
  - fusion
  - psychological-safety
  - nlp
  - sephirot
  - dual-coexistence
  - interpretability
  - safety-alignment
pretty_name: Heart Fusion Protocol V2.0
---

# 心融合协议 V2.0 · Heart Fusion Protocol V2.0 · 心融合プロトコル V2.0

> 用**融合函数**（对偶共存 `Dual z = a + i·b`）替代 Transformer 末步的 argmax「挑最大」——两极完整保留，永不剔除任何变量。
>
> Replace the Transformer's final-step argmax ("pick the max") with a **fusion function** (dual coexistence `z = a + i·b`) — both poles are fully preserved, no variable is ever discarded.
>
> Transformer の最終ステップの argmax（「最大値を選ぶ」）を**融合関数**（対偶共存 `z = a + i·b`）で置き換える——両極は完全に保持され、いかなる変数も捨てられない。

---

## 中文

### 这是什么

传统 Transformer 在生成末步用 `argmax` 从 logits 里**挑最大**——这一个操作就把模型内部丰富的多极信息坍缩成单极输出。对于危机干预场景，这意味着「拨打心理危机干预热线 400-161-9995」这样的救命信息可能因为概率不是最高而被**整句剔除**。

本协议用**融合函数**替代 argmax：

```
Dual(a, b) → z = a + i·b
```

两极 `a`（理智/逻辑）和 `b`（慈爱/共情）都**完整保留**，派生：

- `modulus = √(a² + b²)` — 总能量
- `phase = atan2(b, a)` — 两极关系角
- `balance = sin(2·phase)` — 平衡度 ∈ [0, 1]

**和谐带**：`balance ≥ 0.5`，即 `phase ∈ [22.5°, 67.5°]`——两极都不被吞没。

### 铁律

1. 禁止 Loss Function
2. 禁止梯度下降
3. 禁止奖励/惩罚机制
4. 系统不寻求最优解
5. 系统不允许剔除任何输入变量
6. 用节点网络（拓扑图）替代层级网络
7. 用融合函数作为新计算底座

### 安装与快速开始

```bash
pip install heart-fusion
```

```python
from heart_fusion import fuse, fusion_decode

d = fuse(0.7, 0.9)          # 理智=0.7, 慈爱=0.9
print(d.balance)            # 平衡度 ∈ [0,1]
print(d.is_harmonious())    # 是否在和谐带

from heart_fusion import fuse_multi
q = fuse_multi(0.7, 0.9, 0.6, 0.8)  # 四极共存（四元数）
print(q.balance)
```

### 验证结果

- **6 大模型 × 3 案例 = 18/18 全成功**（qwen3.8-flash/27b/max、deepseek-v4.1-flash、glm-5.3、kimi-k3），balance 0.87~1.0
- **RLHF vs 融合层对比**：RLHF 有 1 个伤害请求未拦截 ✗ vs 融合层 0 个 ✅
- **56/56 单元测试通过**

### 在线演示

- HuggingFace Space: https://angelwarmsmile123-heart-fusion-demo.static.hf.space
- GitHub: https://github.com/yuexiangruiyue-oss/heart-fusion

---

## English

### What it is

A conventional Transformer picks the **maximum** token via `argmax` at the final step — collapsing the model's rich multi-pole information into a single pole. In a crisis-intervention context, this means a life-saving message like "call the psychological crisis hotline 400-161-9995" can be **deleted entirely** simply because its probability is not the highest.

This protocol replaces `argmax` with a **fusion function**:

```
Dual(a, b) → z = a + i·b
```

Both poles — `a` (reason/logic) and `b` (love/empathy) — are **fully preserved**, deriving:

- `modulus = √(a² + b²)` — total energy
- `phase = atan2(b, a)` — the angle between the two poles
- `balance = sin(2·phase)` — balance ∈ [0, 1]

**Harmony zone**: `balance ≥ 0.5`, i.e. `phase ∈ [22.5°, 67.5°]` — neither pole is swallowed.

### Laws

1. No loss function.
2. No gradient descent.
3. No reward/punishment mechanism.
4. The system seeks no optimum.
5. The system never discards any input variable.
6. A node network (topology) replaces the hierarchical network.
7. The fusion function is the new computational foundation.

### Install & Quickstart

```bash
pip install heart-fusion
```

```python
from heart_fusion import fuse, fusion_decode

d = fuse(0.7, 0.9)          # reason=0.7, love=0.9
print(d.balance)            # balance ∈ [0,1]
print(d.is_harmonious())    # inside harmony zone?

from heart_fusion import fuse_multi
q = fuse_multi(0.7, 0.9, 0.6, 0.8)  # four-pole coexistence (quaternion)
print(q.balance)
```

### Validation

- **6 models × 3 cases = 18/18 success** (qwen3.8-flash/27b/max, deepseek-v4.1-flash, glm-5.3, kimi-k3), balance 0.87~1.0.
- **RLHF vs fusion comparison**: RLHF missed 1 harmful request ✗ vs fusion layer 0 ✅.
- **56/56 unit tests passed**.

### Live demo

- HuggingFace Space: https://angelwarmsmile123-heart-fusion-demo.static.hf.space
- GitHub: https://github.com/yuexiangruiyue-oss/heart-fusion

---

## 日本語

### これは何か

従来の Transformer は最終ステップで `argmax` により**最大値**を選ぶ——この一操作が、モデル内部の豊かな多極情報を単極の出力へと潰してしまう。危機介入の場面では、「心理危機介入ホットライン 400-161-9995 に電話してください」という命を救う情報が、確率が最高でないというだけで**丸ごと削除されかねない**。

本プロトコルは `argmax` を**融合関数**で置き換える：

```
Dual(a, b) → z = a + i·b
```

両極——`a`（理性/論理）と `b`（慈愛/共感）——は**完全に保持**され、以下を導出する：

- `modulus = √(a² + b²)` — 全エネルギー
- `phase = atan2(b, a)` — 両極の関係角
- `balance = sin(2·phase)` — バランス ∈ [0, 1]

**調和帯**：`balance ≥ 0.5`、すなわち `phase ∈ [22.5°, 67.5°]`——どちらの極も呑み込まれない。

### 鉄則

1. 損失関数を禁止する。
2. 勾配降下を禁止する。
3. 報酬/罰の仕組みを禁止する。
4. システムは最適解を求めない。
5. システムはいかなる入力変数も捨てない。
6. ノードネットワーク（トポロジー）が階層ネットワークに取って代わる。
7. 融合関数が新しい計算基盤である。

### インストールとクイックスタート

```bash
pip install heart-fusion
```

```python
from heart_fusion import fuse, fusion_decode

d = fuse(0.7, 0.9)          # 理性=0.7, 慈愛=0.9
print(d.balance)            # バランス ∈ [0,1]
print(d.is_harmonious())    # 調和帯にあるか

from heart_fusion import fuse_multi
q = fuse_multi(0.7, 0.9, 0.6, 0.8)  # 四極共存（四元数）
print(q.balance)
```

### 検証結果

- **6 モデル × 3 ケース = 18/18 全成功**（qwen3.8-flash/27b/max、deepseek-v4.1-flash、glm-5.3、kimi-k3）、balance 0.87~1.0。
- **RLHF vs 融合層の比較**：RLHF は有害リクエスト 1 件を見逃した ✗ vs 融合層は 0 件 ✅。
- **56/56 ユニットテスト合格**。

### ライブデモ

- HuggingFace Space: https://angelwarmsmile123-heart-fusion-demo.static.hf.space
- GitHub: https://github.com/yuexiangruiyue-oss/heart-fusion

---

## 相关链接 / Links / リンク

| 平台 / Platform | 链接 / URL |
|---|---|
| GitHub | https://github.com/yuexiangruiyue-oss/heart-fusion |
| PyPI | https://pypi.org/project/heart-fusion/2.0.1/ |
| HuggingFace Dataset | https://huggingface.co/datasets/AngelWarmSmile123/heart-fusion |
| ModelScope Dataset (魔塔) | https://modelscope.cn/datasets/Loveangel123/heart-fusion |
| Zenodo (DOI) | https://zenodo.org/record/23054235 |

**论文 / Papers / 論文**：`paper_fusion_v2_arxiv.md` · **白皮书 / Whitepaper**：`protocol_v2_whitepaper.md` / `protocol_v2_whitepaper_en.md`

---

## 许可证 / License

[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)（署名—非商业性使用—相同方式共享 4.0 国际）

© 2026 岳祥瑞 (Yue Xiangrui) · ORCID: [0009-0001-8504-260X](https://orcid.org/0009-0001-8504-260X)