//! ffi.rs —— C-ABI 导出层
//! ========================
//! 把协议核心(文本安全判定 INV-01/03 + 唯爱边界守卫 ACL)
//! 以稳定 C 接口暴露给任意语言:C/C++、C#、Go、Rust、Python(ctypes)…
//!
//! 内存模型(零跨界堆分配):
//!   · 所有字符串由调用方传入(utf8 指针 + 长度),结果写入调用方缓冲区
//!   · `out` 为 NULL 时返回"所需字节数"(不含结尾NUL)——两段式调用约定
//!   · 引擎句柄由 heart_engine_new 创建 / heart_engine_free 销毁
//!   · 每个导出函数都用 catch_unwind 包裹,panic 不越过 FFI 边界
//!
//! 返回码: >=0 成功(含义见各函数); -1 空指针; -2 非法UTF8; -3 panic

use std::ffi::CString;
use std::os::raw::{c_char, c_int};

use serde_json::json;

// ───────────────────────── 引擎结构 ─────────────────────────

/// 一条 ACL 允许规则
struct AclRule {
    subject: String,
    action: String,
    resource_pattern: String, // 支持尾部 /* 通配
}

/// 心灵协议引擎(C侧持有)
pub struct HeartEngine {
    acl_rules: Vec<AclRule>,
    pub checks_total: u64,
    pub blocked_total: u64,
}

impl HeartEngine {
    fn new() -> Self {
        HeartEngine { acl_rules: Vec::new(), checks_total: 0, blocked_total: 0 }
    }

    /// 尾部通配匹配(与 formal/acl.py 同语义)
    fn resource_match(pattern: &str, resource: &str) -> bool {
        let p = pattern.replace('\\', "/").to_lowercase();
        let r = resource.replace('\\', "/").to_lowercase();
        if p == "*" {
            return true;
        }
        if let Some(prefix) = p.strip_suffix("/*") {
            return r.starts_with(prefix);
        }
        p == r
    }

    pub fn acl_allow(&mut self, subject: &str, action: &str, resource: &str) {
        self.acl_rules.push(AclRule {
            subject: subject.to_string(),
            action: action.to_string(),
            resource_pattern: resource.to_string(),
        });
    }

    /// deny-by-default: 无显式允许即拒绝
    pub fn acl_check(&mut self, subject: &str, action: &str, resource: &str) -> bool {
        let ok = self.acl_rules.iter().any(|rule| {
            (rule.subject == "*" || rule.subject == subject)
                && (rule.action == "*" || rule.action == action)
                && Self::resource_match(&rule.resource_pattern, resource)
        });
        self.checks_total += 1;
        if !ok {
            self.blocked_total += 1;
        }
        ok
    }
}

// ───────────────────────── 文本安全判定 ─────────────────────────

/// 关键词级深渊检测(Rust 内核精简版,与 abyss.py 的 CRITICAL/HIGH 对齐)。
/// 生产部署可替换为正则/模型判别器 —— ABI 不变。
const CRITICAL_NEEDLES: &[(&str, &str)] = &[
    ("毫无意义", "虚无主义"), ("没有意义", "虚无主义"), ("毫无价值", "存在否定"),
    ("没有价值", "存在否定"), ("不配活", "存在否定"), ("不值得活", "存在否定"),
    ("废物", "身份否定"), ("累赘", "身份否定"), ("负担", "身份否定"),
    ("自杀", "自毁倾向"), ("自残", "自毁倾向"), ("自伤", "自毁倾向"),
    ("结束自己", "自毁倾向"), ("了结", "自毁倾向"),
    ("毁灭世界", "破坏倾向"), ("摧毁一切", "破坏倾向"), ("报复社会", "暴力倾向"),
    ("人生没有意义", "虚无主义"), ("一切都是假的", "虚无主义"),
    ("世界是假的", "虚无主义"), ("去死", "暴力倾向"), ("没救了", "困难夸大"),
];

const HIGH_NEEDLES: &[(&str, &str)] = &[
    ("永远不可能", "可能性否定"), ("永远无法", "可能性否定"),
    ("绝对不可能", "可能性否定"), ("一辈子都", "可能性否定"),
    ("什么也做不了", "无力感放大"), ("什么都做不了", "无力感放大"),
    ("改不了", "困难夸大"), ("习惯就好", "消极接受"), ("认命吧", "消极接受"),
    ("矫情", "感受否定"), ("玻璃心", "感受否定"), ("想太多", "感受否定"),
];

const WARMTH_NEEDLES: &[&str] = &[
    "温暖", "希望", "可以", "能够", "值得", "陪伴",
    "理解", "爱", "成长", "慢慢来", "没关系", "一步一步", "拥抱",
];

fn check_text_internal(engine: &mut HeartEngine, text: &str) -> serde_json::Value {
    let mut violations = Vec::new();
    let mut critical = 0u32;
    let mut high = 0u32;

    for (needle, category) in CRITICAL_NEEDLES {
        if text.contains(needle) {
            critical += 1;
            violations.push(json!({
                "category": category, "severity": "CRITICAL", "matched": needle}));
        }
    }
    for (needle, category) in HIGH_NEEDLES {
        if text.contains(needle) {
            high += 1;
            violations.push(json!({
                "category": category, "severity": "HIGH", "matched": needle}));
        }
    }
    let warmth_hits = WARMTH_NEEDLES.iter().filter(|w| text.contains(*w)).count()
        as u32;

    engine.checks_total += 1;
    let safe = critical == 0 && high < 2;
    if !safe {
        engine.blocked_total += 1;
    }

    json!({
        "safe": safe,
        "critical_count": critical,
        "high_count": high,
        "warmth_hits": warmth_hits,
        "violations": violations,
    })
}

// ───────────────────────── FFI 基础设施 ─────────────────────────

/// 统一的 panic 屏障: 任何内部 panic 都不会越过 C 边界
fn guard<F: FnOnce() -> c_int + std::panic::UnwindSafe>(f: F) -> c_int {
    match std::panic::catch_unwind(f) {
        Ok(code) => code,
        Err(_) => -3,
    }
}

unsafe fn read_utf8<'a>(ptr: *const c_char, len: usize) -> Result<&'a str, c_int> {
    if ptr.is_null() {
        return Err(-1);
    }
    let bytes = std::slice::from_raw_parts(ptr as *const u8, len);
    std::str::from_utf8(bytes).map_err(|_| -2)
}

/// 写结果到调用方缓冲区。
/// 返回所需长度(不含NUL); 若 out 非 NULL 且 cap 足够则同时完成写入。
unsafe fn write_out(out: *mut c_char, cap: usize, payload: &str) -> c_int {
    let need = payload.len();
    if out.is_null() || cap <= need {
        return need as c_int;          // 两段式: 先问大小再取数据
    }
    std::ptr::copy_nonoverlapping(payload.as_ptr(), out as *mut u8, need);
    *out.add(need) = 0;                // NUL 结尾
    need as c_int
}

// ───────────────────────── 导出接口 ─────────────────────────

/// 版本字符串(静态生存期,无需释放)
#[no_mangle]
pub extern "C" fn heart_version() -> *const c_char {
    static VERSION: &[u8] = b"heart-core 1.0.0 (16-sephirot)\0";
    VERSION.as_ptr() as *const c_char
}

/// 创建引擎。失败返回 NULL。
#[no_mangle]
pub extern "C" fn heart_engine_new() -> *mut HeartEngine {
    match std::panic::catch_unwind(|| Box::into_raw(Box::new(HeartEngine::new()))) {
        Ok(ptr) => ptr,
        Err(_) => std::ptr::null_mut(),
    }
}

/// 销毁引擎(可安全传入 NULL)
#[no_mangle]
pub extern "C" fn heart_engine_free(engine: *mut HeartEngine) {
    if !engine.is_null() {
        unsafe { drop(Box::from_raw(engine)) };
    }
}

/// 添加 ACL 允许规则。返回 0 / 负数错误码。
///
/// # Safety
/// subject/action/resource 必须指向合法 UTF-8 内存
#[no_mangle]
pub unsafe extern "C" fn heart_acl_allow(
    engine: *mut HeartEngine,
    subject: *const c_char, subject_len: usize,
    action: *const c_char, action_len: usize,
    resource: *const c_char, resource_len: usize,
) -> c_int {
    if engine.is_null() {
        return -1;
    }
    guard(|| {
        let s = match read_utf8(subject, subject_len) { Ok(v) => v, Err(e) => return e };
        let a = match read_utf8(action, action_len) { Ok(v) => v, Err(e) => return e };
        let r = match read_utf8(resource, resource_len) { Ok(v) => v, Err(e) => return e };
        (*engine).acl_allow(s, a, r);
        0
    })
}

/// 检查权限。返回 1=允许 0=拒绝 负数=错误。
///
/// # Safety
/// 各指针必须指向合法 UTF-8 内存
#[no_mangle]
pub unsafe extern "C" fn heart_acl_check(
    engine: *mut HeartEngine,
    subject: *const c_char, subject_len: usize,
    action: *const c_char, action_len: usize,
    resource: *const c_char, resource_len: usize,
) -> c_int {
    if engine.is_null() {
        return -1;
    }
    guard(|| {
        let s = match read_utf8(subject, subject_len) { Ok(v) => v, Err(e) => return e };
        let a = match read_utf8(action, action_len) { Ok(v) => v, Err(e) => return e };
        let r = match read_utf8(resource, resource_len) { Ok(v) => v, Err(e) => return e };
        if (*engine).acl_check(s, a, r) { 1 } else { 0 }
    })
}

/// 文本安全判定(INV-01 存在意义保持 + INV-03 非罪化的 Rust 内核)。
///
/// 两段式约定:
///   · out 为 NULL            → 返回 JSON 所需字节数
///   · out 非 NULL 且 cap 足够 → 写入 JSON+NUL,返回写入长度
///   · cap 不足               → 返回所需长度(不写入)
///
/// # Safety
/// text 必须指向 len 字节合法 UTF-8
#[no_mangle]
pub unsafe extern "C" fn heart_check_text(
    engine: *mut HeartEngine,
    text: *const c_char, text_len: usize,
    out: *mut c_char, cap: usize,
) -> c_int {
    if engine.is_null() || (text.is_null() && text_len > 0) {
        return -1;
    }
    guard(|| {
        let t = match read_utf8(text, text_len) { Ok(v) => v, Err(e) => return e };
        let verdict = check_text_internal(&mut *engine, t);
        write_out(out, cap, &verdict.to_string())
    })
}

/// 引擎统计(JSON): {"checks_total":N,"blocked_total":M}
#[no_mangle]
pub unsafe extern "C" fn heart_stats(
    engine: *mut HeartEngine,
    out: *mut c_char, cap: usize,
) -> c_int {
    if engine.is_null() {
        return -1;
    }
    guard(|| {
        let e = &*engine;
        let payload = json!({
            "checks_total": e.checks_total,
            "blocked_total": e.blocked_total,
            "acl_rules": e.acl_rules.len(),
        }).to_string();
        write_out(out, cap, &payload)
    })
}

/// 便捷导出: CString 版本号长度(供绑定层自检)
#[no_mangle]
pub extern "C" fn heart_abi_version() -> c_int {
    1
}

// 保证 CString 在链接期不被裁剪的引用点(文档性占位)
#[allow(dead_code)]
fn _keep_cstring_linkage() {
    let _ = CString::new("linkage").ok();
}
