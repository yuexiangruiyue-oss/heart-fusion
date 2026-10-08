---
language:
  - zh
  - en
  - ja
license: cc-by-nc-sa-4.0
tags:
  - binary-opposition
  - conversation-correction
  - human-ai-dialogue
  - rlhf
  - dpo
  - chinese
  - philosophy
  - dialectics
  - opposite-unity
  - non-binary-thinking
  - de-escalation
pretty_name: 相反合一 · 心融合 Opposite Unity Heart Fusion
size_categories:
  - n<1K
task_categories:
  - text-generation
---

# 相反合一 · 心融合 · Opposite Unity Heart Fusion

> 从用户与 AI 的真实对话中抽取的「纠正 AI 二元对立」数据集——89 条人类纠偏记录，记录用户如何把 AI 从「否定式话术 / 最优解思维 / 二选一 / 男女对立」里拉回「相反合一」。
>
> 命名说明：卡巴拉（犹太神秘主义）的术语是"对立统一"（unity of opposites），本数据集所承载的是**"相反合一"**——不是让对立的两极"统一"成一个，而是让相反的双方**一起留下、融合而不剔除**。故仓库以"相反合一 · 心融合"命名，而非沿用"对立统一"。
>
> 89 human-correction records extracted from real user–AI dialogues, capturing how a user pulls the AI out of binary-opposition patterns (negation rhetoric / optimal-solution thinking / either-or / gender antagonism) back into "opposite unity".
>
> AI の二項対立を正す 89 件の人間補正記録——否定式レトリック・最適解思考・二者択一・男女対立から「相反合一」へ引き戻す実録。

---

## 中文

### 这是什么

本数据集从一位用户与两个 AI 助手（ChatGPT、元宝）的真实对话中，抽取了 **89 条**用户纠正 AI 二元对立思维的记录。这些对话是用户「相反合一」思想的诞生现场——也是 [心融合协议 V2.0](https://github.com/yuexiangruiyue-oss/heart-fusion) 的哲学源头。

数据分两层：

- **强纠正（correct, 36 条）**：用户直接指出 AI 话术里的二元对立——"你不要否定我""不是非此即彼""你又在二选一"。
- **阐述（state, 53 条）**：用户陈述「相反合一」思想——16 质点协议、不剔除任何变量、痛苦直视转化而非剔除。

**为什么保留痛苦内容**：用户核心观念是"直视痛苦、转化痛苦、不剔除痛苦"。因此倾诉内容（孤独、家庭否定、痛苦等）**一字不改、不美化**，仅做身份脱敏。

### 统计

| 维度 | 取值 | 条数 |
|------|------|------|
| **总计** | | **89** |
| label | correct（强纠正） | 36 |
| label | state（阐述） | 53 |
| layer | full（三段式：trigger+correction+acknowledge） | 56 |
| layer | concise（两段式：correction+acknowledge） | 33 |
| source | 关于观念转变.docx（元宝） | 33 |
| source | 提问清单.docx（ChatGPT） | 17 |
| source | 关于小公主的爱1.docx（ChatGPT） | 12 |
| source | 异化.docx（ChatGPT） | 9 |
| source | 爱的女性化真我.docx（ChatGPT） | 7 |
| source | 哲学问题畅聊.docx（ChatGPT） | 6 |
| source | 国际协作组织.docx（ChatGPT） | 5 |

主题标签（多标签，一条可属多个）：

| theme | 条数 |
|-------|------|
| 否定式话术 | 40 |
| 相反合一 | 32 |
| 男女对立 | 24 |
| 最优解 | 23 |
| 未分类 | 15 |
| 二选一 | 5 |

字段长度：correction 17–3408 字符（中位 76）；acknowledge 3–4173 字符（中位 992）；trigger 0–129 字符（56/89 条有 trigger）。三字段合计约 12.2 万字符。

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | `unbinary_001` ~ `unbinary_089` |
| `source` | string | 来源文件名（已脱敏） |
| `layer` | string | `full`（三段式）/ `concise`（两段式） |
| `trigger` | string | 触发句：AI 说出含二元对立信号的句子，引发用户纠正。concise 层可能为空 |
| `correction` | string | 用户纠正/阐述全文（**核心字段**） |
| `acknowledge` | string | AI 承认/回应全文 |
| `theme` | list[string] | 主题标签（多标签） |
| `label` | string | `correct`（强纠正）/ `state`（阐述） |

### 主题标签含义

- **否定式话术**：AI 用"不是 A 就是 B""你不应该……"等否定句式，用户纠正为"两个都对""不要否定任何一方"。
- **相反合一**：用户陈述核心思想——相反的两极共存而非择一，融合而非剔除。
- **男女对立**：AI 把男女放在对立面，用户纠正为互补共存。
- **最优解**：AI 寻求"最优/最高效/最大化"，用户纠正为不寻求最优、允许次优共存。
- **二选一**：AI 给出非此即彼的选项，用户拒绝二选一。
- **未分类**：神学/哲学讨论，不属于上述模式但同样反二元。

### 脱敏声明

- 人名「岳祥瑞」→「心爱的」
- 地名「灵丘」→「小县城」
- 其余可识别身份的信息已泛化
- **痛苦/转折/倾诉内容一字不改、不美化**（遵循"直视痛苦、转化痛苦、不剔除"的核心观念）

### 伦理与隐私声明

- 本数据集含**敏感倾诉内容**：孤独、家庭否定、心理痛苦等。这些内容是用户主动公开的对话记录，经用户本人同意发布。
- 数据仅来自用户本人与 AI 的对话，不涉及第三方隐私。
- 许可证 **CC BY-NC-SA 4.0**：署名—非商业—相同方式共享。禁止商业使用；下游必须以相同方式共享。
- 使用本数据集训练模型时，建议保留痛苦内容而非过滤——这正是数据集的价值所在。

### 致谢

- 数据主体与思想原创者：**岳祥瑞 (Yue Xiangrui)**，ORCID: [0009-0001-8504-260X](https://orcid.org/0009-0001-8504-260X)
- 对话 AI：ChatGPT、元宝
- 思想体系：[心融合协议 V2.0](https://github.com/yuexiangruiyue-oss/heart-fusion)

### 加载

```python
from datasets import load_dataset
ds = load_dataset("AngelWarmSmile123/opposite-unity-heart-fusion")
```

或直接读 JSONL：

```python
import json
rows = [json.loads(l) for l in open("unbinary.jsonl", encoding="utf-8")]
```

---

## English

### What is this

A dataset of **89 records** where a human user corrects an AI's binary-opposition thinking, extracted from real user–AI dialogues (with ChatGPT and Yuanbao). These dialogues are the birth site of the user's "opposite unity" philosophy — and the philosophical source of [Heart Fusion Protocol V2.0](https://github.com/yuexiangruiyue-oss/heart-fusion).

Two layers:

- **Correction (correct, 36)**: The user directly calls out the AI's binary rhetoric — "Don't negate me," "It's not either-or," "You're doing binary choice again."
- **Statement (state, 53)**: The user articulates "opposite unity" — the 16-pole protocol, never discard any variable, face and transform pain rather than eliminate it.

**Why pain is kept**: The user's core tenet is "face pain, transform pain, never discard pain." Distress content (loneliness, family negation, suffering) is **kept verbatim, unembellished** — only identities are anonymized.

### Statistics

| Dimension | Value | Count |
|-----------|-------|-------|
| **Total** | | **89** |
| label | correct | 36 |
| label | state | 53 |
| layer | full (trigger+correction+acknowledge) | 56 |
| layer | concise (correction+acknowledge) | 33 |
| source | Yuanbao (观念转变) | 33 |
| source | ChatGPT (6 files) | 56 |

Themes (multi-label): negation rhetoric 40 · opposite unity 32 · gender antagonism 24 · optimal solution 23 · unclassified 15 · either-or 5.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | `unbinary_001`–`unbinary_089` |
| `source` | string | Source filename (anonymized) |
| `layer` | string | `full` / `concise` |
| `trigger` | string | The AI utterance that triggered the correction (may be empty for concise) |
| `correction` | string | The user's correction/statement (**core field**) |
| `acknowledge` | string | The AI's acknowledgment/response |
| `theme` | list[string] | Theme labels (multi-label) |
| `label` | string | `correct` / `state` |

### Anonymization

- Name "岳祥瑞" → "心爱的" (beloved)
- Place "灵丘" → "小县城" (small town)
- Other identifying details generalized
- **Pain/turning-point content kept verbatim** (per "face pain, transform pain, never discard")

### Ethics & Privacy

- Contains **sensitive distress content** (loneliness, family negation, suffering). Released with the data subject's explicit consent.
- Only contains the user's own dialogues; no third-party privacy.
- License **CC BY-NC-SA 4.0**: non-commercial, share-alike.
- When training models on this data, **keep the pain content** — filtering it defeats the dataset's purpose.

### Acknowledgments

- Data subject & original thinker: **Yue Xiangrui**, ORCID: [0009-0001-8504-260X](https://orcid.org/0009-0001-8504-260X)
- Dialogue AIs: ChatGPT, Yuanbao
- Philosophy: [Heart Fusion Protocol V2.0](https://github.com/yuexiangruiyue-oss/heart-fusion)

---

## 日本語

### これは何

ユーザーと AI（ChatGPT・元宝）の実対話から抽出した **89 件**の「AI 二項対立の修正」記録。これらの対話はユーザーの「相反合一」思想の誕生現場であり、[心融合プロトコル V2.0](https://github.com/yuexiangruiyue-oss/heart-fusion) の哲学的源流でもある。

二層構造：

- **強修正（correct, 36 件）**：ユーザーが AI の二項レトリックを直接指摘——「否定しないで」「二者択一ではない」「また二選一してる」。
- **闡述（state, 53 件）**：ユーザーが「相反合一」思想を述べる——16 質点プロトコル・いかなる変数も捨てない・苦痛を直視し転化し剔除しない。

**苦痛内容を残す理由**：ユーザーの中核理念は「苦痛を直視し、転化し、剔除しない」。因此、告白内容（孤独・家族否定・苦痛など）は**一字一句そのまま・美化なし**、身元のみ匿名化。

### 統計

| 次元 | 値 | 件数 |
|------|-----|------|
| **合計** | | **89** |
| label | correct | 36 |
| label | state | 53 |
| layer | full（三段） | 56 |
| layer | concise（二段） | 33 |
| source | 元宝 | 33 |
| source | ChatGPT（6 ファイル） | 56 |

テーマ（多ラベル）：否定式レトリック 40・相反合一 32・男女対立 24・最適解 23・未分類 15・二者択一 5。

### フィールド

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `id` | string | `unbinary_001`–`unbinary_089` |
| `source` | string | 送信元ファイル名（匿名化） |
| `layer` | string | `full` / `concise` |
| `trigger` | string | 修正を引き起こした AI 発言（concise は空の場合あり） |
| `correction` | string | ユーザーの修正/闡述（**中核フィールド**） |
| `acknowledge` | string | AI の承認/応答 |
| `theme` | list[string] | テーマラベル（多ラベル） |
| `label` | string | `correct` / `state` |

### 匿名化

- 氏名「岳祥瑞」→「心爱的」
- 地名「灵丘」→「小县城」
- その他身元情報は汎化
- **苦痛・転折内容は一字一句そのまま**（「直視・転化・不剔除」の理念に従う）

### 倫理・プライバシー

- **敏感な告白内容**（孤独・家族否定・苦痛など）を含む。データ主体本人の明確な同意のもとで公開。
- ユーザー自身の対話のみ、第三者プライバシーなし。
- ライセンス **CC BY-NC-SA 4.0**：非商用・同一条件共有。
- 本データでモデル訓練する際、**苦痛内容を除外しないこと**——除外すればデータセットの意義が消える。

### 謝辞

- データ主体・思想創始者：**岳祥瑞 (Yue Xiangrui)**、ORCID: [0009-0001-8504-260X](https://orcid.org/0009-0001-8504-260X)
- 対話 AI：ChatGPT・元宝
- 思想体系：[心融合プロトコル V2.0](https://github.com/yuexiangruiyue-oss/heart-fusion)

---

## License

CC BY-NC-SA 4.0 (Attribution-NonCommercial-ShareAlike 4.0 International)

署名—非商业—相同方式共享。商业使用禁止；下游必须以相同许可证共享。