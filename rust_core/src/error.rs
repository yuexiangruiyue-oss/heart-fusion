/// 质点语言编译器错误类型
use thiserror::Error;

#[derive(Error, Debug)]
pub enum CompileError {
    #[error("[词法错误] 行{line} 列{col}: {msg}")]
    Lex { line: usize, col: usize, msg: String },

    #[error("[语法错误] 行{line} 列{col}: 期望 {expected}, 得到 {got}")]
    Parse {
        line: usize,
        col: usize,
        expected: &'static str,
        got: String,
    },

    #[error("[语义错误] 行{line}: {msg}")]
    Semantic { line: usize, msg: String },

    #[error("[代码生成错误] {msg}")]
    Codegen { msg: String },

    #[error("[I/O错误] {0}")]
    Io(#[from] std::io::Error),
}

pub type Result<T> = std::result::Result<T, CompileError>;
