/// lib.rs — module tree of the SephirotLang compiler
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

// ── Compilation pipeline ─────────────────────────────────

/// Full compilation pipeline: source → IR → target code
pub fn compile(source: &str, target: CompileTarget) -> Result<String> {
    // 1. Lexing
    let tokens = lexer::tokenize(source)?;

    // 2. Parsing
    let ast = parser::Parser::new(tokens).parse()?;

    // 3. Semantic analysis + IR generation
    let ir = ir::build_ir(&ast)?;

    // 4. Code generation
    let emitter: Box<dyn CodeEmitter> = match target {
        CompileTarget::Ptx => Box::new(codegen::ptx::PtxEmitter),
        CompileTarget::Avx => Box::new(codegen::avx::AvxEmitter),
        CompileTarget::Dml => Box::new(codegen::dml::DmlEmitter),
    };

    emitter.emit(&ir)
}

/// Lexing + syntax check (no code generation)
pub fn check(source: &str) -> Result<parser::Program> {
    let tokens = lexer::tokenize(source)?;
    let ast = parser::Parser::new(tokens).parse()?;
    ir::build_ir(&ast)?; // semantic check
    Ok(ast)
}
