/// Compiler error types for the Sephirot language
use thiserror::Error;

#[derive(Error, Debug)]
pub enum CompileError {
    #[error("[lexical error] line {line}, col {col}: {msg}")]
    Lex { line: usize, col: usize, msg: String },

    #[error("[syntax error] line {line}, col {col}: expected {expected}, got {got}")]
    Parse {
        line: usize,
        col: usize,
        expected: &'static str,
        got: String,
    },

    #[error("[semantic error] line {line}: {msg}")]
    Semantic { line: usize, msg: String },

    #[error("[codegen error] {msg}")]
    Codegen { msg: String },

    #[error("[I/O error] {0}")]
    Io(#[from] std::io::Error),
}

pub type Result<T> = std::result::Result<T, CompileError>;
