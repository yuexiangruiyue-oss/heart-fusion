# Heart Protocol V3.1.1 — Release Package

**Author**: Yue Xiangrui (岳祥瑞) · ORCID 0009-0001-8504-260X · yuexiangruiyue@gmail.com
**Date**: 2026-10-23 · **License**: CC BY-NC-SA 4.0

## Contents

| Directory | Contents |
|---|---|
| `paper/` | Trilingual paper (zh/en/ja), PDFs, the full original protocol text, Zenodo metadata |
| `docs/` | CHANGELOG, number reconciliation table, real-model evaluation report |
| `code/` | `heart_protocol/` Python source (protocol, fusion, red lines, middleware, adapters, benchmark) |
| `dist/` | Built wheels and sdist (3.1.0 build; source here is 3.1.1) |

## The proposal

Two polar corpora (love/meaning; reason/objectivity) trained through a fusion layer
(`z = a + i·b`, coexistence `balance = n·min(p)`); no objective, no evaluation criterion,
no human preference score; self-prediction and self-emergence retained; the 16-sephirot
protocol imprinted as a cognitive control layer of eight computations. Training requires
10,000 A100 GPUs. The paradigm has not been tested: it may not work; it may work.

## Data not included

The personal corpus (68 DOCX, 34.36 million characters) and the 13 RAR archives
(642.4 GB of JSONL) are not included in this package. See `MANIFEST.md`.

## Quick start

```bash
pip install dist/heart_protocol_v3-3.1.0-py3-none-any.whl
python -c "from heart_protocol import HeartProtocol; print(HeartProtocol().process('我感到迷茫')['output'])"
```

## Collaboration

Data engineering, training, evaluation, ethics and translation.
Contact: yuexiangruiyue@gmail.com
