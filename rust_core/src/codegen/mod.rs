/// 代码生成后端 trait
use crate::error::Result;
use crate::ir::IrProgram;

pub mod ptx;
pub mod avx;
pub mod dml;

/// 代码生成器统一接口
pub trait CodeEmitter {
    /// 返回目标名称
    fn target_name(&self) -> &str;

    /// 生成目标代码
    fn emit(&self, ir: &IrProgram) -> Result<String>;

    /// 文件扩展名
    fn extension(&self) -> &str;
}
