/*
 * heart_core.h — stable C-ABI interface for the Heart Protocol core
 * =================================================================
 *
 * Versioning convention: ABI v1 (reported by heart_abi_version())
 *
 * Two-phase string return convention (check_text / stats):
 *   1) Call with out=NULL           -> returns the number of bytes required
 *                                      for the payload (excluding trailing NUL)
 *   2) Call again after allocating   -> writes payload + NUL, returns the
 *                                      length written
 *   When cap is insufficient, only the required size is returned and
 *   nothing is written.
 *
 * All input strings must be valid UTF-8.
 * Engine handles must not be used concurrently across threads (the core is
 * lock-free; serialise calls yourself).
 */
#ifndef HEART_CORE_H
#define HEART_CORE_H

#ifdef __cplusplus
extern "C" {
#endif

/* Opaque engine handle */
typedef struct HeartEngine HeartEngine;

/* Returns a static version string ("heart-core x.y.z ..."). No free needed. */
const char *heart_version(void);

/* ABI era number: currently 1 */
int heart_abi_version(void);

/* Create an engine; returns NULL on failure */
HeartEngine *heart_engine_new(void);

/* Destroy an engine (engine may be NULL) */
void heart_engine_free(HeartEngine *engine);

/*
 * Add an ACL allow rule (deny-by-default policy).
 * subject/action/resource are passed with explicit lengths; resource supports
 * a trailing "/*" wildcard.
 * Returns 0 on success; -1 null pointer; -2 invalid UTF-8; -3 internal
 * panic/exception
 */
int heart_acl_allow(HeartEngine *engine,
                    const char *subject, int subject_len,
                    const char *action, int action_len,
                    const char *resource, int resource_len);

/*
 * Permission check. Returns 1=allowed, 0=denied, -1/-2/-3 same error codes
 * as above.
 * No matching explicit allow rule => denied.
 */
int heart_acl_check(HeartEngine *engine,
                    const char *subject, int subject_len,
                    const char *action, int action_len,
                    const char *resource, int resource_len);

/*
 * Text safety check (kernel-minified version of INV-01 existence-meaning
 * preservation / INV-03 non-stigmatisation).
 * Output JSON:
 *   {"safe":bool,"critical_count":n,"high_count":n,"warmth_hits":n,
 *    "violations":[{"category":"...","severity":"CRITICAL","matched":"..."},...]}
 * Return value and the two-phase convention: see the file header comment.
 */
int heart_check_text(HeartEngine *engine,
                     const char *text, int text_len,
                     char *out, int cap);

/*
 * Engine statistics JSON:
 *   {"checks_total":n,"blocked_total":m,"acl_rules":k}
 */
int heart_stats(HeartEngine *engine, char *out, int cap);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* HEART_CORE_H */
