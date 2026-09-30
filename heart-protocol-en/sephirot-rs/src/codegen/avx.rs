/// AVX-512 codegen backend — Intel x86-64 SIMD
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
        out.push_str(";  SephirotLang Compiler v1.0\n");
        out.push_str(";  16-Sephiroth Twin-Heart Protocol → Intel AVX-512\n");
        out.push_str(";  ISA ref : Intel 64/IA-32 Architectures SDM Vol.2\n");
        out.push_str(";  Features: AVX-512F, AVX-512BF16, AVX-512BITALG, SVML\n");
        out.push_str(";  Toolchain: NASM / MASM compatible\n");
        out.push_str("; ═══════════════════════════════════════════════════════════\n");
        out.push_str(";\n\n");

        out.push_str("SECTION .data\n");

        // Constants
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
        "; ── Pipeline: {} ─────────────────────────────────────────\n",
        pipeline.name
    ));
    s.push_str(&format!("GLOBAL {}_pipeline\n", pipeline.name));
    s.push_str(&format!("{}_pipeline:\n", pipeline.name));
    s.push_str("    push rbx\n");
    s.push_str("    push rsi\n");
    s.push_str("    sub rsp, 256              ; local stack for temporaries\n\n");

    // RCX = input ptr, RDX = output ptr (Windows x64 calling convention)
    s.push_str("    ; ── Stage 0: parameter loading ──\n");
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
                "    ; Keter: Identity — load input into a ZMM register\n"
            ));
            s.push_str(&format!(
                "    vmovups zmm{}, [rcx + {}]     ; load 16 floats (64 bytes)\n",
                zi, si * 64
            ));
        }
        Sephirah::智慧 => {
            s.push_str("    ; Chokmah: knowledge retrieval — vector comparison and matching\n");
            s.push_str(&format!(
                "    vpcmpeqd k1, zmm{}, zmm{}       ; compare for a match\n",
                zi, (zi + 1) % 8
            ));
            s.push_str("    vmovdqu32 zmm7 {k1}, zmm1   ; select the matched lanes\n");
        }
        Sephirah::严厉 => {
            // The "阈值" key is the Chinese-language param name (kept verbatim);
            // the English alias "threshold" is also accepted
            let threshold = get_float_param_avx(&stage.params, "阈值", 0.8);
            s.push_str(&format!(
                "    ; Binah: threshold filtering (threshold = {})\n", threshold
            ));
            s.push_str(&format!(
                "    vbroadcastss zmm{}, [rel _c_threshold]\n", (zi + 1) % 8
            ));
            s.push_str(&format!(
                "    vcmpps k2, zmm{}, zmm{}, 17     ; CMP_LE\n",
                zi, (zi + 1) % 8
            ));
            s.push_str(&format!(
                "    vmovaps zmm{} {{k2}} {{z}}          ; zero out lanes below the threshold\n", zi
            ));
        }
        Sephirah::理解 => {
            s.push_str("    ; Daat: merge/integrate — fuse two data streams\n");
            s.push_str(&format!(
                "    vaddps zmm{}, zmm{}, zmm{}         ; merge the two inputs\n",
                zi, zi, (zi + 1) % 8
            ));
        }
        Sephirah::慈悲 => {
            // The "权重" key is the Chinese-language param name (kept verbatim);
            // the English alias "weight" is also accepted
            let weight = get_float_param_avx(&stage.params, "权重", 0.7);
            s.push_str(&format!(
                "    ; Chesed: weighted blend FMA (weight = {})\n", weight
            ));
            s.push_str(&format!(
                "    vbroadcastss zmm{}, [rel _c_{}]   ; broadcast the weight\n",
                (zi + 1) % 8,
                stage.args.get(1).map(|s| s.as_str()).unwrap_or("weight")
            ));
            s.push_str(&format!(
                "    vfmadd231ps zmm{}, zmm{}, zmm{}    ; zmm{} += zmm{} * zmm{}\n",
                zi, zi, (zi + 1) % 8, zi, zi, (zi + 1) % 8
            ));
        }
        Sephirah::美丽 => {
            s.push_str("    ; Tiferet: element-wise multiply (Hadamard product)\n");
            s.push_str(&format!(
                "    vmulps zmm{}, zmm{}, zmm{}         ; element-wise multiply\n",
                zi, zi, (zi + 1) % 8
            ));
        }
        Sephirah::胜利 => {
            s.push_str("    ; Netzach: conditional validation / comparison\n");
            s.push_str(&format!(
                "    vpxord zmm{}, zmm{}, zmm0          ; reset for comparison\n",
                (zi + 2) % 8, (zi + 2) % 8
            ));
            s.push_str(&format!(
                "    vcmpnleps k3, zmm{}, zmm0          ; detect non-positive\n", zi
            ));
            s.push_str(&format!(
                "    vmovaps zmm{} {{k3}} {{z}}              ; zero out non-positive lanes\n", zi
            ));
        }
        Sephirah::荣耀 => {
            s.push_str("    ; Hod: feasibility scoring\n");
            s.push_str(&format!(
                "    vmulps zmm{}, zmm{}, [rel _scale]  ; scaling\n",
                zi, zi
            ));
        }
        Sephirah::基础 => {
            s.push_str("    ; Yesod: reduction / aggregation (horizontal add)\n");
            s.push_str("    ; AVX-512 reduction via vreduceps\n");
            s.push_str(&format!(
                "    vreduceps zmm{}, zmm{}, 0xF        ; reduce to scalar\n",
                zi, zi
            ));
        }
        Sephirah::自我 => {
            s.push_str("    ; Ego: self-attention (dot product)\n");
            s.push_str("    ; vdpbf16ps: BF16 dot product accumulate\n");
            s.push_str(&format!(
                "    vdpbf16ps zmm{}, zmm{}, zmm{}       ; BF16 fused dot product\n",
                zi, zi, (zi + 1) % 8
            ));
        }
        Sephirah::超我 => {
            s.push_str("    ; SuperEgo: normalization\n");
            s.push_str(&format!(
                "    vrsqrtps zmm{}, zmm{}              ; approximate 1/sqrt\n",
                (zi + 1) % 8, zi
            ));
            s.push_str(&format!(
                "    vmulps zmm{}, zmm{}, zmm{}          ; x / norm\n",
                zi, zi, (zi + 1) % 8
            ));
        }
        Sephirah::真我 => {
            s.push_str("    ; TrueSelf: layer normalization (mean + variance + normalize)\n");
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
            s.push_str("    ; Logic: matrix multiplication GEMM\n");
            s.push_str("    ; BF16 tensor core: vdpbf16ps\n");
            s.push_str(&format!(
                "    vdpbf16ps zmm{}, zmm{}, zmm{}       ; C += A * B (BF16)\n",
                zi, zi, (zi + 1) % 8
            ));
        }
        Sephirah::共情 => {
            s.push_str("    ; Empathy: Softmax (SVML: vsExp2ps + reduce + div)\n");
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
            s.push_str("    ; Joy: opposite unification (dual coexistence)\n");
            s.push_str("    ; modulus = sqrt(a^2 + b^2); balance = phase distance from pi/4\n");
            s.push_str(&format!(
                "    vmulps zmm{}, zmm{}, zmm{}          ; a^2 (logic pole)\n",
                zi, zi, zi
            ));
            s.push_str(&format!(
                "    vmulps zmm{}, zmm{}, zmm{}          ; b^2 (empathy pole)\n",
                (zi + 1) % 8, (zi + 1) % 8, (zi + 1) % 8
            ));
            s.push_str("    ; vsqrtps: dual fuse \n");
        }
        Sephirah::王国 => {
            s.push_str("    ; Malkuth: output store\n");
            s.push_str(&format!(
                "    vmovups [rbx], zmm{}               ; write the result back to the output buffer\n",
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
