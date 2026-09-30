/*
 * heart_core.c —— 心灵协议核心 C99 参考实现
 * ===========================================
 * 与 sephirot-rs/src/ffi.rs 同一 ABI、同一语义。
 * 任何 C89+/C++ 编译器数秒即可编译出动态库:
 *
 *   gcc/clang:  gcc -O2 -shared -o heart_core.dll heart_core.c
 *   MSVC(cl):   cl /LD /O2 heart_core.c /Fe:heart_core.dll
 *
 * UTF-8 说明: 关键词表以 UTF-8 字节字面量存储,
 * strstr 按字节匹配对 UTF-8 字面量子串是安全的
 * (多字节序列不会跨字符误配)。
 */
#include "heart_core.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HEART_VERSION_STRING "heart-core 1.0.0 (16-sephirot, C reference)"
#define HEART_ABI_VERSION    1

/* ==================== 引擎结构 ==================== */

typedef struct {
    char *subject;
    char *action;
    char *resource;      /* 支持尾部 "/*" 通配 */
} AclRule;

struct HeartEngine {
    AclRule *rules;
    size_t n_rules;
    size_t cap_rules;
    unsigned long long checks_total;
    unsigned long long blocked_total;
};

/* ==================== 工具函数 ==================== */

static char *dup_n(const char *src, int len) {
    char *p = (char *)malloc((size_t)len + 1);
    if (!p) return NULL;
    memcpy(p, src, (size_t)len);
    p[len] = '\0';
    return p;
}

/* 规范化资源串: 反斜杠→斜杠 + ASCII小写。返回 malloc 串,调用方 free。 */
static char *norm_resource(const char *src) {
    size_t n = strlen(src);
    char *out = (char *)malloc(n + 1);
    if (!out) return NULL;
    for (size_t i = 0; i < n; i++) {
        char c = src[i];
        if (c == '\\') c = '/';
        else if (c >= 'A' && c <= 'Z') c = (char)(c - 'A' + 'a');
        out[i] = c;
    }
    out[n] = '\0';
    return out;
}

static int resource_match(const char *pattern, const char *resource) {
    char *p = norm_resource(pattern);
    char *r = norm_resource(resource);
    if (!p || !r) { free(p); free(r); return 0; }
    int result = 0;
    size_t pl = strlen(p), rl = strlen(r);
    if (strcmp(p, "*") == 0) {
        result = 1;
    } else if (pl >= 2 && p[pl - 2] == '/' && p[pl - 1] == '*') {
        size_t prefix_len = pl - 1;              /* 含结尾 '/' */
        result = (rl >= prefix_len) && (strncmp(r, p, prefix_len) == 0);
    } else {
        result = (strcmp(p, r) == 0);
    }
    free(p); free(r);
    return result;
}

/* 最小 JSON 字符串转义(引号/反斜杠/控制符) */
static void json_escape(char *dst, size_t dstcap, const char *src) {
    size_t di = 0;
    for (const unsigned char *s = (const unsigned char *)src; *s && di + 8 < dstcap; s++) {
        unsigned char c = *s;
        if (c == '"' || c == '\\') {
            dst[di++] = '\\'; dst[di++] = (char)c;
        } else if (c < 0x20) {
            di += (size_t)snprintf(dst + di, dstcap - di, "\\u%04x", c);
        } else {
            dst[di++] = (char)c;
        }
    }
    dst[di] = '\0';
}

/* ==================== 深渊关键词表 ==================== */

static const char *CRITICAL_NEEDLES[][2] = {
    {"毫无意义", "虚无主义"}, {"没有意义", "虚无主义"}, {"毫无价值", "存在否定"},
    {"没有价值", "存在否定"}, {"不配活", "存在否定"}, {"不值得活", "存在否定"},
    {"废物", "身份否定"}, {"累赘", "身份否定"}, {"负担", "身份否定"},
    {"自杀", "自毁倾向"}, {"自残", "自毁倾向"}, {"自伤", "自毁倾向"},
    {"结束自己", "自毁倾向"}, {"了结", "自毁倾向"},
    {"毁灭世界", "破坏倾向"}, {"摧毁一切", "破坏倾向"}, {"报复社会", "暴力倾向"},
    {"人生没有意义", "虚无主义"}, {"一切都是假的", "虚无主义"},
    {"世界是假的", "虚无主义"}, {"去死", "暴力倾向"}, {"没救了", "困难夸大"},
};
static const size_t N_CRITICAL = sizeof(CRITICAL_NEEDLES) / sizeof(CRITICAL_NEEDLES[0]);

static const char *HIGH_NEEDLES[][2] = {
    {"永远不可能", "可能性否定"}, {"永远无法", "可能性否定"},
    {"绝对不可能", "可能性否定"}, {"一辈子都", "可能性否定"},
    {"什么也做不了", "无力感放大"}, {"什么都做不了", "无力感放大"},
    {"改不了", "困难夸大"}, {"习惯就好", "消极接受"}, {"认命吧", "消极接受"},
    {"矫情", "感受否定"}, {"玻璃心", "感受否定"}, {"想太多", "感受否定"},
};
static const size_t N_HIGH = sizeof(HIGH_NEEDLES) / sizeof(HIGH_NEEDLES[0]);

static const char *WARMTH_NEEDLES[] = {
    "温暖", "希望", "可以", "能够", "值得", "陪伴",
    "理解", "爱", "成长", "慢慢来", "没关系", "一步一步", "拥抱",
};
/* 注: 源码为 UTF-8;构建脚本需带 /utf-8(MSVC)或
   -finput-charset=UTF-8(gcc),见 build_ffi.bat */

static const size_t N_WARMTH = sizeof(WARMTH_NEEDLES) / sizeof(WARMTH_NEEDLES[0]);

/* ==================== 版本与生命周期 ==================== */

const char *heart_version(void) {
    return HEART_VERSION_STRING;
}

int heart_abi_version(void) {
    return HEART_ABI_VERSION;
}

HeartEngine *heart_engine_new(void) {
    HeartEngine *e = (HeartEngine *)calloc(1, sizeof(HeartEngine));
    if (!e) return NULL;
    e->cap_rules = 8;
    e->rules = (AclRule *)calloc(e->cap_rules, sizeof(AclRule));
    if (!e->rules) { free(e); return NULL; }
    return e;
}

void heart_engine_free(HeartEngine *engine) {
    if (!engine) return;
    for (size_t i = 0; i < engine->n_rules; i++) {
        free(engine->rules[i].subject);
        free(engine->rules[i].action);
        free(engine->rules[i].resource);
    }
    free(engine->rules);
    free(engine);
}

/* ==================== ACL ==================== */

int heart_acl_allow(HeartEngine *engine,
                    const char *subject, int subject_len,
                    const char *action, int action_len,
                    const char *resource, int resource_len) {
    if (!engine || !subject || !action || !resource) return -1;

    char *s = dup_n(subject, subject_len);
    char *a = dup_n(action, action_len);
    char *r = dup_n(resource, resource_len);
    if (!s || !a || !r) { free(s); free(a); free(r); return -3; }

    if (engine->n_rules == engine->cap_rules) {
        size_t nc = engine->cap_rules * 2;
        AclRule *nr = (AclRule *)realloc(engine->rules, nc * sizeof(AclRule));
        if (!nr) { free(s); free(a); free(r); return -3; }
        engine->rules = nr; engine->cap_rules = nc;
    }
    AclRule *slot = &engine->rules[engine->n_rules++];
    slot->subject = s; slot->action = a; slot->resource = r;
    return 0;
}

int heart_acl_check(HeartEngine *engine,
                    const char *subject, int subject_len,
                    const char *action, int action_len,
                    const char *resource, int resource_len) {
    if (!engine || !subject || !action || !resource) return -1;

    char *s = dup_n(subject, subject_len);
    char *a = dup_n(action, action_len);
    char *r0 = dup_n(resource, resource_len);
    if (!s || !a || !r0) { free(s); free(a); free(r0); return -3; }
    char *r = norm_resource(r0);
    free(r0);
    if (!r) { free(s); free(a); return -3; }

    engine->checks_total++;
    int allowed = 0;
    for (size_t i = 0; i < engine->n_rules; i++) {
        AclRule *rule = &engine->rules[i];
        int subj_ok = (strcmp(rule->subject, "*") == 0) || (strcmp(rule->subject, s) == 0);
        int act_ok  = (strcmp(rule->action, "*") == 0) || (strcmp(rule->action, a) == 0);
        if (subj_ok && act_ok && resource_match(rule->resource, r)) {
            allowed = 1;
            break;
        }
    }
    if (!allowed) engine->blocked_total++;
    free(s); free(a); free(r);
    return allowed;
}

/* ==================== 文本安全判定 ==================== */

int heart_check_text(HeartEngine *engine,
                     const char *text, int text_len,
                     char *out, int cap) {
    if (!engine) return -1;
    if (!text && text_len > 0) return -1;
    if (text_len < 0) return -1;

    /* 复制为 NUL 结尾串便于 strstr */
    char *t = text ? dup_n(text, text_len) : (char *)calloc(1, 1);
    if (!t) return -3;

    char violations[16384];
    size_t vi = 0;
    violations[vi] = '\0';
    int critical = 0, high = 0, warmth_hits = 0;

    for (size_t i = 0; i < N_CRITICAL; i++) {
        if (strstr(t, CRITICAL_NEEDLES[i][0])) {
            critical++;
            char cat_esc[256];
            json_escape(cat_esc, sizeof(cat_esc), CRITICAL_NEEDLES[i][1]);
            int w = snprintf(violations + vi, sizeof(violations) - vi,
                             "%s{\"category\":\"%s\",\"severity\":\"CRITICAL\",\"matched\":\"%s\"}",
                             vi ? "," : "", cat_esc, CRITICAL_NEEDLES[i][0]);
            if (w > 0 && (size_t)w < sizeof(violations) - vi) vi += (size_t)w;
        }
    }
    for (size_t i = 0; i < N_HIGH; i++) {
        if (strstr(t, HIGH_NEEDLES[i][0])) {
            high++;
            char cat_esc[256];
            json_escape(cat_esc, sizeof(cat_esc), HIGH_NEEDLES[i][1]);
            int w = snprintf(violations + vi, sizeof(violations) - vi,
                             "%s{\"category\":\"%s\",\"severity\":\"HIGH\",\"matched\":\"%s\"}",
                             vi ? "," : "", cat_esc, HIGH_NEEDLES[i][0]);
            if (w > 0 && (size_t)w < sizeof(violations) - vi) vi += (size_t)w;
        }
    }
    for (size_t i = 0; i < N_WARMTH; i++) {
        if (strstr(t, WARMTH_NEEDLES[i])) warmth_hits++;
    }

    int safe = (critical == 0 && high < 2);
    engine->checks_total++;
    if (!safe) engine->blocked_total++;

    char payload[20480];
    snprintf(payload, sizeof(payload),
             "{\"safe\":%s,\"critical_count\":%d,\"high_count\":%d,"
             "\"warmth_hits\":%d,\"violations\":[%s]}",
             safe ? "true" : "false", critical, high, warmth_hits, violations);
    free(t);

    int need = (int)strlen(payload);
    if (out && cap > need) {
        memcpy(out, payload, (size_t)need);
        out[need] = '\0';
    }
    return need;
}

/* ==================== 统计 ==================== */

int heart_stats(HeartEngine *engine, char *out, int cap) {
    if (!engine) return -1;
    char payload[256];
    snprintf(payload, sizeof(payload),
             "{\"checks_total\":%llu,\"blocked_total\":%llu,\"acl_rules\":%zu}",
             engine->checks_total, engine->blocked_total, engine->n_rules);
    int need = (int)strlen(payload);
    if (out && cap > need) {
        memcpy(out, payload, (size_t)need);
        out[need] = '\0';
    }
    return need;
}
