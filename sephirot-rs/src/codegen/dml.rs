/// DirectML 代码生成后端 — Microsoft Windows AI 算子图
use crate::codegen::CodeEmitter;
use crate::error::Result;
use crate::ir::{IrProgram, IrStage, IrValue};

pub struct DmlEmitter;

impl CodeEmitter for DmlEmitter {
    fn target_name(&self) -> &str { "DirectML (Windows AI)" }
    fn extension(&self) -> &str { "dml.json" }

    fn emit(&self, ir: &IrProgram) -> Result<String> {
        let mut ops = Vec::new();
        let mut node_id = 0usize;

        for pipeline in &ir.pipelines {
            for stage in &pipeline.stages {
                ops.push(emit_stage_dml(stage, &mut node_id));
            }
        }

        // 构建 JSON
        let mut json = String::new();
        json.push_str("{\n");
        json.push_str("  \"compiler\": \"SephirotLang v1.0 — 16质点神人双生协议\",\n");
        json.push_str("  \"target\": \"DirectML\",\n");
        json.push_str("  \"spec\": \"Microsoft DirectML 1.13 / DirectX 12 Ultimate\",\n\n");

        // 数据声明
        json.push_str("  \"data\": {\n");
        for (i, d) in ir.data_decls.iter().enumerate() {
            json.push_str(&format!(
                "    \"{}\": {{ \"type\": \"{}\", \"bytes\": {} }}{}",
                d.name, d.ty, d.ty.total_bytes(),
                if i + 1 < ir.data_decls.len() { "," } else { "" }
            ));
            json.push_str("\n");
        }
        json.push_str("  },\n\n");

        // 常量
        if !ir.const_decls.is_empty() {
            json.push_str("  \"constants\": {\n");
            for (i, c) in ir.const_decls.iter().enumerate() {
                let val_str = match &c.value {
                    IrValue::Float(f) => format!("{}", f),
                    IrValue::Integer(n) => format!("{}", n),
                    IrValue::Str(s) => format!("\"{}\"", s),
                    IrValue::Ident(_) => "\"$ref$\"".to_string(),
                };
                json.push_str(&format!(
                    "    \"{}\": {}{}",
                    c.name, val_str,
                    if i + 1 < ir.const_decls.len() { "," } else { "" }
                ));
                json.push_str("\n");
            }
            json.push_str("  },\n\n");
        }

        // 算子图
        json.push_str("  \"operators\": [\n");
        for (i, op) in ops.iter().enumerate() {
            json.push_str("    ");
            json.push_str(op);
            if i + 1 < ops.len() {
                json.push_str(",");
            }
            json.push_str("\n");
        }
        json.push_str("  ]\n");
        json.push_str("}\n");

        Ok(json)
    }
}

fn emit_stage_dml(stage: &IrStage, node_id: &mut usize) -> String {
    let id = *node_id;
    *node_id += 1;
    let next_id = *node_id;

    let mut s = String::new();

    s.push_str("{\n");
    s.push_str(&format!("      \"id\": {},\n", id));
    s.push_str(&format!("      \"opcode\": \"{}\",\n", stage.opcode));
    s.push_str(&format!("      \"hebrew\": \"{}\",\n", stage.opcode.hebrew()));
    s.push_str(&format!("      \"side\": \"{}\",\n", stage.side));
    s.push_str(&format!("      \"description\": \"{}\",\n", stage.opcode.description()));
    s.push_str(&format!("      \"dml_operator\": \"{}\",\n", stage.opcode.dml_operator()));

    // 输入/输出
    s.push_str("      \"inputs\": [");
    for (i, arg) in stage.args.iter().enumerate() {
        if i > 0 { s.push_str(", "); }
        s.push_str(&format!("\"{}\"", arg));
    }
    s.push_str("],\n");
    s.push_str(&format!("      \"output\": \"s{}\",\n", next_id));

    // 参数
    if !stage.params.is_empty() {
        s.push_str("      \"params\": {");
        for (i, (k, v)) in stage.params.iter().enumerate() {
            if i > 0 { s.push_str(", "); }
            let val_str = match v {
                IrValue::Float(f) => format!("{}", f),
                IrValue::Integer(n) => format!("{}", n),
                IrValue::Str(sv) => format!("\"{}\"", sv),
                IrValue::Ident(_) => "\"$ref$\"".to_string(),
            };
            s.push_str(&format!("\"{}\": {}", k, val_str));
        }
        s.push_str("},\n");
    }

    // PTX/AVX 交叉参考
    s.push_str(&format!("      \"ptx_instruction\": \"{}\",\n", stage.opcode.ptx_instruction()));
    s.push_str(&format!("      \"avx_instruction\": \"{}\"\n", stage.opcode.avx_instruction()));

    s.push_str("    }");

    s
}
