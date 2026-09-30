/// lib.rs — 质点语言 SephirotLang Compiler 模块树
pub mod error;
pub mod lang;
pub mod lexer;
pub mod parser;
pub mod ir;
pub mod codegen;
pub mod ffi;

pub use error::{CompileError, Result};
pub use lang::{CompileTarget, ElementType, Sephirah, SephirahType, Side};
pub use codegen::CodeEmitter;

// ── 编译流程 ──────────────────────────────────────────────

/// 完整编译流程: 源码 → IR → 目标代码
pub fn compile(source: &str, target: CompileTarget) -> Result<String> {
    // 1. 词法分析
    let tokens = lexer::tokenize(source)?;

    // 2. 语法分析
    let ast = parser::Parser::new(tokens).parse()?;

    // 3. 语义分析 + IR 生成
    let ir = ir::build_ir(&ast)?;

    // 4. 代码生成
    let emitter: Box<dyn CodeEmitter> = match target {
        CompileTarget::Ptx => Box::new(codegen::ptx::PtxEmitter),
        CompileTarget::Avx => Box::new(codegen::avx::AvxEmitter),
        CompileTarget::Dml => Box::new(codegen::dml::DmlEmitter),
    };

    emitter.emit(&ir)
}

/// 词法 + 语法检查（不生成代码）
pub fn check(source: &str) -> Result<parser::Program> {
    let tokens = lexer::tokenize(source)?;
    let ast = parser::Parser::new(tokens).parse()?;
    ir::build_ir(&ast)?; // 语义检查
    Ok(ast)
}
