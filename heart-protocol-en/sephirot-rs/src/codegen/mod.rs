/// Code-generation backend trait
use crate::error::Result;
use crate::ir::IrProgram;

pub mod ptx;
pub mod avx;
pub mod dml;

/// Unified interface for code generators
pub trait CodeEmitter {
    /// Return the target name
    fn target_name(&self) -> &str;

    /// Generate the target code
    fn emit(&self, ir: &IrProgram) -> Result<String>;

    /// File extension
    fn extension(&self) -> &str;
}
