/// 质点语言 SephirotLang Compiler — CLI 入口
/// 16质点神人双生协议 完全体通用编译器

// 库 crate 已更名为 heart_core(与 C-ABI 同名);此处保持旧路径兼容
extern crate heart_core as sephirot_rs;

use clap::{Parser as ClapParser, Subcommand};
use colored::*;
use std::fs;
use std::path::Path;

use sephirot_rs::{compile, check, CompileTarget, Sephirah};

// ── Windows UTF-8 终端 ────────────────────────────────────
#[cfg(target_os = "windows")]
fn setup_utf8() {
    extern "system" {
        fn SetConsoleOutputCP(codepage: u32) -> i32;
        fn SetConsoleCP(codepage: u32) -> i32;
    }
    unsafe {
        SetConsoleOutputCP(65001);
        SetConsoleCP(65001);
    }
}

#[cfg(not(target_os = "windows"))]
fn setup_utf8() {}

// ── CLI 定义 ──────────────────────────────────────────────

#[derive(ClapParser)]
#[command(name = "sephirot")]
#[command(version = "1.0.0")]
#[command(about = "16质点神人双生协议 — 质点语言完全体通用编译器")]
#[command(long_about = "SephirotLang Compiler v1.0\n16 Sephiroth Built-in Primitives → PTX sm_89 / AVX-512 / DirectML")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// 编译 .sephirot 源文件为目标代码
    Compile {
        /// 源文件路径 (.sephirot)
        input: String,

        /// 编译目标: ptx / avx / dml
        #[arg(short, long, default_value = "ptx")]
        target: String,

        /// 输出文件路径（默认自动推导）
        #[arg(short, long)]
        out: Option<String>,

        /// 打印到终端（不写文件）
        #[arg(long)]
        stdout: bool,
    },

    /// 检查源文件语法和语义
    Check {
        /// 源文件路径
        input: String,
    },

    /// 编译并执行 inline 源码
    Run {
        /// 内联源码
        source: Vec<String>,

        /// 编译目标
        #[arg(short, long, default_value = "ptx")]
        target: String,
    },

    /// 列出 16 质点算子
    Vocab,

    /// 交互式 REPL
    Repl,

    /// CPU 模拟执行 PTX 管道（无需 CUDA）
    Simulate {
        /// 源文件路径 (.sephirot)
        input: String,

        /// 输入值（逗号分隔：input,kb,target）
        #[arg(short, long, default_value = "1.0,2.5,0.9")]
        values: String,
    },
}

// ── 主函数 ────────────────────────────────────────────────

fn main() {
    setup_utf8();

    let cli = Cli::parse();

    let result = match cli.command {
        Commands::Compile { input, target, out, stdout } => {
            cmd_compile(&input, &target, out.as_deref(), stdout)
        }
        Commands::Check { input } => cmd_check(&input),
        Commands::Run { source, target } => cmd_run(&source.join(" "), &target),
        Commands::Vocab => cmd_vocab(),
        Commands::Repl => cmd_repl(),
        Commands::Simulate { input, values } => cmd_simulate(&input, &values),
    };

    if let Err(e) = result {
        eprintln!("{}", e.to_string().red().bold());
        std::process::exit(1);
    }
}

// ── 命令实现 ──────────────────────────────────────────────

fn cmd_compile(input: &str, target: &str, out: Option<&str>, to_stdout: bool) -> sephirot_rs::Result<()> {
    let source = fs::read_to_string(input)
        .map_err(|e| sephirot_rs::CompileError::Io(e))?;

    let compile_target: CompileTarget = target.parse()
        .map_err(|e| sephirot_rs::CompileError::Codegen { msg: e })?;

    eprintln!("{}", "╔══════════════════════════════════════════════════╗".dimmed());
    eprintln!("{}", "║   质点语言 SephirotLang Compiler v1.0          ║".cyan());
    eprintln!("{}", "║   16质点神人双生协议 → GPU Machine Code        ║".cyan());
    eprintln!("{}", "╚══════════════════════════════════════════════════╝".dimmed());
    eprintln!("{}", format!("  源文件: {}", input).dimmed());
    eprintln!("{}", format!("  目标:   {}", compile_target).dimmed());
    eprintln!();

    let code = compile(&source, compile_target)?;

    if to_stdout {
        println!("{}", code);
    } else {
        let output_path = match out {
            Some(p) => p.to_string(),
            None => {
                let stem = Path::new(input).file_stem()
                    .map(|s| s.to_string_lossy().to_string())
                    .unwrap_or_else(|| "output".into());
                match compile_target {
                    CompileTarget::Ptx => format!("{}.ptx", stem),
                    CompileTarget::Avx => format!("{}.asm", stem),
                    CompileTarget::Dml => format!("{}.dml.json", stem),
                }
            }
        };

        fs::write(&output_path, &code)?;
        eprintln!("{}", "  ✅ 编译成功".green().bold());
        eprintln!("{}", format!("  输出: {}", output_path).green());
        eprintln!("{}", format!("  大小: {} bytes", code.len()).dimmed());
    }

    Ok(())
}

fn cmd_check(input: &str) -> sephirot_rs::Result<()> {
    let source = fs::read_to_string(input)
        .map_err(|e| sephirot_rs::CompileError::Io(e))?;

    match check(&source) {
        Ok(ast) => {
            let decl_count = ast.decls.len();
            eprintln!("{}", "✅ 检查通过".green().bold());
            eprintln!("{}", format!("  声明数: {}", decl_count).dimmed());
            for decl in &ast.decls {
                match decl {
                    sephirot_rs::parser::Decl::Data(d) => {
                        eprintln!("  {} {} : {}", "数据".yellow(), d.name, d.ty);
                    }
                    sephirot_rs::parser::Decl::Const(c) => {
                        eprintln!("  {} {}", "常量".yellow(), c.name);
                    }
                    sephirot_rs::parser::Decl::Pipeline(p) => {
                        eprintln!("  {} {} ({} stages)", "管道".yellow(), p.name, p.stages.len());
                        for stage in &p.stages {
                            eprintln!("    {} {}({}) [{}]",
                                format!("[{}]", stage.opcode.side()).dimmed(),
                                stage.opcode.keyword().green(),
                                stage.args.join(", "),
                                stage.params.iter()
                                    .map(|(k, _)| k.as_str())
                                    .collect::<Vec<_>>()
                                    .join(", ")
                            );
                        }
                    }
                }
            }
            Ok(())
        }
        Err(e) => Err(e),
    }
}

fn cmd_run(source: &str, target: &str) -> sephirot_rs::Result<()> {
    let compile_target: CompileTarget = target.parse()
        .map_err(|e| sephirot_rs::CompileError::Codegen { msg: e })?;

    eprintln!("{}", format!("═ 编译 inline 源码 → {} ═", compile_target).cyan());
    eprintln!();

    let code = compile(source, compile_target)?;
    println!("{}", code);
    Ok(())
}

fn cmd_vocab() -> sephirot_rs::Result<()> {
    println!("\n{}", "══════════════════════════════════════════════════".cyan());
    println!("{}", "  16质点神人双生协议 — 内置核心算子 (Built-in Opcodes)".cyan());
    println!("{}", "══════════════════════════════════════════════════".cyan());
    println!();

    for (i, op) in Sephirah::ALL.iter().enumerate() {
        let side_str = match op.side() {
            sephirot_rs::Side::Divine => "神侧".magenta(),
            sephirot_rs::Side::Human => "人侧".blue(),
        };
        println!("  {:>2}. {} ({}) — {}",
            i + 1,
            format!("{}", op).green().bold(),
            side_str,
            op.description()
        );
        println!("      PTX: {}", op.ptx_instruction().dimmed());
        println!("      AVX: {}", op.avx_instruction().dimmed());
        println!("      DML: {}", op.dml_operator().dimmed());
        println!();
    }

    Ok(())
}

fn cmd_repl() -> sephirot_rs::Result<()> {
    eprintln!("\n{}", "═══ 质点语言 REPL ═══".cyan());
    eprintln!("{}", "输入源码以编译，或 :help 查看命令，:exit 退出".dimmed());
    eprintln!();

    let mut current_target = CompileTarget::Ptx;
    let mut line_buf = String::new();
    let mut in_block = false;

    loop {
        let prompt = if in_block {
            "  ... ".dimmed()
        } else {
            format!("{}> ", current_target).yellow()
        };
        eprint!("{}", prompt);
        use std::io::Write;
        std::io::stderr().flush().ok();

        let mut input = String::new();
        if std::io::stdin().read_line(&mut input).unwrap_or(0) == 0 {
            break;
        }
        let trimmed = input.trim();

        if trimmed.is_empty() {
            continue;
        }

        // 内部命令
        if trimmed == ":exit" || trimmed == ":q" {
            eprintln!("{}", "再见".dimmed());
            break;
        }
        if trimmed == ":help" {
            eprintln!("  :ptx      切换到 PTX 目标");
            eprintln!("  :avx      切换到 AVX-512 目标");
            eprintln!("  :dml      切换到 DirectML 目标");
            eprintln!("  :vocab    列出 16 质点算子");
            eprintln!("  :check    检查语法");
            eprintln!("  :exit     退出");
            continue;
        }
        if trimmed == ":ptx" {
            current_target = CompileTarget::Ptx;
            eprintln!("{}", "目标: PTX sm_89".green());
            continue;
        }
        if trimmed == ":avx" {
            current_target = CompileTarget::Avx;
            eprintln!("{}", "目标: AVX-512".green());
            continue;
        }
        if trimmed == ":dml" {
            current_target = CompileTarget::Dml;
            eprintln!("{}", "目标: DirectML".green());
            continue;
        }
        if trimmed == ":vocab" {
            cmd_vocab()?;
            continue;
        }

        // 多行输入（管道声明跨行）
        if trimmed.ends_with(':') || trimmed.ends_with('|') || in_block {
            line_buf.push_str(trimmed);
            line_buf.push('\n');
            in_block = true;
            continue;
        }

        line_buf.push_str(trimmed);

        // 编译
        if trimmed == ":check" {
            match check(&line_buf) {
                Ok(_) => eprintln!("{}", "✅ 语法正确".green()),
                Err(e) => eprintln!("{}", e.to_string().red()),
            }
        } else {
            match compile(&line_buf, current_target) {
                Ok(code) => {
                    eprintln!("{}", "─── 编译输出 ───".cyan());
                    println!("{}", code);
                    eprintln!("{}", "─── 结束 ───".cyan());
                }
                Err(e) => eprintln!("{}", e.to_string().red()),
            }
        }

        line_buf.clear();
        in_block = false;
    }

    Ok(())
}

fn cmd_simulate(input: &str, values: &str) -> sephirot_rs::Result<()> {
    let source = fs::read_to_string(input)
        .map_err(|e| sephirot_rs::CompileError::Io(e))?;

    // 解析输入参数
    let v: Vec<f64> = values.split(',')
        .filter_map(|s| s.trim().parse::<f64>().ok())
        .collect();
    let input_val = v.get(0).copied().unwrap_or(1.0) as f32;
    let kb_val    = v.get(1).copied().unwrap_or(2.5) as f32;
    let target_val= v.get(2).copied().unwrap_or(0.9) as f32;

    // 词法 + 语法 + 语义检查，并构建 IR
    let ast = check(&source)?;
    let ir = sephirot_rs::ir::build_ir(&ast)?;

    eprintln!("\n{}", "============================================================".cyan());
    eprintln!("{}", "  质点语言 SephirotLang — PTX 管道 CPU 模拟执行".cyan());
    eprintln!("{}", "  16质点神人双生协议 → RTX 4050 sm_89 模拟".cyan());
    eprintln!("{}", "============================================================".cyan());
    eprintln!("  输入: {}, 知识库: {}, 目标: {}", input_val, kb_val, target_val);
    eprintln!("{}", "------------------------------------------------------------".dimmed());

    if ir.pipelines.is_empty() {
        eprintln!("{}", "  错误: 源文件中没有任何管道声明".red());
        return Err(sephirot_rs::CompileError::Semantic {
            line: 0,
            msg: "缺少管道声明".into(),
        });
    }

    // 执行源文件中声明的第一条管道（真实解析 .sephirot 内容，而非固定 16 步）
    let pipeline = &ir.pipelines[0];
    eprintln!("{}", format!("  管道: {} ({} 个质点阶段)", pipeline.name, pipeline.stages.len()).cyan());
    eprintln!("{}", "------------------------------------------------------------".dimmed());

    // 链式数据流寄存器：上一阶段输出 = 下一阶段输入
    let mut f = input_val;

    for stage in &pipeline.stages {
        let side = match stage.side {
            sephirot_rs::Side::Divine => "神侧",
            sephirot_rs::Side::Human => "人侧",
        };
        f = match stage.opcode {
            Sephirah::王冠 => {
                println!("[{:>2}] 王冠 ({}) 恒等变换: {} ← 加载输入", stage.index, side, f);
                f
            }
            Sephirah::智慧 => {
                println!("[{:>2}] 智慧 ({}) mul.f32 {} * {} = {} ← 知识检索", stage.index, side, f, kb_val, f * kb_val);
                f * kb_val
            }
            Sephirah::严厉 => {
                let threshold = stage_float(&stage.params, &["阈值", "threshold"], 0.8);
                let out = if f < threshold { 0.0 } else { f };
                println!("[{:>2}] 严厉 ({}) setp {} < {} → {} ← 阈值过滤", stage.index, side, f, threshold, out);
                out
            }
            Sephirah::理解 => {
                println!("[{:>2}] 理解 ({}) add.f32 {} + {} = {} ← 合并整合", stage.index, side, f, input_val, f + input_val);
                f + input_val
            }
            Sephirah::慈悲 => {
                let weight = stage_float(&stage.params, &["权重", "weight"], 0.7);
                println!("[{:>2}] 慈悲 ({}) fma {} * {} = {} ← 加权融合", stage.index, side, f, weight, f * weight);
                f * weight
            }
            Sephirah::美丽 => {
                println!("[{:>2}] 美丽 ({}) mul.f32 {} * {} = {} ← 哈达玛积", stage.index, side, f, kb_val, f * kb_val);
                f * kb_val
            }
            Sephirah::胜利 => {
                let out = if f >= 0.0 { f } else { 0.0 };
                println!("[{:>2}] 胜利 ({}) 非负验证 {} ≥ 0 → {} ← 情感过滤", stage.index, side, f, out);
                out
            }
            Sephirah::荣耀 => {
                let out = f * 0.5 + input_val;
                println!("[{:>2}] 荣耀 ({}) {} * 0.5 + {} = {} ← 可行性评分", stage.index, side, f, input_val, out);
                out
            }
            Sephirah::基础 => {
                println!("[{:>2}] 基础 ({}) red.reduce.add.f32 = {} ← 全局归约", stage.index, side, f);
                f
            }
            Sephirah::超我 => {
                let out = if f != 0.0 { f * (1.0 / f) } else { 0.0 };
                println!("[{:>2}] 超我 ({}) rcp {} → norm = {} ← LayerNorm", stage.index, side, f, out);
                out
            }
            Sephirah::自我 => {
                println!("[{:>2}] 自我 ({}) dp4a {} * {} = {} ← 自注意力", stage.index, side, f, kb_val, f * kb_val);
                f * kb_val
            }
            Sephirah::真我 => {
                let out = if f != 0.0 { f * (1.0 / (f + 1e-8)) } else { 0.0 };
                println!("[{:>2}] 真我 ({}) 层归一化 {} → {} ← 整合", stage.index, side, f, out);
                out
            }
            Sephirah::逻辑 => {
                let out = f * kb_val + f;
                println!("[{:>2}] 逻辑 ({}) GEMM mad {} * {} + {} = {} ← 矩阵乘", stage.index, side, f, kb_val, f, out);
                out
            }
            Sephirah::共情 => {
                let e = f.exp();
                let out = if e * e != 0.0 { e * (1.0 / (e * e)) } else { 0.0 };
                println!("[{:>2}] 共情 ({}) softmax exp({}) = {} / {} = {} ← 情感归一化", stage.index, side, f, e, e * e, out);
                out
            }
            Sephirah::幸福 => {
                let diff = f - target_val;
                let loss = diff * diff;
                println!("[{:>2}] 幸福 ({}) loss = ({}-{})^2 = {} ← 损失度量", stage.index, side, f, target_val, loss);
                loss
            }
            Sephirah::王国 => {
                println!("[{:>2}] 王国 ({}) st.global.f32 [p_output] = {} ← 写回结果", stage.index, side, f);
                f
            }
        };
    }

    eprintln!("{}", "============================================================".cyan());
    eprintln!("  最终输出 → 王国: {:.6}", f);
    eprintln!("  16质点管道执行完毕 ✅");
    eprintln!("{}", "============================================================".cyan());

    Ok(())
}

/// 从 IR 阶段参数中取浮点值；支持中文与英文键名
fn stage_float(params: &[(String, sephirot_rs::ir::IrValue)], keys: &[&str], default: f32) -> f32 {
    for (k, v) in params {
        if keys.contains(&k.as_str()) {
            match v {
                sephirot_rs::ir::IrValue::Float(f) => return *f as f32,
                sephirot_rs::ir::IrValue::Integer(n) => return *n as f32,
                _ => {}
            }
        }
    }
    default
}
