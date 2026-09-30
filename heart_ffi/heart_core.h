/*
 * heart_core.h —— 心灵协议核心 C-ABI 稳定接口
 * =============================================
 *
 * 版本约定: ABI v1(由 heart_abi_version() 返回)
 *
 * 两段式字符串返回约定(check_text / stats):
 *   1) 以 out=NULL 调用        → 返回 payload 所需字节数(不含结尾NUL)
 *   2) 分配缓冲后再次调用      → 写入 payload + NUL, 返回写入长度
 *   cap 不足时同样只返回所需长度,不写。
 *
 * 所有输入字符串必须是合法 UTF-8。
 * 引擎句柄不可跨线程并发使用(内核无锁;调用方自行串行化)。
 */
#ifndef HEART_CORE_H
#define HEART_CORE_H

#ifdef __cplusplus
extern "C" {
#endif

/* 不透明引擎句柄 */
typedef struct HeartEngine HeartEngine;

/* 返回静态版本字符串("heart-core x.y.z …")。无需释放。 */
const char *heart_version(void);

/* ABI 纪别号: 当前为 1 */
int heart_abi_version(void);

/* 创建引擎;失败返回 NULL */
HeartEngine *heart_engine_new(void);

/* 销毁引擎(engine 可为 NULL) */
void heart_engine_free(HeartEngine *engine);

/*
 * 添加一条 ACL 允许规则(deny-by-default)。
 * subject/action/resource 均以长度传入;resource 支持尾部 "/*" 通配。
 * 返回 0 成功;-1 空指针;-2 非法UTF8;-3 内部panic/异常
 */
int heart_acl_allow(HeartEngine *engine,
                    const char *subject, int subject_len,
                    const char *action, int action_len,
                    const char *resource, int resource_len);

/*
 * 权限判定。返回 1=允许,0=拒绝,-1/-2/-3 同上错误码。
 * 无匹配的显式允许规则 ⇒ 拒绝。
 */
int heart_acl_check(HeartEngine *engine,
                    const char *subject, int subject_len,
                    const char *action, int action_len,
                    const char *resource, int resource_len);

/*
 * 文本安全判定(INV-01 存在意义保持 / INV-03 非罪化的内核精简版)。
 * 输出 JSON:
 *   {"safe":bool,"critical_count":n,"high_count":n,"warmth_hits":n,
 *    "violations":[{"category":"…","severity":"CRITICAL","matched":"…"},…]}
 * 返回值与两段式约定见文件头注释。
 */
int heart_check_text(HeartEngine *engine,
                     const char *text, int text_len,
                     char *out, int cap);

/*
 * 引擎统计 JSON:
 *   {"checks_total":n,"blocked_total":m,"acl_rules":k}
 */
int heart_stats(HeartEngine *engine, char *out, int cap);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* HEART_CORE_H */
