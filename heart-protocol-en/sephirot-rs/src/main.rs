/// SephirotLang Compiler - CLI entry point
/// The universal compiler for the 16-Sephiroth Twin-Heart Protocol

// The library crate has been renamed to heart_core (same name as the C-ABI);
// the old path is kept here for compatibility
extern crate heart_core as sephirot_rs;

use clap::{Parser as ClapParser, Subcommand};
use colored::*;
use std::fs;
use std::path::Path;

use sephirot_rs::{compile, check, CompileTarget, Sephirah};

// ── Windows UTF-8 terminal ────────────────────────────────
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

// ── CLI definition ────────────────────────────────────────

#[derive(ClapParser)]
#[command(name = "sephirot")]
#[command(version = "1.0.0")]
#[command(about = "16-Sephiroth Twin-Heart Protocol - the universal SephirotLang compiler")]
#[command(long_about = "SephirotLang Compiler v1.0\n16 Sephiroth Built-in Primitives → PTX sm_89 / AVX-512 / DirectML")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Compile a .sephirot source file to target code
    Compile {
        /// Path to the source file (.sephirot)
        input: String,

        /// Compilation target: ptx / avx / dml
        #[arg(short, long, default_value = "ptx")]
        target: String,

        /// Output file path (auto-derived by default)
        #[arg(short, long)]
        out: Option<String>,

        /// Print to the terminal (do not write a file)
        #[arg(long)]
        stdout: bool,
    },

    /// Check the syntax and semantics of a source file
    Check {
        /// Path to the source file
        input: String,
    },

    /// Compile and run inline source code
    Run {
        /// Inline source code
        source: Vec<String>,

        /// Compilation target
        #[arg(short, long, default_value = "ptx")]
        target: String,
    },

    /// List the 16 sephirot opcodes
    Vocab,

    /// Interactive REPL
    Repl,

    /// Simulate the PTX pipeline on the CPU (no CUDA required)
    Simulate {
        /// Path to the source file (.sephirot)
        input: String,

        /// Input values (comma-separated: input,kb,target)
        #[arg(short, long, default_value = "1.0,2.5,0.9")]
        values: String,
    },
}

// ── Main function ─────────────────────────────────────────

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

// ── Command implementations ───────────────────────────────

fn cmd_compile(input: &str, target: &str, out: Option<&str>, to_stdout: bool) -> sephirot_rs::Result<()> {
    let source = fs::read_to_string(input)
        .map_err(|e| sephirot_rs::CompileError::Io(e))?;

    let compile_target: CompileTarget = target.parse()
        .map_err(|e| sephirot_rs::CompileError::Codegen { msg: e })?;

    eprintln!("{}", "╔══════════════════════════════════════════════════╗".dimmed());
    eprintln!("{}", "║   SephirotLang Compiler v1.0                    ║".cyan());
    eprintln!("{}", "║   16-Sephiroth Twin-Heart Protocol → GPU Code   ║".cyan());
    eprintln!("{}", "╚══════════════════════════════════════════════════╝".dimmed());
    eprintln!("{}", format!("  Source: {}", input).dimmed());
    eprintln!("{}", format!("  Target: {}", compile_target).dimmed());
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
        eprintln!("{}", "  ✅ Compilation succeeded".green().bold());
        eprintln!("{}", format!("  Output: {}", output_path).green());
        eprintln!("{}", format!("  Size: {} bytes", code.len()).dimmed());
    }

    Ok(())
}

fn cmd_check(input: &str) -> sephirot_rs::Result<()> {
    let source = fs::read_to_string(input)
        .map_err(|e| sephirot_rs::CompileError::Io(e))?;

    match check(&source) {
        Ok(ast) => {
            let decl_count = ast.decls.len();
            eprintln!("{}", "✅ Check passed".green().bold());
            eprintln!("{}", format!("  Declarations: {}", decl_count).dimmed());
            for decl in &ast.decls {
                match decl {
                    sephirot_rs::parser::Decl::Data(d) => {
                        eprintln!("  {} {} : {}", "data".yellow(), d.name, d.ty);
                    }
                    sephirot_rs::parser::Decl::Const(c) => {
                        eprintln!("  {} {}", "const".yellow(), c.name);
                    }
                    sephirot_rs::parser::Decl::Pipeline(p) => {
                        eprintln!("  {} {} ({} stages)", "pipeline".yellow(), p.name, p.stages.len());
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

    eprintln!("{}", format!("═ Compiling inline source → {} ═", compile_target).cyan());
    eprintln!();

    let code = compile(source, compile_target)?;
    println!("{}", code);
    Ok(())
}

fn cmd_vocab() -> sephirot_rs::Result<()> {
    println!("\n{}", "══════════════════════════════════════════════════".cyan());
    println!("{}", "  16-Sephiroth Twin-Heart Protocol — Built-in Core Opcodes".cyan());
    println!("{}", "══════════════════════════════════════════════════".cyan());
    println!();

    for (i, op) in Sephirah::ALL.iter().enumerate() {
        let side_str = match op.side() {
            sephirot_rs::Side::Divine => "Divine".magenta(),
            sephirot_rs::Side::Human => "Human".blue(),
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
    eprintln!("\n{}", "═══ SephirotLang REPL ═══".cyan());
    eprintln!("{}", "Enter source to compile, or :help for commands, :exit to quit".dimmed());
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

        // Internal commands
        if trimmed == ":exit" || trimmed == ":q" {
            eprintln!("{}", "Goodbye".dimmed());
            break;
        }
        if trimmed == ":help" {
            eprintln!("  :ptx      switch to PTX target");
            eprintln!("  :avx      switch to AVX-512 target");
            eprintln!("  :dml      switch to DirectML target");
            eprintln!("  :vocab    list the 16 sephirot opcodes");
            eprintln!("  :check    check syntax");
            eprintln!("  :exit     quit");
            continue;
        }
        if trimmed == ":ptx" {
            current_target = CompileTarget::Ptx;
            eprintln!("{}", "Target: PTX sm_89".green());
            continue;
        }
        if trimmed == ":avx" {
            current_target = CompileTarget::Avx;
            eprintln!("{}", "Target: AVX-512".green());
            continue;
        }
        if trimmed == ":dml" {
            current_target = CompileTarget::Dml;
            eprintln!("{}", "Target: DirectML".green());
            continue;
        }
        if trimmed == ":vocab" {
            cmd_vocab()?;
            continue;
        }

        // Multi-line input (pipeline declarations span lines)
        if trimmed.ends_with(':') || trimmed.ends_with('|') || in_block {
            line_buf.push_str(trimmed);
            line_buf.push('\n');
            in_block = true;
            continue;
        }

        line_buf.push_str(trimmed);

        // Compile
        if trimmed == ":check" {
            match check(&line_buf) {
                Ok(_) => eprintln!("{}", "✅ Syntax OK".green()),
                Err(e) => eprintln!("{}", e.to_string().red()),
            }
        } else {
            match compile(&line_buf, current_target) {
                Ok(code) => {
                    eprintln!("{}", "─── Compilation output ───".cyan());
                    println!("{}", code);
                    eprintln!("{}", "─── End ───".cyan());
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

    // Parse the input parameters
    let v: Vec<f64> = values.split(',')
        .filter_map(|s| s.trim().parse::<f64>().ok())
        .collect();
    let input_val = v.get(0).copied().unwrap_or(1.0) as f32;
    let kb_val    = v.get(1).copied().unwrap_or(2.5) as f32;
    let target_val= v.get(2).copied().unwrap_or(0.9) as f32;

    // Lex, parse and semantically check, then build the IR
    let ast = check(&source)?;
    let ir = sephirot_rs::ir::build_ir(&ast)?;

    eprintln!("\n{}", "============================================================".cyan());
    eprintln!("{}", "  SephirotLang — PTX pipeline CPU simulation".cyan());
    eprintln!("{}", "  16-Sephiroth Twin-Heart Protocol → RTX 4050 sm_89 simulation".cyan());
    eprintln!("{}", "============================================================".cyan());
    eprintln!("  Input: {}, Knowledge base: {}, Target: {}", input_val, kb_val, target_val);
    eprintln!("{}", "------------------------------------------------------------".dimmed());

    if ir.pipelines.is_empty() {
        eprintln!("{}", "  Error: the source file declares no pipelines".red());
        return Err(sephirot_rs::CompileError::Semantic {
            line: 0,
            msg: "missing pipeline declaration".into(),
        });
    }

    // Run the first pipeline declared in the source file
    // (real parsing of the .sephirot content, not a fixed 16-step sequence)
    let pipeline = &ir.pipelines[0];
    eprintln!("{}", format!("  Pipeline: {} ({} sephirot stages)", pipeline.name, pipeline.stages.len()).cyan());
    eprintln!("{}", "------------------------------------------------------------".dimmed());

    // Chained data-flow register: the previous stage's output is the next stage's input
    let mut f = input_val;

    for stage in &pipeline.stages {
        let side = match stage.side {
            sephirot_rs::Side::Divine => "Divine",
            sephirot_rs::Side::Human => "Human",
        };
        f = match stage.opcode {
            Sephirah::王冠 => {
                println!("[{:>2}] 王冠 ({}) identity: {} ← load input", stage.index, side, f);
                f
            }
            Sephirah::智慧 => {
                println!("[{:>2}] 智慧 ({}) mul.f32 {} * {} = {} ← knowledge retrieval", stage.index, side, f, kb_val, f * kb_val);
                f * kb_val
            }
            Sephirah::严厉 => {
                let threshold = stage_float(&stage.params, &["阈值", "threshold"], 0.8);
                let out = if f < threshold { 0.0 } else { f };
                println!("[{:>2}] 严厉 ({}) setp {} < {} → {} ← threshold filter", stage.index, side, f, threshold, out);
                out
            }
            Sephirah::理解 => {
                println!("[{:>2}] 理解 ({}) add.f32 {} + {} = {} ← merge/integrate", stage.index, side, f, input_val, f + input_val);
                f + input_val
            }
            Sephirah::慈悲 => {
                let weight = stage_float(&stage.params, &["权重", "weight"], 0.7);
                println!("[{:>2}] 慈悲 ({}) fma {} * {} = {} ← weighted blend", stage.index, side, f, weight, f * weight);
                f * weight
            }
            Sephirah::美丽 => {
                println!("[{:>2}] 美丽 ({}) mul.f32 {} * {} = {} ← Hadamard product", stage.index, side, f, kb_val, f * kb_val);
                f * kb_val
            }
            Sephirah::胜利 => {
                let out = if f >= 0.0 { f } else { 0.0 };
                println!("[{:>2}] 胜利 ({}) non-negative check {} ≥ 0 → {} ← sentiment filter", stage.index, side, f, out);
                out
            }
            Sephirah::荣耀 => {
                let out = f * 0.5 + input_val;
                println!("[{:>2}] 荣耀 ({}) {} * 0.5 + {} = {} ← balance reading", stage.index, side, f, input_val, out);
                out
            }
            Sephirah::基础 => {
                println!("[{:>2}] 基础 ({}) red.reduce.add.f32 = {} ← global reduction", stage.index, side, f);
                f
            }
            Sephirah::超我 => {
                let out = if f != 0.0 { f * (1.0 / f) } else { 0.0 };
                println!("[{:>2}] 超我 ({}) rcp {} → norm = {} ← LayerNorm", stage.index, side, f, out);
                out
            }
            Sephirah::自我 => {
                println!("[{:>2}] 自我 ({}) dp4a {} * {} = {} ← self-attention", stage.index, side, f, kb_val, f * kb_val);
                f * kb_val
            }
            Sephirah::真我 => {
                let out = if f != 0.0 { f * (1.0 / (f + 1e-8)) } else { 0.0 };
                println!("[{:>2}] 真我 ({}) layer-norm {} → {} ← integration", stage.index, side, f, out);
                out
            }
            Sephirah::逻辑 => {
                let out = f * kb_val + f;
                println!("[{:>2}] 逻辑 ({}) GEMM mad {} * {} + {} = {} ← matrix multiply", stage.index, side, f, kb_val, f, out);
                out
            }
            Sephirah::共情 => {
                let e = f.exp();
                let out = if e * e != 0.0 { e * (1.0 / (e * e)) } else { 0.0 };
                println!("[{:>2}] 共情 ({}) softmax exp({}) = {} / {} = {} ← sentiment normalization", stage.index, side, f, e, e * e, out);
                out
            }
            Sephirah::幸福 => {
                let a = f;
                let b = target_val;
                let modulus = (a * a + b * b).sqrt();
                let phase = b.atan2(a);
                let balance = (1.0 - (phase - std::f32::consts::FRAC_PI_4).abs() / std::f32::consts::FRAC_PI_4).max(0.0);
                let fused = modulus * balance;
                println!("[{:>2}] 幸福 ({}) fuse({},{}) |z|={:.4} balance={:.4} ← opposite unification", stage.index, side, a, b, modulus, balance);
                fused
            }
            Sephirah::王国 => {
                println!("[{:>2}] 王国 ({}) st.global.f32 [p_output] = {} ← write-back result", stage.index, side, f);
                f
            }
        };
    }

    eprintln!("{}", "============================================================".cyan());
    // "王国" (Malkuth) is the final stage name; kept verbatim as runtime data
    eprintln!("  Final output → 王国: {:.6}", f);
    eprintln!("  16-sephirot pipeline execution complete ✅");
    eprintln!("{}", "============================================================".cyan());

    Ok(())
}

/// Read a float value from the IR stage parameters; supports both Chinese and English key names
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
