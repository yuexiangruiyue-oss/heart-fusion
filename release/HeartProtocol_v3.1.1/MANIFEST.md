# Manifest

## Included
- Trilingual paper + PDFs + original protocol text
- Python source (`heart_protocol/`)
- Wheels/sdist (3.1.0 build)
- CHANGELOG, reconciliation table, real-model report

## External data (not shipped)
- Personal corpus: `爱救人/` — 68 DOCX, 38.1 MB compressed, 34,362,989 characters (23,985,985 Chinese), ~22.9M tokens
- Dataset archives: `爱的数据集/` — 13 RAR, 642.4 GB compressed
  - 16亿数据集.rar 368.97 GB
  - worldfix_v2.rar 263.53 GB
  - sephirot_1b.rar 25.71 GB
  - double_star_dataset_500M.rar 17.58 GB
  - dataset_500M.rar 10.56 GB
  - dataset_100M.rar 2.95 GB (501 JSONL parts)
  - sephirot_final_run*.rar, dataset123.rar, dataset23.rar, double_star_dataset_1M_alpaca.rar,
    AngelEmbraceMeWarmSmile1k.rar, double_star_dataset_100k.rar
- Rust core: `sephirot-rs/` (source + built `heart_core.dll`)
- C reference: `heart_ffi/` (source + `build/heart_core.dll`)
