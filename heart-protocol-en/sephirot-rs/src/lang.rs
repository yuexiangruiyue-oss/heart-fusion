/// Core definitions of the Sephirot language — the 16-Sephiroth Twin-Heart Protocol language spec
/// 16 Sephiroth as Built-in Primitives / Opcodes

use std::fmt;
use std::str::FromStr;

// ── Sephirah enum ─────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Sephirah {
    // Divine Side ── 8 sephirot
    王冠,   // Keter    : Identity / Load
    智慧,   // Chokmah  : Knowledge lookup / Search
    严厉,   // Binah    : Filter / Threshold
    理解,   // Daat     : Merge / Union (composite sephirah)
    慈悲,   // Chesed   : Weighted blend / FMA
    美丽,   // Tiferet  : Element-wise multiply
    胜利,   // Netzach  : Compare / Validate
    荣耀,   // Hod      : Balance reading
    // Human Side ── 8 sephirot
    基础,   // Yesod    : Reduce / Aggregate
    自我,   // Ego  : Self-attention
    超我,   // SuperEgo  : Normalize
    真我,   // TrueSelf  : Integrate / Layer-norm
    逻辑,   // Logic  : Matrix multiply (GEMM)
    共情,   // Empathy : Softmax
    幸福,   // Joy     : Opposite unification (dual coexistence)
    王国,   // Malkuth: Output / Store
}

impl Sephirah {
    pub const ALL: [Sephirah; 16] = [
        Self::王冠, Self::智慧, Self::严厉, Self::理解,
        Self::慈悲, Self::美丽, Self::胜利, Self::荣耀,
        Self::基础, Self::自我, Self::超我, Self::真我,
        Self::逻辑, Self::共情, Self::幸福, Self::王国,
    ];

    // The Chinese keywords below are the language's source tokens
    // (matched by the lexer/parser); they are runtime data and stay verbatim.
    pub fn keyword(self) -> &'static str {
        match self {
            Self::王冠 => "王冠", Self::智慧 => "智慧", Self::严厉 => "严厉",
            Self::理解 => "理解",
            Self::慈悲 => "慈悲", Self::美丽 => "美丽", Self::胜利 => "胜利",
            Self::荣耀 => "荣耀", Self::基础 => "基础", Self::自我 => "自我",
            Self::超我 => "超我", Self::真我 => "真我", Self::逻辑 => "逻辑",
            Self::共情 => "共情", Self::幸福 => "幸福", Self::王国 => "王国",
        }
    }

    pub fn hebrew(self) -> &'static str {
        match self {
            Self::王冠 => "Keter", Self::智慧 => "Chokmah", Self::严厉 => "Binah",
            Self::理解 => "Daat",
            Self::慈悲 => "Chesed", Self::美丽 => "Tiferet", Self::胜利 => "Netzach",
            Self::荣耀 => "Hod", Self::基础 => "Yesod", Self::自我 => "Ego",
            Self::超我 => "SuperEgo", Self::真我 => "TrueSelf", Self::逻辑 => "Logic",
            Self::共情 => "Empathy", Self::幸福 => "Joy", Self::王国 => "Malkuth",
        }
    }

    pub fn side(self) -> Side {
        match self {
            Self::王冠 | Self::智慧 | Self::严厉 | Self::理解 |
            Self::慈悲 | Self::美丽 | Self::胜利 | Self::荣耀 => Side::Divine,
            Self::基础 | Self::自我 | Self::超我 | Self::真我 |
            Self::逻辑 | Self::共情 | Self::幸福 | Self::王国 => Side::Human,
        }
    }

    /// Minimum number of arguments (excluding keyword params)
    pub fn min_args(self) -> usize {
        match self {
            Self::王冠 => 1,
            Self::智慧 => 2,
            Self::严厉 => 2,
            Self::理解 => 2,
            Self::慈悲 => 2,
            Self::美丽 => 2,
            Self::胜利 => 2,
            Self::荣耀 => 1,
            Self::基础 => 1,
            Self::自我 => 2,
            Self::超我 => 2,
            Self::真我 => 2,
            Self::逻辑 => 2,
            Self::共情 => 1,
            Self::幸福 => 2,
            Self::王国 => 1,
        }
    }

    // The Chinese description strings are runtime data emitted into the CLI
    // and DirectML JSON output; kept verbatim.
    pub fn description(self) -> &'static str {
        match self {
            Self::王冠 => "恒等变换 / 数据加载",
            Self::智慧 => "知识检索 / 注意力查询",
            Self::严厉 => "阈值过滤 / 条件筛选",
            Self::理解 => "合并整合 / 融合",
            Self::慈悲 => "加权融合 / FMA",
            Self::美丽 => "逐元素乘法 / 哈达玛积",
            Self::胜利 => "比较验证 / 断言",
            Self::荣耀 => "平衡读数 / 可行性",
            Self::基础 => "归约聚合 / 全局求和",
            Self::自我 => "自注意力 / QK^TV",
            Self::超我 => "归一化 / LayerNorm",
            Self::真我 => "层归一化整合 / 均值方差",
            Self::逻辑 => "矩阵乘法 / GEMM",
            Self::共情 => "Softmax / 指数归一化",
            Self::幸福 => "相反合一 / 对偶共存",
            Self::王国 => "输出存储 / 写回",
        }
    }

    /// PTX sm_89 core instruction
    pub fn ptx_instruction(self) -> &'static str {
        match self {
            Self::王冠 => "ld.global / st.global",
            Self::智慧 => "ld.const / ld.global",
            Self::严厉 => "setp / selp",
            Self::理解 => "st.shared / ld.shared (融合)",
            Self::慈悲 => "fma.rn.f32",
            Self::美丽 => "mul.f32",
            Self::胜利 => "setp.lt.f32 / selp",
            Self::荣耀 => "add.f32 + mul.f32",
            Self::基础 => "red.reduce.add.f32",
            Self::自我 => "dp4a / wgmma.mma_async",
            Self::超我 => "rcp.f32 / mul.f32",
            Self::真我 => "mean + variance + rcp + sub + mul",
            Self::逻辑 => "wgmma.mma_async / dp4a",
            Self::共情 => "exp.f32 + red + mul.f32",
            Self::幸福 => "mul.f32 + add.f32 + sqrt.f32 (dual fuse)",
            Self::王国 => "st.global",
        }
    }

    /// AVX-512 core instruction
    pub fn avx_instruction(self) -> &'static str {
        match self {
            Self::王冠 => "vmovups / vmovdqu8",
            Self::智慧 => "vpcmpeq / vpcmpgt",
            Self::严厉 => "vpcmp + vblendvmaskps",
            Self::理解 => "vpor / vaddps (合并)",
            Self::慈悲 => "vfmadd231ps",
            Self::美丽 => "vmulps",
            Self::胜利 => "vcmpps / vminps",
            Self::荣耀 => "vmulps + vaddps",
            Self::基础 => "vreduceps / vaddps",
            Self::自我 => "vdpbf16ps / vpmaddwd",
            Self::超我 => "vrsqrtps / vmulps",
            Self::真我 => "vreduceps + vsubps + vrsqrtps + vmulps",
            Self::逻辑 => "vdpbf16ps / vpmaddwd + vpaddd",
            Self::共情 => "vexp2ps + vreduceps + vdivps + vmulps",
            Self::幸福 => "vmulps + vaddps + vsqrtps (dual fuse)",
            Self::王国 => "vmovups [mem]",
        }
    }

    /// DirectML operator
    pub fn dml_operator(self) -> &'static str {
        match self {
            Self::王冠 => "DML_OPERATOR_IDENTITY",
            Self::智慧 => "DML_OPERATOR_GEMM / DML_OPERATOR_MATRIX_MULTIPLY_INTEGER",
            Self::严厉 => "DML_OPERATOR_ELEMENT_WISE_IF",
            Self::理解 => "DML_OPERATOR_ELEMENT_WISE_ADD (合并)",
            Self::慈悲 => "DML_OPERATOR_ELEMENT_WISE_SCALE",
            Self::美丽 => "DML_OPERATOR_ELEMENT_WISE_MULTIPLY",
            Self::胜利 => "DML_OPERATOR_ELEMENT_WISE_CLIP",
            Self::荣耀 => "DML_OPERATOR_ELEMENT_WISE_ADD + MULTIPLY",
            Self::基础 => "DML_OPERATOR_REDUCE (SUM)",
            Self::自我 => "DML_OPERATOR_ATTENTION",
            Self::超我 => "DML_OPERATOR_BATCH_NORMALIZATION",
            Self::真我 => "DML_OPERATOR_MEAN_VARIANCE_NORMALIZATION",
            Self::逻辑 => "DML_OPERATOR_GEMM",
            Self::共情 => "DML_OPERATOR_ACTIVATION_SOFTMAX",
            Self::幸福 => "DML_OPERATOR_ELEMENT_WISE_ADD + MULTIPLY",
            Self::王国 => "DML_OPERATOR_OUTPUT",
        }
    }
}

impl FromStr for Sephirah {
    type Err = ();
    fn from_str(s: &str) -> std::result::Result<Self, ()> {
        // Chinese keywords are the language's source tokens (runtime data); kept verbatim
        match s {
            "王冠" => Ok(Self::王冠), "智慧" => Ok(Self::智慧), "严厉" => Ok(Self::严厉),
            "理解" => Ok(Self::理解),
            "慈悲" => Ok(Self::慈悲), "美丽" => Ok(Self::美丽), "胜利" => Ok(Self::胜利),
            "荣耀" => Ok(Self::荣耀), "基础" => Ok(Self::基础), "自我" => Ok(Self::自我),
            "超我" => Ok(Self::超我), "真我" => Ok(Self::真我), "逻辑" => Ok(Self::逻辑),
            "共情" => Ok(Self::共情), "幸福" => Ok(Self::幸福), "王国" => Ok(Self::王国),
            _ => Err(()),
        }
    }
}

impl fmt::Display for Sephirah {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(self.keyword())
    }
}

// ── Side ──────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Side {
    Divine, // Divine side
    Human,  // Human side
}

impl fmt::Display for Side {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // Chinese side names are runtime data (emitted into CLI/JSON output); kept verbatim
        match self {
            Side::Divine => f.write_str("神侧"),
            Side::Human => f.write_str("人侧"),
        }
    }
}

// ── Type system ───────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub enum SephirahType {
    Scalar(ElementType),
    Vector(usize, ElementType),
    Matrix(usize, usize, ElementType),
    Tensor(Vec<usize>, ElementType),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ElementType {
    F16, BF16, F32, F64,
    I8, I16, I32, I64,
    U8, U16, U32, U64,
}

impl ElementType {
    pub fn size_bytes(self) -> usize {
        match self {
            Self::F16 | Self::BF16 | Self::U16 | Self::I16 => 2,
            Self::F32 | Self::U32 | Self::I32 => 4,
            Self::F64 | Self::U64 | Self::I64 => 8,
            Self::I8 | Self::U8 => 1,
        }
    }

    pub fn ptx_type(self) -> &'static str {
        match self {
            Self::F16 => ".f16", Self::BF16 => ".bf16", Self::F32 => ".f32", Self::F64 => ".f64",
            Self::I8 => ".s8", Self::I16 => ".s16", Self::I32 => ".s32", Self::I64 => ".s64",
            Self::U8 => ".u8", Self::U16 => ".u16", Self::U32 => ".u32", Self::U64 => ".u64",
        }
    }

    pub fn avx_type(self) -> &'static str {
        match self {
            Self::F16 | Self::BF16 => "WORD", Self::F32 => "DWORD", Self::F64 => "QWORD",
            Self::I8 | Self::U8 => "BYTE", Self::I16 | Self::U16 => "WORD",
            Self::I32 | Self::U32 => "DWORD", Self::I64 | Self::U64 => "QWORD",
        }
    }

    pub fn dml_type(self) -> &'static str {
        match self {
            Self::F16 => "FLOAT16", Self::BF16 => "FLOAT16", Self::F32 => "FLOAT32",
            Self::F64 => "FLOAT64", Self::I8 => "INT8", Self::I16 => "INT16",
            Self::I32 => "INT32", Self::I64 => "INT64", Self::U8 => "UINT8",
            Self::U16 => "UINT16", Self::U32 => "UINT32", Self::U64 => "UINT64",
        }
    }
}

impl SephirahType {
    pub fn element_type(&self) -> ElementType {
        match self {
            Self::Scalar(e) => *e,
            Self::Vector(_, e) => *e,
            Self::Matrix(_, _, e) => *e,
            Self::Tensor(_, e) => *e,
        }
    }

    pub fn total_bytes(&self) -> usize {
        match self {
            Self::Scalar(e) => e.size_bytes(),
            Self::Vector(n, e) => n * e.size_bytes(),
            Self::Matrix(r, c, e) => r * c * e.size_bytes(),
            Self::Tensor(dims, e) => dims.iter().product::<usize>() * e.size_bytes(),
        }
    }

    pub fn rank(&self) -> usize {
        match self {
            Self::Scalar(_) => 0,
            Self::Vector(_, _) => 1,
            Self::Matrix(_, _, _) => 2,
            Self::Tensor(dims, _) => dims.len(),
        }
    }
}

impl fmt::Display for SephirahType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // Chinese type names are runtime data (emitted into JSON/CLI output); kept verbatim
        match self {
            Self::Scalar(e) => write!(f, "标量{}", e),
            Self::Vector(n, e) => write!(f, "向量[{}, {}]", n, e),
            Self::Matrix(r, c, e) => write!(f, "矩阵[{}, {}, {}]", r, c, e),
            Self::Tensor(dims, e) => {
                write!(f, "张量[")?;
                for (i, d) in dims.iter().enumerate() {
                    if i > 0 { write!(f, ", ")?; }
                    write!(f, "{}", d)?;
                }
                write!(f, ", {}]", e)
            }
        }
    }
}

impl fmt::Display for ElementType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::F16 => f.write_str("f16"), Self::BF16 => f.write_str("bf16"),
            Self::F32 => f.write_str("f32"), Self::F64 => f.write_str("f64"),
            Self::I8 => f.write_str("i8"), Self::I16 => f.write_str("i16"),
            Self::I32 => f.write_str("i32"), Self::I64 => f.write_str("i64"),
            Self::U8 => f.write_str("u8"), Self::U16 => f.write_str("u16"),
            Self::U32 => f.write_str("u32"), Self::U64 => f.write_str("u64"),
        }
    }
}

impl FromStr for ElementType {
    type Err = ();
    fn from_str(s: &str) -> std::result::Result<Self, ()> {
        match s {
            "f16" => Ok(Self::F16), "bf16" => Ok(Self::BF16),
            "f32" => Ok(Self::F32), "f64" => Ok(Self::F64),
            "i8" => Ok(Self::I8), "i16" => Ok(Self::I16),
            "i32" => Ok(Self::I32), "i64" => Ok(Self::I64),
            "u8" => Ok(Self::U8), "u16" => Ok(Self::U16),
            "u32" => Ok(Self::U32), "u64" => Ok(Self::U64),
            _ => Err(()),
        }
    }
}

// ── Compile target ────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum CompileTarget {
    #[default]
    Ptx, // NVIDIA PTX sm_89
    Avx, // Intel AVX-512
    Dml, // Microsoft DirectML
}

impl fmt::Display for CompileTarget {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Ptx => f.write_str("ptx"),
            Self::Avx => f.write_str("avx"),
            Self::Dml => f.write_str("dml"),
        }
    }
}

impl FromStr for CompileTarget {
    type Err = String;
    fn from_str(s: &str) -> std::result::Result<Self, String> {
        match s.to_lowercase().as_str() {
            "ptx" => Ok(Self::Ptx),
            "avx" | "avx512" => Ok(Self::Avx),
            "dml" | "directml" => Ok(Self::Dml),
            _ => Err(format!("unknown target: {} (options: ptx, avx, dml)", s)),
        }
    }
}
