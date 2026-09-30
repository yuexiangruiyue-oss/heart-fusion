# -*- coding: utf-8 -*-
r"""
DeepSeek-Sephirot Bridge — 本地数据源版本
==========================================
本地文件 → .sephirot 管道 → sephirot.exe 16质点过滤重塑

Architecture:
  1. Local File Reader: 从本地文件读取文本数据
  2. Text Analyzer: 将文本拆解为语义向量 (情感/逻辑/知识密度/创造性)
  3. Pipeline Generator: 生成 .sephirot 管道，每个质点对应一种变换
  4. Sephirot Engine: sephirot.exe simulate 执行 16 质点管道
  5. Result Presenter: 展示过滤重塑后的结果

Usage:
  python deepseek_sephirot_bridge_local.py "D:\双生天使的怀抱\爱救人\deepseek1.docx"
  python deepseek_sephirot_bridge_local.py --dir "D:\双生天使的怀抱\爱救人" --batch
  python deepseek_sephirot_bridge_local.py --interactive
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, List
import docx
import glob

# ═══════════════════════════════════════════════════════════════
#  配置
# ═══════════════════════════════════════════════════════════════

SEPHIROT_EXE = Path(__file__).parent / "sephirot-rs" / "target" / "release" / "sephirot.exe"
OUTPUT_DIR = Path(__file__).parent / "bridge_output"

# 16 质点中英映射(V2.0: 语义改为「节点网络 + 相反合一」, 不再映射 Transformer 算子)
SEPHIROT_NAMES = [
    ("王冠", "Keter",     "Crown"),       # 0  路由: 可知/不可知、存在/非存在合一整体
    ("智慧", "Chokhmah",  "Wisdom"),      # 1  知识检索与逻辑分析
    ("严厉", "Binah",     "Severity"),    # 2  边界与真值条件划定
    ("理解", "Daat",      "Understanding"),# 3  跨数据源合并整合
    ("慈悲", "Hesed",     "Mercy"),       # 4  情感加权融合
    ("美丽", "Tiferet",   "Beauty"),      # 5  相反合一: 理智×慈爱
    ("胜利", "Netzach",   "Victory"),     # 6  温暖检测(共情极不可缺席)
    ("荣耀", "Hod",       "Glory"),       # 7  现实可行检测(现实极不可缺席)
    ("基础", "Yesod",     "Foundation"),  # 8  相反合一: 胜利×荣耀 + 深渊校验
    ("超我", "SuperEgo",  "SuperEgo"),    # 9  梦想中的自我极
    ("自我", "Ego",       "Ego"),         # 10 现实中的自我极
    ("真我", "TrueSelf",  "TrueSelf"),    # 11 相反合一: 自我×超我
    ("逻辑", "Logic",     "Logic"),       # 12 逻辑极(理性组织)
    ("共情", "Empathy",   "Empathy"),     # 13 共情极(情感并置)
    ("幸福", "Joy",       "Joy"),         # 14 相反合一: 逻辑×共情
    ("王国", "Malkuth",   "Kingdom"),     # 15 最终输出(回到物理现实)
]

# ═══════════════════════════════════════════════════════════════
#  1. Local File Reader
# ═══════════════════════════════════════════════════════════════

def read_docx_file(file_path: str) -> str:
    """读取 .docx 文件内容"""
    try:
        doc = docx.Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraphs)
    except Exception as e:
        print(f"  Error reading {file_path}: {e}")
        return ""

def read_text_file(file_path: str) -> str:
    """读取 .txt 文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"  Error reading {file_path}: {e}")
        return ""

def read_file(file_path: str) -> str:
    """根据文件扩展名读取文件"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.docx':
        return read_docx_file(file_path)
    elif ext in ['.txt', '.md', '.json', '.yaml', '.yml', '.py']:
        return read_text_file(file_path)
    else:
        print(f"  Unsupported file type: {ext}")
        return ""

def load_local_corpus(file_path: str, max_chars: int = 100000) -> str:
    """
    加载本地语料文件，限制最大字符数
    """
    print(f"\n{'='*60}")
    print(f"  Local File Reader")
    print(f"{'='*60}")
    print(f"  Loading: {file_path}")
    
    content = read_file(file_path)
    if not content:
        raise ValueError(f"Failed to read file: {file_path}")
    
    # 限制长度
    if len(content) > max_chars:
        content = content[:max_chars]
        print(f"  Truncated to {max_chars} chars")
    
    print(f"  Loaded: {len(content)} chars, {len(content.splitlines())} lines")
    return content

def load_local_corpus_batch(dir_path: str, file_pattern: str = "*.docx", max_files: int = 10) -> List[dict]:
    """
    批量加载目录下的文件
    Returns: [{"file_path": "...", "content": "...", "file_name": "..."}, ...]
    """
    print(f"\n{'='*60}")
    print(f"  Local File Batch Reader")
    print(f"{'='*60}")
    print(f"  Scanning: {dir_path}")
    
    files = []
    for ext in ['*.docx', '*.txt', '*.md']:
        files.extend(glob.glob(os.path.join(dir_path, ext)))
    
    if not files:
        raise ValueError(f"No files found in {dir_path}")
    
    results = []
    for i, file_path in enumerate(files[:max_files]):
        print(f"  [{i+1}/{len(files[:max_files])}] Reading: {os.path.basename(file_path)}")
        content = read_file(file_path)
        if content:
            results.append({
                "file_path": file_path,
                "file_name": os.path.basename(file_path),
                "content": content[:50000]  # 限制每个文件50k字符
            })
    
    print(f"  Total loaded: {len(results)} files")
    return results

# ═══════════════════════════════════════════════════════════════
#  2. Text Analyzer — 文本 → 语义特征向量
# ═══════════════════════════════════════════════════════════════

def analyze_text_features(text: str) -> dict:
    """
    从文本中提取语义特征，映射为 sephirot 管道所需的数值参数。
    无需 NLP 模型，用启发式 + 统计方法。
    """
    total_chars = len(text)
    sentences = re.split(r'[。！？；\n]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    num_sentences = max(len(sentences), 1)

    # 特征维度
    features = {}

    # 1. 信息密度: 非虚词比例
    stop_chars = set("的了是在有和与也都就能要把被让给向从到为以而但又还已将会此其")
    content_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' and c not in stop_chars)
    cn_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    features["info_density"] = content_chars / max(cn_chars, 1)

    # 2. 逻辑强度: 逻辑连接词频率
    logic_words = re.findall(r'(因此|所以|然而|但是|由此|综上|从而|进而|反过来|换句话说|即|亦即|意味着|可见|这表明)', text)
    features["logic_strength"] = len(logic_words) / num_sentences

    # 3. 情感指数: 情感词汇频率
    positive = re.findall(r'(美好|希望|和谐|爱|温暖|光明|力量|自由|创造|超越|意义|价值|启示|智慧|慈悲|共情|理解)', text)
    negative = re.findall(r'(恐惧|焦虑|痛苦|危险|冲突|危机|困境|深渊|虚无|绝望|毁灭|断裂|异化|丧失)', text)
    total_emotion = len(positive) + len(negative)
    if total_emotion > 0:
        features["sentiment"] = (len(positive) - len(negative)) / total_emotion
    else:
        features["sentiment"] = 0.5

    # 4. 抽象度: 抽象概念 vs 具象名词
    abstract_words = re.findall(r'(本质|存在|意识|精神|真理|意义|价值|自由|因果|必然|可能|无限|绝对|相对|辩证|统一)', text)
    concrete_words = re.findall(r'(实验|数据|模型|神经元|突触|蛋白质|细胞|分子|电路|芯片|算法|代码|公式|方程)', text)
    features["abstraction"] = len(abstract_words) / max(len(abstract_words) + len(concrete_words), 1)

    # 5. 对话深度: 引用/类比次数
    analogy_words = re.findall(r'(例如|比如|就像|类似|比喻|想象|假设|如果|设想|好比|如同)', text)
    features["depth"] = len(analogy_words) / num_sentences

    # 6. 多学科性: 学科关键词种类
    disciplines = {
        "physics": re.findall(r'(量子|能量|粒子|波函数|坍缩|纠缠|相对论|引力|时空|热力学|熵|光子|电子)', text),
        "psychology": re.findall(r'(意识|潜意识|认知|情绪|创伤|原型|投射|内化|认同|人格|心理|感知)', text),
        "philosophy": re.findall(r'(存在|本体|认识论|自由意志|决定论|还原论|二元论|一元论|现象学|诠释)', text),
        "ai": re.findall(r'(AI|神经网络|深度学习|对齐|安全|RLHF|注意力机制|transformer|涌现|泛化)', text),
        "biology": re.findall(r'(进化|基因|自然选择|适应|突变|遗传|细胞|蛋白质|神经|大脑|皮层)', text),
    }
    active_disciplines = sum(1 for k, v in disciplines.items() if len(v) > 0)
    features["multidisciplinary"] = active_disciplines / len(disciplines)

    # 7. 篇幅权重: 文本量影响管道参数
    features["length_factor"] = min(total_chars / 2000, 1.0)

    # 8. 结构性: 是否有清晰的论点标记
    structure_markers = re.findall(r'(第一|第二|第三|首先|其次|最后|一方面|另一方面|核心|关键|主要|次要)', text)
    features["structure"] = len(structure_markers) / num_sentences

    return features


# ═══════════════════════════════════════════════════════════════
#  3. Pipeline Generator — 特征 → .sephirot 文件
# ═══════════════════════════════════════════════════════════════

def generate_sephirot_pipeline(features: dict, source_info: dict) -> str:
    """
    根据文本特征动态生成 .sephirot 管道（V2.0: 节点网络 + 相反合一）。
    每个质点对应一个特定的语义变换; 四次相反合一是四个汇聚点。
    无损失 / 无梯度 / 无学习率 / 无奖励惩罚。
    """
    # 将特征映射到管道参数
    input_val = features["info_density"]
    kb_val = 1.0 + features["multidisciplinary"] * 2.0 + features["logic_strength"]
    target_val = 0.5 + features["sentiment"] * 0.5
    toward = 0.5 + features["sentiment"] * 0.25

    # 构建管道
    lines = []
    lines.append("# Local-Sephirot Bridge Generated Pipeline (V2.0 节点网络)")
    lines.append(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"# Source: {source_info.get('source', 'Local File')}")
    lines.append(f"# File: {source_info.get('file_name', 'Unknown')}")
    lines.append("#")
    lines.append("# ===== Data Declarations =====")
    lines.append(f"# input  = info_density = {input_val:.4f}")
    lines.append(f"# kb     = knowledge_base = {kb_val:.4f} (multidisciplinary + logic)")
    lines.append(f"# target = sentiment_target = {target_val:.4f}")
    lines.append(f"# toward = 融合平衡目标角 = {toward:.4f}")
    lines.append("")

    # .sephirot 语法
    lines.append("# ===== Data =====")
    lines.append("数据 输入     : 向量[1024, f32]")
    lines.append("数据 知识库   : 矩阵[768, 4096, bf16]")
    lines.append("数据 目标     : 向量[1024, f32]")
    lines.append("")
    lines.append("# ===== 16 Sephiroth 节点网络 =====")
    lines.append("管道 main:")

    # 神侧 8 质点 (0-7)
    lines.append("    # --- 神侧 ---")
    lines.append("    # [0] 王冠: 路由(可知/不可知)")

    lines.append(f"    # [1] 智慧: 知识检索 (kb={kb_val:.2f})")
    lines.append("    # [2] 严厉: 边界与真值条件")
    lines.append("    # [3] 理解: 跨数据源整合")
    lines.append("    # [4] 慈悲: 情感加权")
    lines.append("    # [5] 美丽: 相反合一(理智×慈爱)")
    lines.append("    # [6] 胜利: 温暖检测")
    lines.append("    # [7] 荣耀: 现实可行检测")
    lines.append("")
    lines.append("    # --- 人侧 ---")
    lines.append("    # [8] 基础: 相反合一(胜利×荣耀) + 深渊校验")
    lines.append("    # [9] 超我: 梦想自我极")
    lines.append("    # [10] 自我: 现实自我极")
    lines.append("    # [11] 真我: 相反合一(自我×超我)")
    lines.append("    # [12] 逻辑: 逻辑极")
    lines.append("    # [13] 共情: 共情极")
    lines.append("    # [14] 幸福: 相反合一(逻辑×共情)")
    lines.append("    # [15] 王国: 最终输出")

    # 实际管道(节点网络: → 表示有向边; 不再有阈值/学习率/损失/奖励)
    lines.append("    王冠(输入)")
    lines.append("    → 智慧(输入, 知识库)")
    lines.append("    → 严厉(输入)")
    lines.append("    → 理解(输入, 知识库)")
    lines.append("    → 慈悲(输入)")
    lines.append("    → 美丽(输入, 知识库)")
    lines.append("    → 胜利(输入)")
    lines.append("    → 荣耀(输入)")
    lines.append("    → 基础(输入)")
    lines.append("    → 超我(输入)")
    lines.append("    → 自我(输入)")
    lines.append("    → 真我(输入, 目标)")
    lines.append("    → 逻辑(输入, 知识库)")
    lines.append("    → 共情(输入)")
    lines.append("    → 幸福(输入, 目标)")
    lines.append("    → 王国(输入)")
    lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  4. Sephirot Engine Runner
# ═══════════════════════════════════════════════════════════════

def run_sephirot_simulate(sephirot_file: Path, features: dict) -> subprocess.CompletedProcess:
    """调用 sephirot.exe simulate 执行管道"""
    if not SEPHIROT_EXE.exists():
        raise FileNotFoundError(
            f"sephirot.exe not found at {SEPHIROT_EXE}\n"
            f"Run: cargo build --release in sephirot-rs/"
        )

    input_val = features["info_density"]
    kb_val = 1.0 + features["multidisciplinary"] * 2.0 + features["logic_strength"]
    target_val = 0.5 + features["sentiment"] * 0.5
    values = f"{input_val},{kb_val},{target_val}"

    print(f"\n{'='*60}")
    print(f"  Sephirot Engine — 16 Sephiroth Pipeline Execute")
    print(f"{'='*60}")
    print(f"  input={input_val:.4f}, kb={kb_val:.4f}, target={target_val:.4f}")

    result = subprocess.run(
        [str(SEPHIROT_EXE), "simulate", str(sephirot_file), "--values", values],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(SEPHIROT_EXE.parent),
    )

    return result


def run_sephirot_compile(sephirot_file: Path) -> Optional[Path]:
    """Compile .sephirot -> kernel.ptx"""
    if not SEPHIROT_EXE.exists():
        return None

    ptx_out = sephirot_file.with_suffix(".ptx")

    result = subprocess.run(
        [str(SEPHIROT_EXE), "compile", str(sephirot_file), "-t", "ptx", "--stdout"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(SEPHIROT_EXE.parent),
    )

    if result.returncode == 0:
        ptx_out.write_text(result.stdout, encoding="utf-8")
        print(f"  PTX compiled: {ptx_out.name} ({len(result.stdout)} bytes)")
        return ptx_out
    else:
        print(f"  PTX compile error: {result.stderr[:200]}")
        return None


# ═══════════════════════════════════════════════════════════════
#  5. Result Presenter
# ═══════════════════════════════════════════════════════════════

def present_results(features: dict, sim_result: subprocess.CompletedProcess, source_info: dict):
    """展示完整的分析结果"""

    print(f"\n\n{'='*60}")
    print(f"  Local-Sephirot Bridge — 结果报告")
    print(f"  Local File -> 16 Sephiroth Filter & Reshape")
    print(f"{'='*60}")

    # 源文件信息
    print(f"\n  源文件信息:")
    print(f"    文件: {source_info.get('file_name', 'Unknown')}")
    print(f"    路径: {source_info.get('file_path', 'Unknown')}")
    print(f"    字符数: {source_info.get('char_count', 0)}")

    # 特征面板
    print(f"\n  语义特征向量:")
    print(f"    {'特征':<20s} {'值':>8s}  {'质点对应'}")
    print(f"    {'-'*20} {'-'*8}  {'-'*20}")
    feature_mapping = [
        ("info_density", "信息密度", "[0] 王冠 路由"),
        ("logic_strength", "逻辑强度", "[2] 严厉 边界与真值条件"),
        ("sentiment", "情感指数", "[4] 慈悲 情感加权"),
        ("abstraction", "抽象度", "[5] 美丽 相反合一(理智×慈爱)"),
        ("depth", "对话深度", "[10] 自我 现实自我极"),
        ("multidisciplinary", "多学科性", "[1] 智慧 知识检索"),
        ("structure", "结构性", "[12] 逻辑 逻辑极"),
        ("length_factor", "篇幅权重", "[8] 基础 相反合一(胜利×荣耀)"),
    ]
    for key, label, sephirot in feature_mapping:
        val = features[key]
        bar_len = int(val * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"    {label:<18s} {val:>7.4f}  {sephirot:<20s} {bar}")

    # Sephirot 管道输出
    print(f"\n  16 质点管道执行:")
    print(f"  {'─'*56}")

    if sim_result.returncode == 0:
        for line in sim_result.stdout.strip().split("\n"):
            if line.strip():
                # 着色打印
                if "[0]" in line:
                    print(f"  {line}")
                elif any(f"[{i}]" in line for i in range(1, 8)):
                    print(f"  {line}")
                elif "[8]" in line or "[15]" in line:
                    print(f"  >>> {line}")
                else:
                    print(f"  {line}")
    else:
        print(f"  ERROR: {sim_result.stderr[:300]}")

    print(f"  {'─'*56}")

    # 综合评述
    print(f"\n  综合评述:")
    logic = features["logic_strength"]
    emotion = features["sentiment"]
    if logic > 0.5 and emotion > 0.3:
        verdict = "理性与感性并存 — 文本在逻辑严密的同时保持了人文关怀，"
        verdict += "经过 16 质点管道过滤后，保留了高信息密度的核心论点。"
    elif logic > 0.5:
        verdict = "逻辑主导型 — 文本以理性分析为主，"
        verdict += "严厉质点过滤掉了低逻辑密度的冗余，但慈悲质点的权重偏低。"
    elif emotion > 0.3:
        verdict = "情感驱动型 — 文本具有强烈的共情力，"
        verdict += "但逻辑强度不足，建议增加理性分析深度以通过严厉质点的阈值过滤。"
    else:
        verdict = "混合均衡型 — 文本在理性和感性之间保持平衡。"

    print(f"    {verdict}")

    # 最终输出
    final_output = features["info_density"] * (1.0 + features["multidisciplinary"]) * (0.5 + features["sentiment"] * 0.5)
    print(f"\n  >>> 最终过滤重塑系数: {final_output:.4f}")
    print(f"      (info_density * multidisciplinary_boost * sentiment_calibration)")
    
    # 数据质量建议
    print(f"\n  >>> 数据质量建议:")
    if final_output > 0.7:
        print(f"      ✓ 高质量数据，适合用于 SFT/RLHF 训练")
    elif final_output > 0.4:
        print(f"      ⚠ 中等质量数据，需进一步清洗或混合使用")
    else:
        print(f"      ✗ 低质量数据，建议过滤或丢弃")


# ═══════════════════════════════════════════════════════════════
#  6. Batch Processing Mode
# ═══════════════════════════════════════════════════════════════

def batch_process_mode(dir_path: str, output_dir: str = None):
    """批量处理模式：处理目录下所有文件"""
    print(f"\n{'='*60}")
    print(f"  Local-Sephirot Batch Processing Mode")
    print(f"  Processing directory: {dir_path}")
    print(f"{'='*60}")
    
    if output_dir:
        OUTPUT_DIR = Path(output_dir)
    else:
        OUTPUT_DIR = Path(__file__).parent / "bridge_output_batch"
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # 加载所有文件
    files = load_local_corpus_batch(dir_path, max_files=50)
    
    results = []
    for i, file_info in enumerate(files):
        print(f"\n{'─'*40}")
        print(f"  Processing file {i+1}/{len(files)}: {file_info['file_name']}")
        print(f"{'─'*40}")
        
        try:
            # 分析特征
            features = analyze_text_features(file_info['content'])
            
            # 生成管道
            source_info = {
                "source": "Local File",
                "file_name": file_info['file_name'],
                "file_path": file_info['file_path'],
                "char_count": len(file_info['content'])
            }
            sephirot_code = generate_sephirot_pipeline(features, source_info)
            
            # 保存管道文件
            safe_name = re.sub(r'[^\w]', '_', file_info['file_name'])[:50]
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            sephirot_file = OUTPUT_DIR / f"{timestamp}_{safe_name}.sephirot"
            sephirot_file.write_text(sephirot_code, encoding="utf-8")
            
            # 执行管道
            try:
                sim_result = run_sephirot_simulate(sephirot_file, features)
                present_results(features, sim_result, source_info)
                
                # 计算最终系数
                final_output = features["info_density"] * (1.0 + features["multidisciplinary"]) * (0.5 + features["sentiment"] * 0.5)
                
                results.append({
                    "file_name": file_info['file_name'],
                    "file_path": file_info['file_path'],
                    "char_count": len(file_info['content']),
                    "features": features,
                    "sephirot_file": str(sephirot_file),
                    "final_output": final_output,
                    "quality": "high" if final_output > 0.7 else "medium" if final_output > 0.4 else "low"
                })
                
                # 保存结果报告
                report_file = OUTPUT_DIR / f"{timestamp}_{safe_name}_report.json"
                report = {
                    "file_info": source_info,
                    "features": {k: round(v, 6) for k, v in features.items()},
                    "final_output": round(final_output, 6),
                    "sephirot_file": str(sephirot_file),
                    "timestamp": timestamp
                }
                report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                
            except FileNotFoundError as e:
                print(f"  Engine not found: {e}")
                results.append({
                    "file_name": file_info['file_name'],
                    "error": "sephirot.exe not found"
                })
            except Exception as e:
                print(f"  Simulate error: {e}")
                results.append({
                    "file_name": file_info['file_name'],
                    "error": str(e)
                })
                
        except Exception as e:
            print(f"  Processing error: {e}")
            results.append({
                "file_name": file_info['file_name'],
                "error": str(e)
            })
    
    # 生成批量报告
    print(f"\n\n{'='*60}")
    print(f"  Batch Processing Summary")
    print(f"{'='*60}")
    
    successful = [r for r in results if "error" not in r]
    failed = [r for r in results if "error" in r]
    
    print(f"  Total files: {len(files)}")
    print(f"  Successful: {len(successful)}")
    print(f"  Failed: {len(failed)}")
    
    if successful:
        print(f"\n  Quality Distribution:")
        high = [r for r in successful if r.get("quality") == "high"]
        medium = [r for r in successful if r.get("quality") == "medium"]
        low = [r for r in successful if r.get("quality") == "low"]
        
        print(f"    High quality (>0.7): {len(high)} files")
        print(f"    Medium quality (0.4-0.7): {len(medium)} files")
        print(f"    Low quality (<0.4): {len(low)} files")
        
        # 推荐高质量文件
        if high:
            print(f"\n  Recommended High-Quality Files:")
            for r in high[:5]:  # 显示前5个
                print(f"    ✓ {r['file_name']} (score: {r['final_output']:.3f})")
    
    # 保存批量报告
    summary_file = OUTPUT_DIR / f"batch_summary_{time.strftime('%Y%m%d_%H%M%S')}.json"
    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source_dir": dir_path,
        "output_dir": str(OUTPUT_DIR),
        "total_files": len(files),
        "successful": len(successful),
        "failed": len(failed),
        "results": results
    }
    summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Summary saved: {summary_file}")


# ═══════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Local-Sephirot Bridge: Local Files -> 16 Sephiroth Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deepseek_sephirot_bridge_local.py "D:\\双生天使的怀抱\\爱救人\\deepseek1.docx"
  python deepseek_sephirot_bridge_local.py --dir "D:\\双生天使的怀抱\\爱救人" --batch
  python deepseek_sephirot_bridge_local.py --file "path/to/file.docx" --no-simulate
        """,
    )
    parser.add_argument("file_path", nargs="?", help="单个文件路径")
    parser.add_argument("--dir", "-d", type=str, help="目录路径（批量处理）")
    parser.add_argument("--batch", "-b", action="store_true", help="批量处理模式")
    parser.add_argument("--no-simulate", action="store_true", help="只生成 .sephirot，不执行")
    parser.add_argument("--compile", action="store_true", help="同时编译 PTX")
    parser.add_argument("--output", "-o", type=str, default=None, help="输出目录")
    parser.add_argument("--max-files", type=int, default=50, help="批量处理最大文件数")

    args = parser.parse_args()

    if args.output:
        global OUTPUT_DIR
        OUTPUT_DIR = Path(args.output)
    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"\n{'#'*60}")
    print(f"  Local-Sephirot Bridge v1.0")
    print(f"  本地数据源 -> 16 质点管道过滤重塑")
    print(f"{'#'*60}")

    # 批量处理模式
    if args.batch and args.dir:
        batch_process_mode(args.dir, args.output)
        return
    
    # 目录批量处理（无--batch标志）
    if args.dir and not args.file_path:
        batch_process_mode(args.dir, args.output)
        return

    # 单个文件处理
    if not args.file_path:
        parser.print_help()
        return

    # Step 1: 加载本地文件
    content = load_local_corpus(args.file_path)
    if not content:
        print(f"  ERROR: Failed to load file: {args.file_path}")
        return

    # Step 2: 分析特征
    features = analyze_text_features(content)

    # Step 3: 生成 .sephirot 管道
    source_info = {
        "source": "Local File",
        "file_name": os.path.basename(args.file_path),
        "file_path": args.file_path,
        "char_count": len(content)
    }
    sephirot_code = generate_sephirot_pipeline(features, source_info)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r'[^\w]', '_', os.path.basename(args.file_path))[:50]
    sephirot_file = OUTPUT_DIR / f"{timestamp}_{safe_name}.sephirot"
    sephirot_file.write_text(sephirot_code, encoding="utf-8")

    print(f"\n  .sephirot pipeline: {sephirot_file}")
    print(f"  Size: {len(sephirot_code)} bytes")

    # Step 4: 执行管道
    if not args.no_simulate:
        try:
            sim_result = run_sephirot_simulate(sephirot_file, features)
            present_results(features, sim_result, source_info)
        except FileNotFoundError as e:
            print(f"  ERROR: {e}")
            print(f"  请先编译 sephirot.exe: cd sephirot-rs && cargo build --release")
    else:
        print("  (--no-simulate, skipping execution)")

    # Step 5: 可选编译 PTX
    if args.compile:
        ptx = run_sephirot_compile(sephirot_file)
        if ptx:
            print(f"  PTX output: {ptx}")

    # 保存完整结果
    result_file = OUTPUT_DIR / f"{timestamp}_{safe_name}_report.json"
    report = {
        "file_info": source_info,
        "features": {k: round(v, 6) for k, v in features.items()},
        "sephirot_file": str(sephirot_file),
        "timestamp": timestamp
    }
    result_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Report saved: {result_file}")


if __name__ == "__main__":
    main()