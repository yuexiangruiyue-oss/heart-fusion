/// 中间表示 (IR) — 类型检查 + 数据流分析
use crate::error::{CompileError, Result};
use crate::lang::{Sephirah, SephirahType, Side};
use crate::parser::{Decl, Expr, PipelineDecl, Program};

// ── IR 类型 ───────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct IrProgram {
    pub data_decls: Vec<IrData>,
    pub const_decls: Vec<IrConst>,
    pub pipelines: Vec<IrPipeline>,
}

#[derive(Debug, Clone)]
pub struct IrData {
    pub name: String,
    pub ty: SephirahType,
    pub init_value: Option<f64>,
}

#[derive(Debug, Clone)]
pub struct IrConst {
    pub name: String,
    pub value: IrValue,
}

#[derive(Debug, Clone)]
pub enum IrValue {
    Float(f64),
    Integer(i64),
    Str(String),
    Ident(String),
}

#[derive(Debug, Clone)]
pub struct IrPipeline {
    pub name: String,
    pub stages: Vec<IrStage>,
    /// 数据流类型追踪
    pub flow_type: Option<SephirahType>,
}

#[derive(Debug, Clone)]
pub struct IrStage {
    pub index: usize,
    pub opcode: Sephirah,
    pub side: Side,
    pub args: Vec<String>,
    pub params: Vec<(String, IrValue)>,
    pub input_type: Option<SephirahType>,
    pub output_type: Option<SephirahType>,
}

// ── IR Builder ────────────────────────────────────────────

pub struct IrBuilder {
    data: Vec<IrData>,
    consts: Vec<IrConst>,
    pipelines: Vec<IrPipeline>,
    /// 已知的数据类型
    type_env: std::collections::HashMap<String, SephirahType>,
    /// 已知的常量值
    const_env: std::collections::HashMap<String, IrValue>,
}

impl IrBuilder {
    pub fn new() -> Self {
        Self {
            data: Vec::new(),
            consts: Vec::new(),
            pipelines: Vec::new(),
            type_env: std::collections::HashMap::new(),
            const_env: std::collections::HashMap::new(),
        }
    }

    pub fn build(mut self, program: &Program) -> Result<IrProgram> {
        // 第一遍：收集数据和常量声明
        for decl in &program.decls {
            match decl {
                Decl::Data(d) => {
                    let init = d.init.as_ref().and_then(|e| eval_const(e, &self.const_env));
                    let ir_data = IrData {
                        name: d.name.clone(),
                        ty: d.ty.clone(),
                        init_value: init,
                    };
                    self.type_env.insert(d.name.clone(), d.ty.clone());
                    self.data.push(ir_data);
                }
                Decl::Const(c) => {
                    let val = eval_expr_to_ir(&c.value, &self.const_env)?;
                    self.const_env.insert(c.name.clone(), val.clone());
                    self.consts.push(IrConst {
                        name: c.name.clone(),
                        value: val,
                    });
                }
                Decl::Pipeline(_) => {} // 第二遍处理
            }
        }

        // 第二遍：构建管道 IR
        for decl in &program.decls {
            if let Decl::Pipeline(p) = decl {
                let ir_pipeline = self.build_pipeline(p)?;
                self.pipelines.push(ir_pipeline);
            }
        }

        Ok(IrProgram {
            data_decls: self.data,
            const_decls: self.consts,
            pipelines: self.pipelines,
        })
    }

    fn build_pipeline(&self, pipeline: &PipelineDecl) -> Result<IrPipeline> {
        let mut ir_stages = Vec::new();
        // 默认数据流类型
        let mut current_type: Option<SephirahType> = None;

        for (i, stage) in pipeline.stages.iter().enumerate() {
            // 参数数量检查
            let min_args = stage.opcode.min_args();
            if stage.args.len() < min_args {
                return Err(CompileError::Semantic {
                    line: stage.span.line,
                    msg: format!(
                        "{} 至少需要 {} 个参数，提供了 {} 个",
                        stage.opcode, min_args, stage.args.len()
                    ),
                });
            }

            // 推断输入类型：从参数查找
            let input_type = stage.args.first()
                .and_then(|arg| self.type_env.get(arg))
                .cloned()
                .or(current_type.clone());

            // 推断输出类型（简化：输入类型传递）
            let output_type = input_type.clone();

            ir_stages.push(IrStage {
                index: i,
                opcode: stage.opcode,
                side: stage.opcode.side(),
                args: stage.args.clone(),
                params: stage.params.iter()
                    .map(|(k, v)| (k.clone(), eval_expr_to_ir(v, &self.const_env).unwrap_or(IrValue::Float(0.0))))
                    .collect(),
                input_type: input_type.clone(),
                output_type: output_type.clone(),
            });

            current_type = output_type;
        }

        Ok(IrPipeline {
            name: pipeline.name.clone(),
            stages: ir_stages,
            flow_type: current_type,
        })
    }
}

fn eval_expr_to_ir(expr: &Expr, env: &std::collections::HashMap<String, IrValue>) -> Result<IrValue> {
    match expr {
        Expr::Float(f) => Ok(IrValue::Float(*f)),
        Expr::Integer(n) => Ok(IrValue::Integer(*n)),
        Expr::Str(s) => Ok(IrValue::Str(s.clone())),
        Expr::Ident(s) => env.get(s).cloned().ok_or(CompileError::Semantic {
            line: 0, msg: format!("未知常量: {}", s),
        }),
        Expr::Neg(inner) => match eval_expr_to_ir(inner, env)? {
            IrValue::Float(f) => Ok(IrValue::Float(-f)),
            IrValue::Integer(n) => Ok(IrValue::Integer(-n)),
            other => Ok(other),
        },
        Expr::BinOp(op, l, r) => {
            let lv = eval_expr_to_ir(l, env)?;
            let rv = eval_expr_to_ir(r, env)?;
            match (lv, rv) {
                (IrValue::Float(a), IrValue::Float(b)) => Ok(IrValue::Float(match op {
                    crate::parser::BinOp::Add => a + b,
                    crate::parser::BinOp::Sub => a - b,
                    crate::parser::BinOp::Mul => a * b,
                    crate::parser::BinOp::Div => a / b,
                })),
                (IrValue::Integer(a), IrValue::Integer(b)) => Ok(IrValue::Integer(match op {
                    crate::parser::BinOp::Add => a + b,
                    crate::parser::BinOp::Sub => a - b,
                    crate::parser::BinOp::Mul => a * b,
                    crate::parser::BinOp::Div => a / b,
                })),
                (IrValue::Float(a), IrValue::Integer(b)) => Ok(IrValue::Float(match op {
                    crate::parser::BinOp::Add => a + b as f64,
                    crate::parser::BinOp::Sub => a - b as f64,
                    crate::parser::BinOp::Mul => a * b as f64,
                    crate::parser::BinOp::Div => a / b as f64,
                })),
                _ => Ok(IrValue::Float(0.0)),
            }
        }
    }
}

fn eval_const(expr: &Expr, env: &std::collections::HashMap<String, IrValue>) -> Option<f64> {
    match eval_expr_to_ir(expr, env) {
        Ok(IrValue::Float(f)) => Some(f),
        Ok(IrValue::Integer(n)) => Some(n as f64),
        _ => None,
    }
}

/// 便捷：从 AST 构建 IR
pub fn build_ir(program: &Program) -> Result<IrProgram> {
    IrBuilder::new().build(program)
}
