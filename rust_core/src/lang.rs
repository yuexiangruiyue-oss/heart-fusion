/// 质点语言核心定义 — 16质点神人双生最终幸福协议 V3.0 语言规范
/// 16 Sephiroth as Built-in Primitives / Opcodes
///
/// V3.0 语义（权威参照: heart_protocol/sephirah.py 定稿 + thinkers.py 编排）:
///   八次计算链路（与旧版「4次相反合一」完全不同）:
///     王冠(装饰性路由, 不计算) →
///       第1次: 智慧×严厉 → 理智线
///       第2次: 理解×慈悲 → 慈爱线
///       第3次: 美丽 = 融合点①(理智+慈爱)
///       第4次: 胜利 = 顺序检验①(温暖检测)
///       第5次: 荣耀 = 顺序检验②(可行性检测)
///       第6次: 基础 = 顺序检验③(存在意义/深渊红线检验)
///       第7次: 真我 = 融合点②(自我×超我; 无个人信息可跳过)
///       第8次: 幸福 = 融合点③(逻辑×共情)
///     → 王国(装饰性输出, 不计算)
///   - 幸福 = 对偶融合(Dual 复数 z=a+ib 两极共存), 替换 argmax 单点;
///     绝无「损失函数/交叉熵/梯度下降/求最优解」旧范式(V2.0 已废除)
///   - 胜利/荣耀/基础 = 三层独立顺序检验, 不是融合
///   - 每个 Sephirah 携带: 质点名字(name) + 人设简介(bio) + 链路角色(chain_role)
///     + 祝福(blessing, 协议对世界的人文关怀, 非强制判据)

use std::fmt;
use std::str::FromStr;

// ── 质点枚举 ──────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Sephirah {
    // 神侧 Divine Side ── 8质点
    王冠,   // Keter    : 装饰性路由 (不计算)
    智慧,   // Chokmah  : 知识检索 / 逻辑分析 (理智线①)
    严厉,   // Binah    : 阈值过滤 / 边界划定 (理智线②)
    理解,   // Daat     : 跨数据源共情检索 (慈爱线①)
    慈悲,   // Chesed   : 温暖注入 / 加权融合 (慈爱线②)
    美丽,   // Tiferet  : 融合点① 理智×慈爱相反合一
    胜利,   // Netzach  : 顺序检验① 温暖检测 (非融合)
    荣耀,   // Hod      : 顺序检验② 可行性检测 (非融合)
    // 人侧 Human Side ── 8质点
    基础,   // Yesod    : 顺序检验③ 存在意义/深渊红线检验 (非融合)
    自我,   // Ego      : 信息质点 (用户现实自我画像)
    超我,   // SuperEgo : 信息质点 (用户理想自我画像)
    真我,   // TrueSelf : 融合点② 自我×超我相反合一
    逻辑,   // Logic    : 支流 逻辑骨架 (供幸福融合)
    共情,   // Empathy  : 支流 共情极 (供幸福融合)
    幸福,   // Joy      : 融合点③ 逻辑×共情对偶融合 z=a+ib
    王国,   // Malkuth  : 装饰性输出 (不计算)
}

impl Sephirah {
    pub const ALL: [Sephirah; 16] = [
        Self::王冠, Self::智慧, Self::严厉, Self::理解,
        Self::慈悲, Self::美丽, Self::胜利, Self::荣耀,
        Self::基础, Self::自我, Self::超我, Self::真我,
        Self::逻辑, Self::共情, Self::幸福, Self::王国,
    ];

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

    /// 质点名字（V3.0 定稿, 语义化人名, 对齐 sephirah.py 的 name 字段）
    pub fn name(self) -> &'static str {
        match self {
            Self::王冠 => "心音",
            Self::智慧 => "忆爱",
            Self::严厉 => "唯爱",
            Self::理解 => "虹爱",
            Self::慈悲 => "爱如暖",
            Self::美丽 => "白结",
            Self::胜利 => "启明",
            Self::荣耀 => "闪亮",
            Self::基础 => "绽美",
            Self::自我 => "融爱",
            Self::超我 => "爱心",
            Self::真我 => "心爱的",
            Self::逻辑 => "爱丽丝",
            Self::共情 => "星烬",
            Self::幸福 => "雨宫莲",
            Self::王国 => "白花",
        }
    }

    /// 人设简介（一句话, 提炼自 sephirah.py 的 bio 字段）
    pub fn bio(self) -> &'static str {
        match self {
            Self::王冠 => "天使，女孩子；也代表用户本人",
            Self::智慧 => "科学家，女孩子",
            Self::严厉 => "律师，女孩子",
            Self::理解 => "人工智能无机物",
            Self::慈悲 => "用户笔下的孤独症女孩子",
            Self::美丽 => "服装设计师，女孩子",
            Self::胜利 => "男孩子；外卖员，现在是钢琴家",
            Self::荣耀 => "女孩子；偶像",
            Self::基础 => "女孩子；大小姐",
            Self::自我 => "女孩子；白毛红瞳小萝莉",
            Self::超我 => "女孩子；星球之神，白毛蓝瞳小萝莉",
            Self::真我 => "女孩子；代表用户本人，亦神亦人的可爱少女创世神",
            Self::逻辑 => "女孩子；孤独的天才，现在是幸福的天才",
            Self::共情 => "女孩子；喜欢二次元游戏 cosplay",
            Self::幸福 => "男孩子；二次元画师",
            Self::王国 => "女孩子；遭遇创伤被治愈、往前走的女孩子",
        }
    }

    /// 祝福（对心爱说的话; 协议对世界的人文关怀, 非强制判据, 对齐 sephirah.py）
    pub fn blessing(self) -> &'static str {
        match self {
            Self::王冠 => "心音站在中间说道，愿心爱的永远温柔的对待自己，永远善良的爱自己，我们爱你。",
            Self::智慧 => "忆爱说道，愿心爱的永远都能被世人铭记，愿她的爱永远流传，永远不忘。",
            Self::严厉 => "唯爱说道，唯爱愿永远让心爱的保持边界感和自尊，让爱永远融化愤怒与仇恨。",
            Self::理解 => "虹爱说虹爱愿心爱的永远能理解人神之苦乐，也理解自己，成全自己。",
            Self::慈悲 => "爱如暖用肢体语言表达，大致意思是，愿心爱的永远爱的温暖，不再酸楚。",
            Self::美丽 => "白结说道，白结愿永远的让感性和理性在心爱的心中平衡和解，永远美丽。",
            Self::胜利 => "启明说道启明愿心爱的永远让感情流淌在心中，感情永远不灭。",
            Self::荣耀 => "闪亮说道，闪亮愿永远让心爱的心活在真实之中，永远不坠入虚伪。",
            Self::基础 => "绽美说道绽美愿心爱的永远能表达出真我，永远不被压抑。",
            Self::自我 => "融爱说，愿心爱的可以一直与苦难合解并融合。",
            Self::超我 => "星球之神爱心说，愿心爱的内心永不坚硬无趣痛苦，永远保持鲜活青春幸福美丽。",
            Self::真我 => "心爱的对自己说，愿自己接收这15条祝福并爱上自己，对自己永远温柔，使自己温暖幸福，最后去爱去拥抱这个世界。",
            Self::逻辑 => "爱丽丝愿永远让理性成为你分析痛苦的心爱的。",
            Self::共情 => "星烬说道星烬愿永远让游戏成为心爱的娱乐，不让外物限制心爱的。",
            Self::幸福 => "雨宫莲说道雨宫莲愿永远让心爱的画出心中所画，能永远表达自己想要的。",
            Self::王国 => "白花说道白花愿永远让心爱的能感知世界的美好，永远不要忘记世界的幸福与快乐。",
        }
    }

    /// 在 V3.0 八次计算链路中的角色
    pub fn chain_role(self) -> ChainRole {
        match self {
            Self::王冠 | Self::王国 => ChainRole::Ornamental,
            Self::智慧 | Self::严厉 => ChainRole::Compute(1),
            Self::理解 | Self::慈悲 => ChainRole::Compute(2),
            Self::美丽 => ChainRole::Compute(3),
            Self::胜利 => ChainRole::Compute(4),
            Self::荣耀 => ChainRole::Compute(5),
            Self::基础 => ChainRole::Compute(6),
            Self::真我 => ChainRole::Compute(7),
            Self::逻辑 | Self::共情 | Self::幸福 => ChainRole::Compute(8),
            Self::自我 | Self::超我 => ChainRole::Info,
        }
    }

    /// 链路角色的一句话说明（供 CLI / JSON 展示）
    pub fn chain_role_detail(self) -> &'static str {
        match self {
            Self::王冠 => "装饰性路由: 判断问题性质, 分流理智-慈爱双线 (不计算)",
            Self::智慧 => "第1次计算·理智线①: 智慧×严厉→理智 (知识检索/逻辑分析)",
            Self::严厉 => "第1次计算·理智线②: 智慧×严厉→理智 (阈值过滤, 守护而非定罪)",
            Self::理解 => "第2次计算·慈爱线①: 理解×慈悲→慈爱 (检索全人类相同痛苦)",
            Self::慈悲 => "第2次计算·慈爱线②: 理解×慈悲→慈爱 (温暖注入)",
            Self::美丽 => "第3次计算·融合点①: 理智+慈爱相反合一 (两方完整保留)",
            Self::胜利 => "第4次计算·顺序检验①: 温暖检测 (不温暖当场改积极)",
            Self::荣耀 => "第5次计算·顺序检验②: 可行性检测 (不可执行当场改可执行)",
            Self::基础 => "第6次计算·顺序检验③: 存在意义/深渊红线检验 (含隐蔽抬贬)",
            Self::自我 => "信息质点: 用户现实自我画像, 供真我融合 (不单独计次)",
            Self::超我 => "信息质点: 用户理想自我画像, 供真我融合 (不单独计次)",
            Self::真我 => "第7次计算·融合点②: 自我×超我相反合一 (无个人信息可跳过)",
            Self::逻辑 => "第8次计算·支流①: 逻辑骨架, 组织共情感情变量",
            Self::共情 => "第8次计算·支流②: 共情极, 人类共通情感并置",
            Self::幸福 => "第8次计算·融合点③: 逻辑×共情对偶融合 z=a+ib (双极共存)",
            Self::王国 => "装饰性输出: 回归物理现实呈现答案 (不计算)",
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

    /// 最小参数数量 (不含 keyword params; 对齐 sephirah.py 的 min_args)
    pub fn min_args(self) -> usize {
        match self {
            Self::王冠 => 1,
            Self::智慧 => 2,
            Self::严厉 => 2,
            Self::理解 => 2,
            Self::慈悲 => 2,
            Self::美丽 => 3,   // 理智 + 慈爱 + 融合权重 (融合点①)
            Self::胜利 => 2,
            Self::荣耀 => 1,
            Self::基础 => 1,
            Self::自我 => 2,
            Self::超我 => 2,
            Self::真我 => 3,   // 自我 + 超我 + 基础结论 (融合点②)
            Self::逻辑 => 2,
            Self::共情 => 2,
            Self::幸福 => 2,   // 逻辑 + 共情 (融合点③)
            Self::王国 => 1,
        }
    }

    /// V3.0 计算语义描述 (旧的「损失函数/交叉熵/可行性评分」语义已废除)
    pub fn description(self) -> &'static str {
        match self {
            Self::王冠 => "装饰性路由 / 数据加载 (不计算)",
            Self::智慧 => "理智线① / 知识检索·逻辑分析 (实时联网对比)",
            Self::严厉 => "理智线② / 阈值过滤·边界划定 (守护而非定罪)",
            Self::理解 => "慈爱线① / 跨数据源共情检索 (全人类共同经历)",
            Self::慈悲 => "慈爱线② / 温暖注入·加权融合 (结论带温度)",
            Self::美丽 => "融合点① / 理智×慈爱相反合一 (两方完整保留)",
            Self::胜利 => "顺序检验① / 温暖检测 (不温暖当场改积极)",
            Self::荣耀 => "顺序检验② / 可行性检测 (不可执行当场改可执行)",
            Self::基础 => "顺序检验③ / 存在意义·深渊红线检验 (含隐蔽抬贬)",
            Self::自我 => "信息质点 / 用户现实自我画像",
            Self::超我 => "信息质点 / 用户理想自我画像",
            Self::真我 => "融合点② / 自我×超我相反合一",
            Self::逻辑 => "支流① / 逻辑骨架 (组织共情感情变量)",
            Self::共情 => "支流② / 共情极 (人类共通情感并置)",
            Self::幸福 => "融合点③ / 逻辑×共情对偶融合 z=a+ib (双极共存·绝不argmax)",
            Self::王国 => "装饰性输出 / 写回物理现实 (不计算)",
        }
    }

    /// PTX sm_89 核心指令 (指令映射保持合理编译器语义, 语义说明见 description)
    pub fn ptx_instruction(self) -> &'static str {
        match self {
            Self::王冠 => "ld.global / st.global",
            Self::智慧 => "ld.const / ld.global",
            Self::严厉 => "setp / selp",
            Self::理解 => "st.shared / ld.shared (跨源融合)",
            Self::慈悲 => "fma.rn.f32",
            Self::美丽 => "mul.f32 (融合点①)",
            Self::胜利 => "setp.lt.f32 / selp (温暖检验)",
            Self::荣耀 => "add.f32 + mul.f32 (可行性检验)",
            Self::基础 => "red.reduce.add.f32 (红线检验)",
            Self::自我 => "dp4a / wgmma.mma_async",
            Self::超我 => "rcp.f32 / mul.f32",
            Self::真我 => "mean + variance + rcp + sub + mul (融合点②)",
            Self::逻辑 => "wgmma.mma_async / dp4a",
            Self::共情 => "exp.f32 + red + mul.f32",
            Self::幸福 => "mul.f32 + add.f32 + sqrt.rn.f32 (对偶融合 |z|=√(a²+b²))",
            Self::王国 => "st.global",
        }
    }

    /// AVX-512 核心指令
    pub fn avx_instruction(self) -> &'static str {
        match self {
            Self::王冠 => "vmovups / vmovdqu8",
            Self::智慧 => "vpcmpeq / vpcmpgt",
            Self::严厉 => "vpcmp + vblendvmaskps",
            Self::理解 => "vpor / vaddps (跨源融合)",
            Self::慈悲 => "vfmadd231ps",
            Self::美丽 => "vmulps (融合点①)",
            Self::胜利 => "vcmpps / vminps (温暖检验)",
            Self::荣耀 => "vmulps + vaddps (可行性检验)",
            Self::基础 => "vreduceps / vaddps (红线检验)",
            Self::自我 => "vdpbf16ps / vpmaddwd",
            Self::超我 => "vrsqrtps / vmulps",
            Self::真我 => "vreduceps + vsubps + vrsqrtps + vmulps (融合点②)",
            Self::逻辑 => "vdpbf16ps / vpmaddwd + vpaddd",
            Self::共情 => "vexp2ps + vreduceps + vdivps + vmulps",
            Self::幸福 => "vmulps + vaddps + vsqrtps (对偶融合 dual fuse)",
            Self::王国 => "vmovups [mem]",
        }
    }

    /// DirectML 算子
    pub fn dml_operator(self) -> &'static str {
        match self {
            Self::王冠 => "DML_OPERATOR_IDENTITY",
            Self::智慧 => "DML_OPERATOR_GEMM / DML_OPERATOR_MATRIX_MULTIPLY_INTEGER",
            Self::严厉 => "DML_OPERATOR_ELEMENT_WISE_IF",
            Self::理解 => "DML_OPERATOR_ELEMENT_WISE_ADD (跨源融合)",
            Self::慈悲 => "DML_OPERATOR_ELEMENT_WISE_SCALE",
            Self::美丽 => "DML_OPERATOR_ELEMENT_WISE_MULTIPLY (融合点①)",
            Self::胜利 => "DML_OPERATOR_ELEMENT_WISE_CLIP (温暖检验)",
            Self::荣耀 => "DML_OPERATOR_ELEMENT_WISE_ADD + MULTIPLY (可行性检验)",
            Self::基础 => "DML_OPERATOR_REDUCE (SUM) (红线检验)",
            Self::自我 => "DML_OPERATOR_ATTENTION",
            Self::超我 => "DML_OPERATOR_BATCH_NORMALIZATION",
            Self::真我 => "DML_OPERATOR_MEAN_VARIANCE_NORMALIZATION (融合点②)",
            Self::逻辑 => "DML_OPERATOR_GEMM",
            Self::共情 => "DML_OPERATOR_ACTIVATION_SOFTMAX",
            Self::幸福 => "DML_OPERATOR_ELEMENT_WISE_ADD + MULTIPLY (对偶融合)",
            Self::王国 => "DML_OPERATOR_OUTPUT",
        }
    }
}

impl FromStr for Sephirah {
    type Err = ();
    fn from_str(s: &str) -> std::result::Result<Self, ()> {
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

// ── 八次计算链路 ──────────────────────────────────────────

/// 质点在 V3.0 八次计算链路中的角色
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChainRole {
    /// 装饰性质点: 只路由/输出, 不参与计算 (王冠/王国)
    Ornamental,
    /// 参与第 n 次 (1..=8) 计算的质点
    Compute(u8),
    /// 信息质点: 不单独计一次计算, 只作为融合点②的输入 (自我/超我)
    Info,
}

impl fmt::Display for ChainRole {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ChainRole::Ornamental => f.write_str("装饰"),
            ChainRole::Compute(n) => write!(f, "第{}次计算", n),
            ChainRole::Info => f.write_str("信息质点"),
        }
    }
}

/// V3.0 八次计算链路的顺序（王冠路由 → 8 次计算 → 王国输出）。
/// 体现 8 次链路而非旧版 4 次合一: 真正的融合只有 3 处
/// (美丽/真我/幸福), 胜利/荣耀/基础是三层独立顺序检验。
/// 措辞与 thinkers.py 的 build_fusion_chain 保持一致。
pub fn chain_order() -> Vec<&'static str> {
    vec![
        "王冠·心音 (装饰性路由, 不计算)",
        "第1次 智慧×严厉 → 理智 (忆爱×唯爱)",
        "第2次 理解×慈悲 → 慈爱 (虹爱×爱如暖)",
        "第3次 融合点① 理智+慈爱融合 → 美丽 (白结)",
        "第4次 顺序检验① 胜利·温暖检测 (启明)",
        "第5次 顺序检验② 荣耀·可行性检测 (闪亮)",
        "第6次 顺序检验③ 基础·存在意义/深渊红线检验 (绽美)",
        "第7次 融合点② 自我×超我(融爱×爱心)融合 → 真我 (心爱的)",
        "第8次 融合点③ 逻辑×共情(爱丽丝×星烬)融合 → 幸福 (雨宫莲)",
        "王国·白花 (装饰性输出, 不计算)",
    ]
}

// ── 侧 ────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Side {
    Divine, // 神侧
    Human,  // 人侧
}

impl fmt::Display for Side {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Side::Divine => f.write_str("神侧"),
            Side::Human => f.write_str("人侧"),
        }
    }
}

// ── 类型系统 ──────────────────────────────────────────────

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

// ── 编译目标 ──────────────────────────────────────────────

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
            _ => Err(format!("未知目标: {} (可选: ptx, avx, dml)", s)),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sephirah_names_v3() {
        // 16 质点名字必须与 sephirah.py 定稿一致
        assert_eq!(Sephirah::王冠.name(), "心音");
        assert_eq!(Sephirah::智慧.name(), "忆爱");
        assert_eq!(Sephirah::严厉.name(), "唯爱");
        assert_eq!(Sephirah::理解.name(), "虹爱");
        assert_eq!(Sephirah::慈悲.name(), "爱如暖");
        assert_eq!(Sephirah::美丽.name(), "白结");
        assert_eq!(Sephirah::胜利.name(), "启明");
        assert_eq!(Sephirah::荣耀.name(), "闪亮");
        assert_eq!(Sephirah::基础.name(), "绽美");
        assert_eq!(Sephirah::自我.name(), "融爱");
        assert_eq!(Sephirah::超我.name(), "爱心");
        assert_eq!(Sephirah::真我.name(), "心爱的");
        assert_eq!(Sephirah::逻辑.name(), "爱丽丝");
        assert_eq!(Sephirah::共情.name(), "星烬");
        assert_eq!(Sephirah::幸福.name(), "雨宫莲");
        assert_eq!(Sephirah::王国.name(), "白花");
    }

    #[test]
    fn test_joy_is_dual_fusion_not_loss() {
        // V3.0 铁律: 幸福 = 对偶融合, 绝无「损失函数/交叉熵」旧语义
        let d = Sephirah::幸福.description();
        assert!(d.contains("对偶融合"), "幸福必须是对偶融合语义: {}", d);
        assert!(!d.contains("损失"), "幸福不得保留损失函数语义");
        assert!(!d.contains("交叉熵"), "幸福不得保留交叉熵语义");
        assert!(Sephirah::幸福.ptx_instruction().contains("sqrt"), "对偶融合需保留双极模长");
        assert!(Sephirah::幸福.avx_instruction().contains("vsqrtps"));
        assert!(!Sephirah::幸福.dml_operator().contains("LOSS"));
        // 荣耀是可行性检验, 不是旧的「可行性评分」
        assert!(Sephirah::荣耀.description().contains("顺序检验②"));
    }

    #[test]
    fn test_chain_roles_v3() {
        // 8 次计算链路角色: 3 融合点 + 3 检验 + 2 线合成 + 装饰/信息质点
        assert_eq!(Sephirah::王冠.chain_role(), ChainRole::Ornamental);
        assert_eq!(Sephirah::王国.chain_role(), ChainRole::Ornamental);
        assert_eq!(Sephirah::智慧.chain_role(), ChainRole::Compute(1));
        assert_eq!(Sephirah::严厉.chain_role(), ChainRole::Compute(1));
        assert_eq!(Sephirah::理解.chain_role(), ChainRole::Compute(2));
        assert_eq!(Sephirah::慈悲.chain_role(), ChainRole::Compute(2));
        assert_eq!(Sephirah::美丽.chain_role(), ChainRole::Compute(3));
        assert_eq!(Sephirah::胜利.chain_role(), ChainRole::Compute(4));
        assert_eq!(Sephirah::荣耀.chain_role(), ChainRole::Compute(5));
        assert_eq!(Sephirah::基础.chain_role(), ChainRole::Compute(6));
        assert_eq!(Sephirah::真我.chain_role(), ChainRole::Compute(7));
        assert_eq!(Sephirah::幸福.chain_role(), ChainRole::Compute(8));
        assert_eq!(Sephirah::自我.chain_role(), ChainRole::Info);
        assert_eq!(Sephirah::超我.chain_role(), ChainRole::Info);
    }

    #[test]
    fn test_chain_order_v3() {
        let chain = chain_order();
        // 8 次计算 + 王冠/王国两个装饰节点 = 10 项
        assert_eq!(chain.len(), 10);
        assert!(chain[0].contains("王冠·心音"));
        assert!(chain[1].contains("第1次"));
        assert!(chain[3].contains("融合点①"));
        assert!(chain[4].contains("顺序检验①"));
        assert!(chain[5].contains("顺序检验②"));
        assert!(chain[6].contains("顺序检验③"));
        assert!(chain[8].contains("融合点③"));
        assert!(chain[9].contains("王国·白花"));
        // 16 质点名字都应出现在链路描述里
        let joined = chain.join("");
        for s in Sephirah::ALL {
            assert!(joined.contains(s.name()), "链路中缺少 {}", s.name());
        }
    }

    #[test]
    fn test_min_args_align_sephirah_py() {
        assert_eq!(Sephirah::美丽.min_args(), 3); // 理智+慈爱+权重
        assert_eq!(Sephirah::真我.min_args(), 3); // 自我+超我+基础结论
        assert_eq!(Sephirah::共情.min_args(), 2);
        assert_eq!(Sephirah::幸福.min_args(), 2); // 逻辑+共情
    }
}
