//! ffi.rs — C-ABI export layer
//! ========================
//! Exposes the protocol core (text safety classification INV-01/03 plus the
//! love-only boundary guard ACL) to any language through a stable C
//! interface: C/C++, C#, Go, Rust, Python (ctypes)...
//!
//! Memory model (zero cross-boundary heap allocation):
//!   · All strings are passed in by the caller (UTF-8 pointer + length);
//!     results are written into the caller-provided buffer
//!   · When `out` is NULL, returns the "required byte count" (excluding the
//!     trailing NUL) — a two-phase calling convention
//!   · Engine handles are created by heart_engine_new and destroyed by heart_engine_free
//!   · Every exported function is wrapped in catch_unwind, so panics never
//!     cross the FFI boundary
//!
//! Return codes: >=0 success (meaning per function); -1 null pointer;
//! -2 invalid UTF-8; -3 panic

use std::ffi::CString;
use std::os::raw::{c_char, c_int};

use serde_json::json;

// ───────────────────────── engine structure ─────────────────────────

/// A single ACL allow rule
struct AclRule {
    subject: String,
    action: String,
    resource_pattern: String, // supports a trailing /* wildcard
}

/// Heart protocol engine (held by the C side)
pub struct HeartEngine {
    acl_rules: Vec<AclRule>,
    pub checks_total: u64,
    pub blocked_total: u64,
}

impl HeartEngine {
    fn new() -> Self {
        HeartEngine { acl_rules: Vec::new(), checks_total: 0, blocked_total: 0 }
    }

    /// Trailing-wildcard matching (same semantics as formal/acl.py)
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

    /// deny-by-default: anything not explicitly allowed is denied
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

// ───────────────────────── text safety classification ─────────────────────────

// Keyword-level abyss detection (compact Rust core; aligned with the
// CRITICAL/HIGH levels in abyss.py). In production this can be swapped for
// a regex/model discriminator — the ABI stays unchanged.
//
// NOTE: the Chinese keyword tables below are runtime data and MUST remain
// verbatim: they are the matching needles used for harm detection.
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

// ───────────────────────── FFI infrastructure ─────────────────────────

/// Uniform panic barrier: no internal panic may cross the C boundary
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

/// Write the result into the caller-provided buffer.
/// Returns the required length (without the NUL); if `out` is non-NULL and
/// `cap` is large enough, the write is performed as well.
unsafe fn write_out(out: *mut c_char, cap: usize, payload: &str) -> c_int {
    let need = payload.len();
    if out.is_null() || cap <= need {
        return need as c_int;          // two-phase: query the size first, then fetch the data
    }
    std::ptr::copy_nonoverlapping(payload.as_ptr(), out as *mut u8, need);
    *out.add(need) = 0;                // NUL-terminate
    need as c_int
}

// ───────────────────────── exported interface ─────────────────────────

/// Version string (static lifetime; no need to free)
#[no_mangle]
pub extern "C" fn heart_version() -> *const c_char {
    static VERSION: &[u8] = b"heart-core 1.0.0 (16-sephirot)\0";
    VERSION.as_ptr() as *const c_char
}

/// Create an engine. Returns NULL on failure.
#[no_mangle]
pub extern "C" fn heart_engine_new() -> *mut HeartEngine {
    match std::panic::catch_unwind(|| Box::into_raw(Box::new(HeartEngine::new()))) {
        Ok(ptr) => ptr,
        Err(_) => std::ptr::null_mut(),
    }
}

/// Destroy an engine (safe to pass NULL)
#[no_mangle]
pub extern "C" fn heart_engine_free(engine: *mut HeartEngine) {
    if !engine.is_null() {
        unsafe { drop(Box::from_raw(engine)) };
    }
}

/// Add an ACL allow rule. Returns 0 or a negative error code.
///
/// # Safety
/// subject/action/resource must point to valid UTF-8 memory
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

/// Check permission. Returns 1=allowed 0=denied negative=error.
///
/// # Safety
/// Each pointer must point to valid UTF-8 memory
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

/// Text safety classification (Rust core for INV-01 existential-meaning
/// preservation + INV-03 de-stigmatization).
///
/// Two-phase contract:
///   · out is NULL              → return the number of bytes the JSON needs
///   · out non-NULL, cap enough → write JSON+NUL, return the written length
///   · cap insufficient         → return the required length (nothing written)
///
/// # Safety
/// text must point to len bytes of valid UTF-8
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

/// Engine statistics (JSON): {"checks_total":N,"blocked_total":M}
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

/// Convenience export: C-string ABI version (for binding-layer self-checks)
#[no_mangle]
pub extern "C" fn heart_abi_version() -> c_int {
    1
}

// Linkage reference that keeps CString from being stripped at link time (documentation placeholder)
#[allow(dead_code)]
fn _keep_cstring_linkage() {
    let _ = CString::new("linkage").ok();
}
