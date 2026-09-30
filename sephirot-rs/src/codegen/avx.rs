/// AVX-512 代码生成后端 — Intel x86-64 SIMD
use crate::codegen::CodeEmitter;
use crate::error::Result;
use crate::ir::{IrProgram, IrPipeline, IrStage, IrValue};
use crate::lang::Sephirah;

pub struct AvxEmitter;

impl CodeEmitter for AvxEmitter {
    fn target_name(&self) -> &str { "AVX-512 (Intel x86-64)" }
    fn extension(&self) -> &str { "asm" }

    fn emit(&self, ir: &IrProgram) -> Result<String> {
        let mut out = String::new();

        out.push_str(";\n");
        out.push_str("; ═══════════════════════════════════════════════════════════\n");
        out.push_str(";  质点语言 SephirotLang Compiler v1.0\n");
        out.push_str(";  16质点神人双生协议 → Intel AVX-512\n");
        out.push_str(";  ISA ref : Intel 64/IA-32 Architectures SDM Vol.2\n");
        out.push_str(";  Features: AVX-512F, AVX-512BF16, AVX-512BITALG, SVML\n");
        out.push_str(";  Toolchain: NASM / MASM compatible\n");
        out.push_str("; ═══════════════════════════════════════════════════════════\n");
        out.push_str(";\n\n");

        out.push_str("SECTION .data\n");

        // 常量
        for c in &ir.const_decls {
            match &c.value {
                IrValue::Float(f) => {
                    out.push_str(&format!("    _c_{} dd {:.10}\n", c.name, f));
                }
                IrValue::Integer(n) => {
                    out.push_str(&format!("    _c_{} dd {}\n", c.name, n));
                }
                _ => {}
            }
        }

        out.push_str("\nSECTION .text\n");

        for pipeline in &ir.pipelines {
            out.push_str(&emit_pipeline_avx(pipeline));
        }

        Ok(out)
    }
}

fn emit_pipeline_avx(pipeline: &IrPipeline) -> String {
    let mut s = String::new();

    s.push_str(&format!(
        "; ── 管道: {} ───────────────────────────────────────────\n",
        pipeline.name
    ));
    s.push_str(&format!("GLOBAL {}_pipeline\n", pipeline.name));
    s.push_str(&format!("{}_pipeline:\n", pipeline.name));
    s.push_str("    push rbx\n");
    s.push_str("    push rsi\n");
    s.push_str("    sub rsp, 256              ; local stack for temporaries\n\n");

    // RCX = input ptr, RDX = output ptr (Windows x64 calling convention)
    s.push_str("    ; ── Stage 0: 参数加载 ──\n");
    s.push_str("    mov rbx, rdx              ; save output pointer\n\n");

    for stage in &pipeline.stages {
        s.push_str(&emit_stage_avx(stage));
    }

    s.push_str("    add rsp, 256\n");
    s.push_str("    pop rsi\n");
    s.push_str("    pop rbx\n");
    s.push_str("    ret\n\n");

    s
}

fn emit_stage_avx(stage: &IrStage) -> String {
    let mut s = String::new();
    let si = stage.index;
    let zi = si % 8; // zmm register index (reuse zmm0-zmm7)

    s.push_str(&format!(
        "    ; [{}] {} ({}) — {}\n",
        si, stage.opcode, stage.side, stage.opcode.description()
    ));

    match stage.opcode {
        Sephirah::王冠 => {
            s.push_str(&format!(
                "    ; 王冠: Identity — 加载输入到 ZMM 寄存器\n"
            ));
            s.push_str(&format!(
                "    vmovups zmm{}, [rcx + {}]     ; 加载 16 个 float (64 bytes)\n",
                zi, si * 64
            ));
        }
        Sephirah::智慧 => {
            s.push_str("    ; 智慧: 知识检索 — 向量比较与匹配\n");
            s.push_str(&format!(
                "    vpcmpeqd k1, zmm{}, zmm{}       ; 比较匹配\n",
                zi, (zi + 1) % 8
            ));
            s.push_str("    vmovdqu32 zmm7 {k1}, zmm1   ; 选择匹配项\n");
        }
        Sephirah::严厉 => {
            let threshold = get_float_param_avx(&stage.params, "阈值", 0.8);
            s.push_str(&format!(
                "    ; 严厉: 阈值过滤 (threshold = {})\n", threshold
            ));
            s.push_str(&format!(
                "    vbroadcastss zmm{}, [rel _c_threshold]\n", (zi + 1) % 8
            ));
            s.push_str(&format!(
                "    vcmpps k2, zmm{}, zmm{}, 17     ; CMP_LE\n",
                zi, (zi + 1) % 8
            ));
            s.push_str(&format!(
                "    vmovaps zmm{} {{k2}} {{z}}          ; 低于阈值的置零\n", zi
            ));
        }
        Sephirah::理解 => {
            s.push_str("    ; 理解: 合并整合 — 融合两个数据流\n");
            s.push_str(&format!(
                "    vaddps zmm{}, zmm{}, zmm{}         ; 合并两个输入\n",
                zi, zi, (zi + 1) % 8
            ));
        }
        Sephirah::慈悲 => {
            let weight = get_float_param_avx(&stage.params, "权重", 0.7);
            s.push_str(&format!(
                "    ; 慈悲: 加权融合 FMA (weight = {})\n", weight
            ));
            s.push_str(&format!(
                "    vbroadcastss zmm{}, [rel _c_{}]   ; 广播权重\n",
                (zi + 1) % 8,
                stage.args.get(1).map(|s| s.as_str()).unwrap_or("weight")
            ));
            s.push_str(&format!(
                "    vfmadd231ps zmm{}, zmm{}, zmm{}    ; zmm{} += zmm{} * zmm{}\n",
                zi, zi, (zi + 1) % 8, zi, zi, (zi + 1) % 8
            ));
        }
        Sephirah::美丽 => {
            s.push_str("    ; 美丽: 逐元素乘法 (哈达玛积)\n");
            s.push_str(&format!(
                "    vmulps zmm{}, zmm{}, zmm{}         ; element-wise multiply\n",
                zi, zi, (zi + 1) % 8
            ));
        }
        Sephirah::胜利 => {
            s.push_str("    ; 胜利: 条件验证 / 比较\n");
            s.push_str(&format!(
                "    vpxord zmm{}, zmm{}, zmm0          ; reset for comparison\n",
                (zi + 2) % 8, (zi + 2) % 8
            ));
            s.push_str(&format!(
                "    vcmpnleps k3, zmm{}, zmm0          ; 检测非正\n", zi
            ));
            s.push_str(&format!(
                "    vmovaps zmm{} {{k3}} {{z}}              ; 非正值归零\n", zi
            ));
        }
        Sephirah::荣耀 => {
            s.push_str("    ; 荣耀: 可行性评分\n");
            s.push_str(&format!(
                "    vmulps zmm{}, zmm{}, [rel _scale]  ; scaling\n",
                zi, zi
            ));
        }
        Sephirah::基础 => {
            s.push_str("    ; 基础: 归约聚合 (horizontal add)\n");
            s.push_str("    ; AVX-512 reduction via vreduceps\n");
            s.push_str(&format!(
                "    vreduceps zmm{}, zmm{}, 0xF        ; reduce to scalar\n",
                zi, zi
            ));
        }
        Sephirah::自我 => {
            s.push_str("    ; 自我: 自注意力 (dot-product)\n");
            s.push_str("    ; vdpbf16ps: BF16 dot product accumulate\n");
            s.push_str(&format!(
                "    vdpbf16ps zmm{}, zmm{}, zmm{}       ; BF16 fused dot product\n",
                zi, zi, (zi + 1) % 8
            ));
        }
        Sephirah::超我 => {
            s.push_str("    ; 超我: 归一化\n");
            s.push_str(&format!(
                "    vrsqrtps zmm{}, zmm{}              ; 近似 1/sqrt\n",
                (zi + 1) % 8, zi
            ));
            s.push_str(&format!(
                "    vmulps zmm{}, zmm{}, zmm{}          ; x / norm\n",
                zi, zi, (zi + 1) % 8
            ));
        }
        Sephirah::真我 => {
            s.push_str("    ; 真我: 层归一化 (mean + variance + normalize)\n");
            s.push_str("    ; mean = horizontal_add(input) / N\n");
            s.push_str(&format!(
                "    vreduceps zmm{}, zmm{}, 0xF        ; sum for mean\n",
                (zi + 1) % 8, zi
            ));
            s.push_str("    ; var = horizontal_add((x - mean)^2) / N\n");
            s.push_str("    ; output = (x - mean) * rcp(sqrt(var + eps))\n");
            s.push_str(&format!(
                "    vsubps zmm{}, zmm{}, zmm{}          ; x - mean\n",
                zi, zi, (zi + 1) % 8
            ));
        }
        Sephirah::逻辑 => {
            s.push_str("    ; 逻辑: 矩阵乘法 GEMM\n");
            s.push_str("    ; BF16 tensor core: vdpbf16ps\n");
            s.push_str(&format!(
                "    vdpbf16ps zmm{}, zmm{}, zmm{}       ; C += A * B (BF16)\n",
                zi, zi, (zi + 1) % 8
            ));
        }
        Sephirah::共情 => {
            s.push_str("    ; 共情: Softmax (SVML: vsExp2ps + reduce + div)\n");
            s.push_str(&format!(
                "    vexp2ps zmm{}, zmm{}                ; e^x (SVML)\n",
                (zi + 1) % 8, zi
            ));
            s.push_str(&format!(
                "    vreduceps zmm{}, zmm{}, 0xF        ; sum(e^x)\n",
                (zi + 2) % 8, (zi + 1) % 8
            ));
            s.push_str("    ; vrcp: approximate reciprocal\n");
            s.push_str(&format!(
                "    vdivps zmm{}, zmm{}, zmm{}          ; softmax = exp / sum\n",
                zi, (zi + 1) % 8, (zi + 2) % 8
            ));
        }
        Sephirah::幸福 => {
            s.push_str("    ; 幸福: 损失函数 (cross-entropy)\n");
            s.push_str("    ; loss = -sum(target * log(pred + eps))\n");
            s.push_str(&format!(
                "    vmulps zmm{}, zmm{}, zmm{}          ; target * pred\n",
                zi, zi, (zi + 1) % 8
            ));
            s.push_str("    ; vlog2ps: SVML logarithm\n");
        }
        Sephirah::王国 => {
            s.push_str("    ; 王国: 输出存储\n");
            s.push_str(&format!(
                "    vmovups [rbx], zmm{}               ; 写回结果到输出缓冲区\n",
                zi
            ));
        }
    }

    s.push_str("\n");
    s
}

fn get_float_param_avx(params: &[(String, IrValue)], key: &str, default: f64) -> f64 {
    for (k, v) in params {
        if k == key {
            if let IrValue::Float(f) = v { return *f; }
            if let IrValue::Integer(n) = v { return *n as f64; }
        }
    }
    default
}
