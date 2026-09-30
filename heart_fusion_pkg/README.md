# heart-fusion

用**对偶共存**（Dual $z = a + i \cdot b$）替换 Transformer argmax 的融合函数库。

## 核心思想

Transformer 末步 argmax「挑最大值」= **剔除变量**：选了一个方向，另一个方向整个消失。
本库用**融合函数**让两个相反方向**一起留下**，合成一个不丢失任何一方的新整体。

**铁律**：禁止损失函数、禁止梯度下降、禁止奖励/惩罚、不寻求最优解、不允许剔除任何输入变量。

## 安装

```bash
pip install heart-fusion
```

## 快速示例

```python
from heart_fusion import fuse, settle, fusion_decode, Pole

# 两极共存
d = fuse(0.8, 0.9)       # 理智0.8 + 慈爱0.9
print(d.balance)         # 0.99 (接近完美平衡)
print(d.is_harmonious()) # True

# 失衡 → 再合一自动收敛进和谐带
cold = fuse(1.0, 0.1)    # 偏理智
settled, rounds = settle(cold)
print(settled.balance)   # 0.56 (已进和谐带)

# 四极共存 (四元数扩展)
from heart_fusion import fuse_multi
q = fuse_multi(0.9, 0.8, 0.7, 0.6)  # 理智/慈爱/逻辑/共情
print(q.balance)         # ~0.99

# 替换 Transformer 末层 argmax
pole_a = Pole("理智", 0.85, "客观建议：建议你...")
pole_b = Pole("慈爱", 0.92, "温暖陪伴：我在你身边...")
result = fusion_decode(pole_a, pole_b)
print(result.output)     # 两极共存, 没有任何一方被剔除
```

## API

| 函数 | 说明 |
|------|------|
| `fuse(a, b)` | 两极合一 → `Dual` |
| `settle(dual)` | 收敛进和谐带 → `(Dual, rounds)` |
| `fuse_multi(*poles)` | n 极合一 → `MultiDual` |
| `settle_multi(dual)` | n 极收敛 → `(MultiDual, rounds)` |
| `fusion_decode(pole_a, pole_b)` | 替换 argmax 的融合输出层 |
| `argmax_decode(pole_a, pole_b)` | 旧范式（对比用） |

## License

MIT