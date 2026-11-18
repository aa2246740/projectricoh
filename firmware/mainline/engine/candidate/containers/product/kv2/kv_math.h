#ifndef KV_MATH_H
#define KV_MATH_H
#include <stdint.h>

enum { KV_BYTES=552, KV_Q=4096, KV_PARAMS=10 };
enum { KV_CONTRAST,KV_HIGHLIGHT,KV_SHADOW,KV_FADE,KV_SATURATION,
       KV_WARMTH,KV_TINT,KV_SPLIT,KV_FILTER,KV_TONE };
typedef struct {
    int32_t amount;
    int32_t dose[KV_PARAMS];
    int32_t wb_method;
    int32_t tone_method;
} KvRequest;
typedef struct {
    int32_t clamps,node_repairs,monotone_repairs,slope_repairs;
    int32_t colour_cap,matrix_cap,rowsum_cap;
} KvStats;
typedef union {
    uint8_t blend[2][KV_BYTES];
    struct {
        int32_t w[28],dd[28],delta[3],a[3],bb[3],v[3];
    } matrix;
} KvStage;
typedef struct {
    uint8_t base[KV_BYTES];
    uint8_t result[KV_BYTES];
    KvStage stage;
    KvRequest request;
    KvStats stats;
} KvWork;

_Static_assert(sizeof(KvRequest)==52,"KvRequest size");
_Static_assert(sizeof(KvStats)==28,"KvStats size");
_Static_assert(sizeof(KvStage)==1104,"KvStage size");
_Static_assert(sizeof(KvWork)==2288,"KvWork size");
_Static_assert(sizeof(int)==4,"32 bit coefficients");

/* Inputs are validated immutable expanded entries. The caller owns one work
 * area per session and excludes concurrent calls. No service calls occur.
 * Request fields match the r2 core; menu callers keep dose[KV_TONE] at zero.
 * out may overlap stock or base. work is disjoint from stock, out and stats.
 * base=work->base and request=&work->request are supported. Other overlaps
 * with work are excluded. Work fields are scratch storage on every call.
 * Returns 0, -1 for an invalid request, or -2 for a nonpositive Y row sum.
 * A failure leaves out and stats unchanged. A successful call writes all
 * 552 bytes and all stats.
 */
int kv_apply_work(const uint8_t stock[KV_BYTES],const uint8_t base[KV_BYTES],
                  const KvRequest *request,uint8_t out[KV_BYTES],
                  KvStats *stats,KvWork *work);

/* GCC M32R DImode ABI helpers. Multiplication returns the low 64 bits.
 * Division truncates toward zero. Zero divisor returns zero; MIN/-1 returns
 * MIN. Neither case is reachable from a valid mathematics request. */
int64_t __muldi3(int64_t a,int64_t b);
int64_t __divdi3(int64_t a,int64_t b);
#endif
