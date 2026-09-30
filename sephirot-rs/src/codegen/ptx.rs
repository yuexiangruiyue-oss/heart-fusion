/// PTX sm_89 codegen backend - NVIDIA Ada Lovelace / RTX 4050
/// Outputs ptxas-assemblable ASCII-only PTX (CUDA 13.2 compatible)
///
/// 寄存器数据流：每个质点的输出寄存器成为下一质点的输入寄存器，
/// 形成真正的链式管道（不再各自从全局指针重载输入）。
use crate::codegen::CodeEmitter;
use crate::error::Result;
use crate::ir::{IrProgram, IrPipeline, IrStage, IrValue};
use crate::lang::Sephirah;

pub struct PtxEmitter;

impl CodeEmitter for PtxEmitter {
    fn target_name(&self) -> &str { "PTX sm_89 (NVIDIA Ada Lovelace)" }
    fn extension(&self) -> &str { "ptx" }

    fn emit(&self, ir: &IrProgram) -> Result<String> {
        let mut out = String::new();

        // Header (ASCII only for ptxas compatibility)
        out.push_str("//\n");
        out.push_str("// SephirotLang v1.0 - 16 Sephiroth PTX Kernel\n");
        out.push_str("// Target: sm_89 (RTX 4050 Ada Lovelace)\n");
        out.push_str("// PTX ISA 8.5 / CUDA 13.2\n");
        out.push_str("//\n\n");

        out.push_str(".version 8.5\n");
        out.push_str(".target sm_89\n");
        out.push_str(".address_size 64\n\n");

        // Collect unique params from all pipelines
        let mut all_params: Vec<String> = Vec::new();
        for pipeline in &ir.pipelines {
            for stage in &pipeline.stages {
                for arg in &stage.args {
                    if !all_params.contains(arg) {
                        all_params.push(arg.clone());
                    }
                }
            }
        }

        // Emit kernels for each pipeline
        for pipeline in &ir.pipelines {
            out.push_str(&emit_pipeline_ptx(pipeline, &all_params));
        }

        Ok(out)
    }
}

/// Convert f64 to PTX hex float literal (0fXXXXXXXX)
fn f32_to_ptx_hex(val: f64) -> String {
    let bits = (val as f32).to_bits();
    format!("0f{:08X}", bits)
}

fn emit_pipeline_ptx(pipeline: &IrPipeline, all_params: &[String]) -> String {
    let mut s = String::new();

    s.push_str("// ============================================================\n");
    s.push_str(&format!("// Pipeline: {}\n", pipeline.name));
    s.push_str("// ============================================================\n\n");

    // Kernel signature - up to 8 params for simplicity
    let param_count = std::cmp::min(all_params.len(), 8);
    let param_count = std::cmp::max(param_count, pipeline.stages.len() + 1);

    s.push_str(".visible .entry sephirot_kernel(\n");
    for i in 0..std::cmp::min(param_count, 9) {
        s.push_str(&format!("    .param .u64 p{},\n", i));
    }
    s.push_str("    .param .u64 p_output\n");
    s.push_str(") {\n");
    s.push_str("    .reg .pred  %p<4>;\n");
    s.push_str("    .reg .f32   %f<64>;\n");
    s.push_str("    .reg .u32   %r<4>;\n");
    s.push_str("    .reg .u64   %rd<12>;\n\n");

    // Load all param pointers into general-purpose registers
    for i in 0..std::cmp::min(param_count, 9) {
        s.push_str(&format!("    ld.param.u64 %rd{}, [p{}];\n", i, i));
    }
    s.push_str("    ld.param.u64 %rd10, [p_output];\n\n");

    // Thread index
    s.push_str("    mov.u32 %r0, %tid.x;\n");
    s.push_str("    cvt.u64.u32 %rd11, %r0;\n\n");

    // 链式寄存器数据流：上一阶段的输出寄存器 = 下一阶段的输入寄存器
    let mut prev_reg: Option<u32> = None;
    let mut last_reg = 0u32;
    for stage in &pipeline.stages {
        let (code, final_reg) = emit_stage_ptx(stage, all_params, prev_reg);
        s.push_str(&code);
        last_reg = final_reg;
        prev_reg = Some(final_reg);
    }

    // Write output
    s.push_str(&format!(
        "    st.global.f32 [%rd10], %f{};\n\n",
        last_reg
    ));

    s.push_str("    ret;\n");
    s.push_str("}\n\n");

    s
}

fn get_param_reg(arg: &str, all_params: &[String]) -> usize {
    all_params.iter().position(|p| p == arg).unwrap_or(0)
}

/// 从阶段参数中取浮点值；支持中文与英文键名
fn get_float_param(params: &[(String, IrValue)], keys: &[&str], default: f64) -> f64 {
    for (k, v) in params {
        if keys.contains(&k.as_str()) {
            if let IrValue::Float(f) = v { return *f; }
            if let IrValue::Integer(n) = v { return *n as f64; }
        }
    }
    default
}

fn emit_stage_ptx(stage: &IrStage, all_params: &[String], prev_reg: Option<u32>) -> (String, u32) {
    let mut s = String::new();
    let ri = (stage.index * 4) as u32;

    // Header comment
    s.push_str(&format!(
        "    // [{:>2}] {} ({:?}) - {}\n",
        stage.index, stage.opcode.keyword(), stage.opcode.side(), stage.opcode.description()
    ));
    s.push_str(&format!(
        "    // PTX: {}\n", stage.opcode.ptx_instruction()
    ));

    // 输入寄存器：首阶段从参数指针加载；后续阶段使用上游输出
    let in_reg: u32 = match prev_reg {
        Some(pr) => {
            s.push_str(&format!("    // in  = %f{} (上游输出)\n", pr));
            pr
        }
        None => {
            let arg0 = stage.args.first().map(|s| s.as_str()).unwrap_or("");
            let pr = get_param_reg(arg0, all_params);
            s.push_str(&format!("    // in  = [%rd{}] (首阶段参数加载)\n", pr));
            s.push_str(&format!("    ld.global.nc.f32 %f{}, [%rd{}];\n", ri, pr));
            ri
        }
    };

    let out_reg = match stage.opcode {
        Sephirah::王冠 => {
            // Identity / Load — 直通
            s.push_str("    // 恒等变换: out = in\n");
            in_reg
        }
        Sephirah::智慧 => {
            let arg1 = stage.args.get(1).map(|s| s.as_str()).unwrap_or("");
            let pr1 = get_param_reg(arg1, all_params);
            s.push_str(&format!("    ld.global.nc.f32 %f{}, [%rd{}];\n", ri + 1, pr1));
            s.push_str(&format!("    mul.f32 %f{}, %f{}, %f{};\n", ri + 2, in_reg, ri + 1));
            ri + 2
        }
        Sephirah::严厉 => {
            let threshold = get_float_param(&stage.params, &["阈值", "threshold"], 0.8);
            let hex = f32_to_ptx_hex(threshold);
            let zero_hex = f32_to_ptx_hex(0.0);
            s.push_str(&format!("    mov.f32 %f{}, {};   // threshold\n", ri + 1, hex));
            s.push_str(&format!("    setp.lt.f32 %p0, %f{}, %f{};\n", in_reg, ri + 1));
            s.push_str(&format!("    selp.f32 %f{}, {}, %f{}, %p0;  // 低于阈值置零\n", ri + 2, zero_hex, in_reg));
            ri + 2
        }
        Sephirah::理解 => {
            let arg1 = stage.args.get(1).map(|s| s.as_str()).unwrap_or("");
            let pr1 = get_param_reg(arg1, all_params);
            s.push_str(&format!("    ld.global.nc.f32 %f{}, [%rd{}];\n", ri + 1, pr1));
            s.push_str(&format!("    add.f32 %f{}, %f{}, %f{};\n", ri + 2, in_reg, ri + 1));
            ri + 2
        }
        Sephirah::慈悲 => {
            let weight = get_float_param(&stage.params, &["权重", "weight"], 0.7);
            let hex_w = f32_to_ptx_hex(weight);
            s.push_str(&format!("    mov.f32 %f{}, {};   // weight\n", ri + 1, hex_w));
            s.push_str(&format!("    fma.rn.f32 %f{}, %f{}, %f{}, 0f00000000;\n", ri + 2, in_reg, ri + 1));
            ri + 2
        }
        Sephirah::美丽 => {
            let arg1 = stage.args.get(1).map(|s| s.as_str()).unwrap_or("");
            let pr1 = get_param_reg(arg1, all_params);
            s.push_str(&format!("    ld.global.nc.f32 %f{}, [%rd{}];\n", ri + 1, pr1));
            s.push_str(&format!("    mul.f32 %f{}, %f{}, %f{};   // 哈达玛积\n", ri + 2, in_reg, ri + 1));
            ri + 2
        }
        Sephirah::胜利 => {
            let zero_hex = f32_to_ptx_hex(0.0);
            s.push_str(&format!("    setp.ge.f32 %p1, %f{}, {};\n", in_reg, zero_hex));
            s.push_str(&format!("    selp.f32 %f{}, %f{}, {}, %p1;  // 非负验证\n", ri + 1, in_reg, zero_hex));
            ri + 1
        }
        Sephirah::荣耀 => {
            let half_hex = f32_to_ptx_hex(0.5);
            s.push_str(&format!("    mul.f32 %f{}, %f{}, {};\n", ri + 1, in_reg, half_hex));
            s.push_str(&format!("    add.f32 %f{}, %f{}, %f{};   // 可行性评分\n", ri + 2, ri + 1, in_reg));
            ri + 2
        }
        Sephirah::基础 => {
            s.push_str(&format!("    atom.global.add.f32 %f{}, [%rd10], %f{};  // 全局归约\n", ri + 1, in_reg));
            ri + 1
        }
        Sephirah::超我 => {
            s.push_str(&format!("    rcp.rn.f32 %f{}, %f{};\n", ri + 1, in_reg));
            s.push_str(&format!("    mul.f32 %f{}, %f{}, %f{};   // LayerNorm\n", ri + 2, in_reg, ri + 1));
            ri + 2
        }
        Sephirah::自我 => {
            let arg1 = stage.args.get(1).map(|s| s.as_str()).unwrap_or("");
            let pr1 = get_param_reg(arg1, all_params);
            s.push_str(&format!("    ld.global.nc.f32 %f{}, [%rd{}];\n", ri + 1, pr1));
            s.push_str(&format!("    mul.f32 %f{}, %f{}, %f{};   // 自注意力(dot)\n", ri + 2, in_reg, ri + 1));
            ri + 2
        }
        Sephirah::真我 => {
            let eps_hex = f32_to_ptx_hex(1e-8);
            s.push_str(&format!("    add.f32 %f{}, %f{}, {};\n", ri + 1, in_reg, eps_hex));
            s.push_str(&format!("    rcp.rn.f32 %f{}, %f{};\n", ri + 2, ri + 1));
            s.push_str(&format!("    mul.f32 %f{}, %f{}, %f{};   // 层归一化整合\n", ri + 3, in_reg, ri + 2));
            ri + 3
        }
        Sephirah::逻辑 => {
            let arg1 = stage.args.get(1).map(|s| s.as_str()).unwrap_or("");
            let pr1 = get_param_reg(arg1, all_params);
            s.push_str(&format!("    ld.global.nc.f32 %f{}, [%rd{}];\n", ri + 1, pr1));
            s.push_str(&format!("    mul.f32 %f{}, %f{}, %f{};\n", ri + 2, in_reg, ri + 1));
            s.push_str(&format!("    add.f32 %f{}, %f{}, %f{};   // GEMM(简化)\n", ri + 3, ri + 2, in_reg));
            ri + 3
        }
        Sephirah::共情 => {
            s.push_str(&format!("    ex2.approx.f32 %f{}, %f{};\n", ri + 1, in_reg));
            s.push_str(&format!("    mul.f32 %f{}, %f{}, %f{};\n", ri + 2, ri + 1, ri + 1));
            s.push_str(&format!("    rcp.rn.f32 %f{}, %f{};\n", ri + 3, ri + 2));
            s.push_str(&format!("    mul.f32 %f{}, %f{}, %f{};   // Softmax\n", ri + 4, ri + 1, ri + 3));
            ri + 4
        }
        Sephirah::幸福 => {
            let arg1 = stage.args.get(1).map(|s| s.as_str()).unwrap_or("");
            let pr1 = get_param_reg(arg1, all_params);
            s.push_str(&format!("    ld.global.nc.f32 %f{}, [%rd{}];   // target\n", ri + 1, pr1));
            s.push_str(&format!("    sub.f32 %f{}, %f{}, %f{};\n", ri + 2, in_reg, ri + 1));
            s.push_str(&format!("    mul.f32 %f{}, %f{}, %f{};   // 损失(MSE)\n", ri + 3, ri + 2, ri + 2));
            ri + 3
        }
        Sephirah::王国 => {
            s.push_str("    // 输出存储: out = in (由内核尾声写回)\n");
            in_reg
        }
    };

    s.push_str("\n");
    (s, out_reg)
}
