#ifdef HF1
#include "hf1.h"
#include "fx_image.h"
#include "src/firmware/engine/core/eng_internal.h"
#include "src/firmware/engine/panel/panel_port.h"
#include <stddef.h>

enum {
    HF_A = 0x848B8A00u,
    HF_B = 0x83166A00u,
    HF_W = 4288u,
    HF_H = 2848u,
    HF_STRIDE = 8576u,
#if defined(HF10_SEAM25)
    /* 250 (hf10-r1): gutter 56 words = 112 px = 2.61% of the long side
     * (research/halfframe_seam_portrait_r1/REPORT.md 4). */
    HF_SRC_W = 550u,
    HF_HALF_W = 1044u,
    HF_GUT_W = 1044u,
    HF_GUT_N = 56u,
    HF_RIGHT_W = 1100u,
#elif defined(HF5)
    HF_SRC_W = 542u,
    HF_HALF_W = 1060u,
    HF_GUT_W = 1060u,
    HF_GUT_N = 24u,
    HF_RIGHT_W = 1084u,
#else
    HF_SRC_W = 538u,
    HF_HALF_W = 1068u,
    HF_GUT_W = 1068u,
    HF_GUT_N = 8u,
    HF_RIGHT_W = 1076u,
#endif
    HF_BLACK = 0x00008080u,
    HF_RING = 0x205757A4u,
    HF_SLOTS = 18u,
    HF_SLOT = 588u,
    HF_MODE_BYTE = 0x2057AC8Eu,
#ifdef HF5_H42
    HF_OUTER = 0x20172BCCu,
    HF_ENTRY = 0x2015DF5Cu,
#else
    HF_OUTER = 0x201558A8u,
    HF_ENTRY = 0x2016583Cu,
#endif
    HF_REGION = 0x200C0DD0u,
    HF_BASE = 0x808BC000u,
    HF_LEN = 0x076C0000u,
    HF_SCAN = 0x20744800u
};

#ifdef HF5_H42
_Static_assert(sizeof(Hf1State) == 44, "Hf1State size");
#else
_Static_assert(sizeof(Hf1State) == 36, "Hf1State size");
#endif
_Static_assert(HF_HALF_W * 2u + HF_GUT_N == HF_W / 2u, "half-frame word geometry");
_Static_assert(HF_HALF_W % 4u == 0u, "4x unroll");

Hf1State hf1_state;
#if defined(HF9_CHECKED) && (!defined(HF9_REVIEW) || !defined(HF4))
#error "HF9_CHECKED needs HF9_REVIEW and HF4"
#endif
#if defined(HF10_SEAM25) || defined(HF10_PORTRAIT) || defined(HF10_REVIEW)
#if !defined(HF9_REVIEW) || !defined(HF9_CHECKED) || !defined(HF5_H42) || !defined(HF7_H43)
#error "HF10_* needs HF9_REVIEW, HF9_CHECKED, HF5_H42 and HF7_H43"
#endif
#if defined(HF10_SEAM25) != defined(HF10_REVIEW)
#error "HF10_SEAM25 and HF10_REVIEW go together (the hole HF10 and the main image share one geometry)"
#endif
#if defined(HF10_PORTRAIT) && !defined(HF10_REVIEW)
#error "HF10_PORTRAIT needs HF10_REVIEW (review mode 3 exists only in the hole HF10)"
#endif
#ifdef HF1_DIAG
/* hf10-r1: only the daily candidate 250 exists (root ruling: no test build); the diag-only
 * probes (hf7_gutter, hf4_count_twins, hf5_scan_z) still carry the 248 geometry. */
#error "HF10_* is not built with HF1_DIAG (HF10_DIAG is not implemented)"
#endif
#endif
#ifdef HF9_REVIEW
#if !defined(HF7_H43) || !defined(L2N_R2V2) || !defined(XPAN_ZOOM_R2) || !defined(MERGED_R1)
#error "HF9_REVIEW needs HF7_H43, L2N_R2V2, XPAN_ZOOM_R2 (the hole is in zoom E3 dead code) and MERGED_R1"
#endif
#if defined(HF9_DIAG) && (!defined(HF8_DIAG) || !defined(HF9_DIAG_TRIM))
#error "HF9_DIAG needs HF8_DIAG and HF9_DIAG_TRIM"
#endif
/* 246/247 half-frame post-shot review (research/halfframe_review_r1/REPORT.md 3, 4.3).
 * The native hole HF9 (L2N row at 0x200FB7D4, entered from R2c' on the review display path)
 * reads the flag block: +0 mode (1 = photo 1, sides black; 2 = photo 2, diptych; any other
 * value = leave the review alone; the hole overwrites it with the K it acted on), +4 src
 * (photo 1 small image K1+0x180), +8 E (photo 2's predicted even K; K = E or E+588 accepted).
 * The block is stock code, dead once zoom E3 is written: the DAT writes it only while the
 * whole L2N table is verified, in the order mode 0, src, E, mode. Never a jump into the DAT. */
#define HF9_FLAG 0x200FB8CCu
static struct {
    uint32_t src, k1, sum, ref;        /* photo 1 at H43: K+0x180, K, strip checksum, ref_count */
#ifdef HF9_CHECKED
    /* 248/249 (hf-review-r2, review P2-1): checked = this shooting segment has re-checked the
     * current record; a new record (H43, new photo 1) or any non-pre word clears it, so mode 2
     * always follows a re-check in the same segment (in_pre is gone). */
    uint8_t ok, clean, checked, mode;  /* ok: H43 recorded + last re-check; mode: last target */
#else
    uint8_t ok, clean, in_pre, mode;   /* ok: H43 recorded + last re-check; mode: last target */
#endif
#ifdef HF9_DIAG
    uint8_t seen, dmode, eslot, ver;   /* v row; seen/eslot = slot + 1 (0 = none, shown FF) */
#endif
#ifdef HF10_PORTRAIT
    uint8_t o;                         /* photo 1's EXIF orientation, set with the record at H43 */
#endif
} hf9;
int hf9_table_ok(void);
#endif
#ifdef HF7_H43
static uint32_t hf7_pair_k; /* K of the last successful H42 compose (photo 2) */
#endif
#ifdef HF4
static uint8_t bars_active, scan_active;

enum { HF4_Y0 = 28u, HF4_Y1 = 452u };
#ifdef HF10_SEAM25
/* 250: viewfinder bar 8-px groups 0..20 and 59..79 = columns 0..167 and 472..639 (true window
 * 164.2..475.8, REPORT 4); 248: groups 0..19 and 60..79 = columns 0..159 and 480..639. */
#define HF_BAR_GL 21u
#define HF_BAR_GR 59u
#else
#define HF_BAR_GL 20u
#define HF_BAR_GR 60u
#endif
static const uint8_t hf4_from[8] = {180u,181u,182u,183u,200u,207u,208u,209u};
static const uint8_t hf4_to[8]   = {201u,202u,203u,204u,205u,210u,211u,212u};

#define HF4_SLOT 0x20222432u
static const uint8_t hf4_r5[4] = {0x20u,0x7fu,0x21u,0x7fu};   /* at 0x2005276C */
static const uint8_t hf4_s32[5] = {' ','3',':','2',0};
static const uint8_t hf4_s12[5] = {' ','1','/','2',0};
static const uint8_t hf4_s22[5] = {' ','2','/','2',0};

static int hf4_bytes_eq(const volatile uint8_t *p, const uint8_t *q, unsigned n)
{
    unsigned i;
    for (i = 0u; i < n; ++i) if (p[i] != q[i]) return 0;
    return 1;
}

static int hf4_slot_ok(void)
{
    return hf4_bytes_eq(RV_PTR(0x2005276Cu), hf4_r5, 4u);
}

static int hf4_slot_ours(void)
{
    const volatile uint8_t *p = RV_PTR(HF4_SLOT);
    return hf4_bytes_eq(p, hf4_s12, 5u) || hf4_bytes_eq(p, hf4_s22, 5u);
}

static int hf4_active(void)
{
    const Gxr2View *view = eng_validated_view();
    return hf1_state.enabled && view && view->selected_module == 1u && fx_aspect_byte() == 1u;
}
#else
static uint8_t bars_active, scan_active, hw_shown_state;
#endif

#ifdef HF1_DIAG
Hf1Diag hf1_diag;
#endif

uint32_t hf1_tick(void);
uint32_t hf1_irq_enabled(void);

typedef struct {
    uint32_t epoch[4], power, mode;
} Hf1Bind;

static uint32_t rd32(uint32_t a)
{
    const volatile uint8_t *p = RV_PTR(a);
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}

static uint16_t rd16(uint32_t a)
{
    const volatile uint8_t *p = RV_PTR(a);
    return (uint16_t)((p[0] << 8) | p[1]);
}

static void snap(Hf1Bind *b, const RvPrivateContext *ctx)
{
    const RvRoot *r = RV_PTR(ctx->root_address);
    unsigned i;
    for (i = 0u; i < 4u; ++i) b->epoch[i] = r->epoch[i];
    b->power = r->epoch[RV_POWER_E];
    b->mode = r->epoch[RV_MODE_E];
}

static int live(const Hf1Bind *b, const RvPrivateContext *ctx)
{
    const RvRoot *r = RV_PTR(ctx->root_address);
    unsigned i;
    uint32_t now = hf1_tick();
    if (!hf1_irq_enabled() || !now) return 10;
    if (r->state != RV_READY || (r->flags & (RF_STOP | RF_UNCERTAIN)) || r->lease != ctx->nonce) return 11;
    for (i = 0u; i < 4u; ++i) if (b->epoch[i] != r->epoch[i]) return 11;
    if (b->power != r->epoch[RV_POWER_E] || b->mode != r->epoch[RV_MODE_E]) return 11;
    return 0;
}

static int strip_sum(uint32_t base, const Hf1Bind *b, const RvPrivateContext *ctx, uint32_t *out)
{
    uint32_t s = 0x48463152u, y, i;
    for (y = 0u; y < HF_H; ++y) {
        const volatile uint32_t *p;
        if ((y & 127u) == 0u && live(b, ctx)) return 1;
        p = (const volatile uint32_t *)RV_PTR(base + y * HF_STRIDE + HF_SRC_W * 4u);
        for (i = 0u; i < HF_HALF_W; i += 4u) {
            uint32_t v0 = p[i], v1 = p[i + 1u], v2 = p[i + 2u], v3 = p[i + 3u];
            s = ((s << 5) | (s >> 27)) + v0;
            s = ((s << 5) | (s >> 27)) + v1;
            s = ((s << 5) | (s >> 27)) + v2;
            s = ((s << 5) | (s >> 27)) + v3;
        }
    }
    *out = s;
    return 0;
}

static void compose_row(uint32_t cur, uint32_t oth)
{
    volatile uint32_t *c = (volatile uint32_t *)RV_PTR(cur);
    const volatile uint32_t *o = (const volatile uint32_t *)RV_PTR(oth);
    uint32_t i;
    for (i = HF_HALF_W; i > 0u; i -= 4u) {
        uint32_t j = i - 4u;
        c[HF_RIGHT_W + j + 3u] = c[HF_SRC_W + j + 3u];
        c[HF_RIGHT_W + j + 2u] = c[HF_SRC_W + j + 2u];
        c[HF_RIGHT_W + j + 1u] = c[HF_SRC_W + j + 1u];
        c[HF_RIGHT_W + j] = c[HF_SRC_W + j];
    }
#ifdef HF5
    for (i = 0u; i < HF_GUT_N; i += 4u) {
        c[HF_GUT_W + i] = HF_BLACK;
        c[HF_GUT_W + i + 1u] = HF_BLACK;
        c[HF_GUT_W + i + 2u] = HF_BLACK;
        c[HF_GUT_W + i + 3u] = HF_BLACK;
    }
#else
    c[HF_GUT_W + 0u] = HF_BLACK; c[HF_GUT_W + 1u] = HF_BLACK;
    c[HF_GUT_W + 2u] = HF_BLACK; c[HF_GUT_W + 3u] = HF_BLACK;
    c[HF_GUT_W + 4u] = HF_BLACK; c[HF_GUT_W + 5u] = HF_BLACK;
    c[HF_GUT_W + 6u] = HF_BLACK; c[HF_GUT_W + 7u] = HF_BLACK;
#endif
    for (i = 0u; i < HF_HALF_W; i += 4u) {
        c[i] = o[HF_SRC_W + i];
        c[i + 1u] = o[HF_SRC_W + i + 1u];
        c[i + 2u] = o[HF_SRC_W + i + 2u];
        c[i + 3u] = o[HF_SRC_W + i + 3u];
    }
}

#ifdef HF1_DIAG
static uint8_t cap_u8(uint32_t v)
{
    return (uint8_t)(v > 255u ? 255u : v);
}
#endif

#ifdef HF5
static int hf5_k_in_ring(uint32_t k)
{
    return k >= HF_RING && !(k & 3u) && k - HF_RING < HF_SLOTS * HF_SLOT && (k - HF_RING) % HF_SLOT == 0u;
}
#endif

#ifdef HF10_PORTRAIT
/* 250 (hf10-r1, research/halfframe_seam_portrait_r1/REPORT.md 1, 3, 5.3 items 3-9).
 * o1: photo 1's orientation, read in hf4_reg_shot1 together with state = 1;
 * o2/why: photo 2's H42 reading and void bits (record only); pv: step-2 forecast void
 * (REPORT 3.4; step 1 never sets it). */
static struct { uint8_t o1, o2, pv, why; } hfo;

/* The value the native IFD writers put into EXIF Orientation (274): *(u16)(info+30) with
 * info = *(K+0x1D8), filled by 0x20171F34 before the H42 call at 0x20172BC4 (REPORT 1.1-1.3);
 * 0 is written as 1. Returns 1/3/6/8, 0 = unreadable (K not a ring slot, K+13 != 0, info
 * pointer odd or outside the image area, any other value). Only this function knows where the
 * orientation lives (probe 251 may move it). */
static uint8_t hfo_read(uint32_t k)
{
    uint32_t inf;
    uint16_t o;
    if (!hf5_k_in_ring(k) || RV_BYTE(k + 13u) != 0u) return 0u;
    inf = rd32(k + 0x1D8u);
    if ((inf & 1u) || inf < HF_BASE || inf - HF_BASE > HF_LEN - 32u) return 0u;
    o = rd16(inf + 30u);
    if (o == 0u) o = 1u;
    return (o == 1u || o == 3u || o == 6u || o == 8u) ? (uint8_t)o : 0u;
}

/* Photo 2's H42: 0x40 = o1 or o2 unreadable (or a step-2 forecast void), 0x80 = o2 != o1. */
static uint8_t hfo_h42_fb(uint32_t k)
{
    uint8_t o2 = hfo_read(k), w = 0u;
    if (!hfo.o1 || !o2 || hfo.pv) w = 0x40u;
    else if (o2 != hfo.o1) w = 0x80u;
    hfo.o2 = o2;
    hfo.why = w;
    return w;
}

/* Step 2 hook (REPORT 3.4): a DAT-readable forecast of photo 2's orientation in its shooting
 * words. Step 1 (250): none, always 1. */
static int hfo_pre_ok(void)
{
    return 1;
}

/* EXIF 3/8: photo 1 goes to the right half (upright, photo 1 is on top / on the left).
 * Order matters: the left shift reads words [HF_SRC_W, HF_SRC_W + HF_HALF_W) of this row,
 * which the gutter and the right half overwrite, so it runs first (forward: dest < src). */
static void compose_row_swap(uint32_t cur, uint32_t oth)
{
    volatile uint32_t *c = (volatile uint32_t *)RV_PTR(cur);
    const volatile uint32_t *o = (const volatile uint32_t *)RV_PTR(oth);
    uint32_t i;
    for (i = 0u; i < HF_HALF_W; i += 4u) {
        c[i] = c[HF_SRC_W + i];
        c[i + 1u] = c[HF_SRC_W + i + 1u];
        c[i + 2u] = c[HF_SRC_W + i + 2u];
        c[i + 3u] = c[HF_SRC_W + i + 3u];
    }
    for (i = 0u; i < HF_GUT_N; i += 4u) {
        c[HF_GUT_W + i] = HF_BLACK;
        c[HF_GUT_W + i + 1u] = HF_BLACK;
        c[HF_GUT_W + i + 2u] = HF_BLACK;
        c[HF_GUT_W + i + 3u] = HF_BLACK;
    }
    for (i = 0u; i < HF_HALF_W; i += 4u) {
        c[HF_RIGHT_W + i] = o[HF_SRC_W + i];
        c[HF_RIGHT_W + i + 1u] = o[HF_SRC_W + i + 1u];
        c[HF_RIGHT_W + i + 2u] = o[HF_SRC_W + i + 2u];
        c[HF_RIGHT_W + i + 3u] = o[HF_SRC_W + i + 3u];
    }
}
#endif

#if defined(HF5) && defined(HF1_DIAG) && HF5_DIAG_TRIM < 1
static void hf5_rec_x(uint32_t k, uint8_t k6)
{
    uint32_t t17c = rd32(k + 0x17Cu), t180 = rd32(k + 0x180u);
    uint8_t off = 0xffu;
    if (t17c >= t180) {
        uint32_t d = t17c - t180;
        uint32_t q = d / 1280u;
        if (q <= 255u && q * 1280u == d) off = (uint8_t)q;
    }
    hf1_diag.x_k6 = k6;
    hf1_diag.x_w16c = cap_u8(rd16(k + 0x16Cu) >> 2);
    hf1_diag.x_off = off;
    hf1_diag.x_ac8c = RV_BYTE(0x2057ac8cu);
}
#endif

#ifdef HF4
static int hf4_reg_shot1(uint32_t ptr, uint32_t k, const Hf1Bind *bind, const RvPrivateContext *ctx)
{
    uint32_t sum = 0u;
#ifdef HF9_REVIEW
    hf9.ok = 0u;   /* new photo 1: its strip is recorded again at its H43 */
#ifdef HF9_CHECKED
    hf9.checked = 0u;
#endif
#endif
#ifdef HF10_PORTRAIT
    hfo.o1 = hfo_read(k);   /* bound to this registration (same function as state = 1) */
    hfo.pv = 0u;
#endif
    hf1_state.ref_buf = ptr;
    hf1_state.ref_count = hf1_state.h40_count;
#ifdef HF1_DIAG
    hf1_diag.q_slot1 = (uint8_t)((k - HF_RING) / HF_SLOT);
#ifndef HF5
    hf1_diag.p_diff = 0u;
#endif
#else
    (void)k;
#endif
    if (strip_sum(ptr, bind, ctx, &sum)) {
        hf1_state.state = 0u;
        return 0;
    }
    hf1_state.ref_sum = sum;
    hf1_state.state = 1u;
    return 0;
}

static int hf1_on_h40_core(const void *ctx_void, uint32_t k, uint32_t outer, uint32_t entry, int image_follow)
#else
int hf1_on_h40(const void *ctx_void, uint32_t k, uint32_t outer, uint32_t entry, int image_follow)
#endif
{
    const RvPrivateContext *ctx = ctx_void;
    const Gxr2View *view;
    uint32_t ptr = 0u, other;
    uint8_t why = 0u;
    Hf1Bind bind;
#ifdef HF5_H42
    int k_ok;
#endif

    hf1_state.h40_count++;
#if defined(HF5) && !defined(HF5_H42) && defined(HF1_DIAG) && HF5_DIAG_TRIM < 1
    if (hf5_k_in_ring(k)) {
        uint8_t k6 = RV_BYTE(k + 6u);
        if (k6 != 0u && k6 != 1u) hf5_rec_x(k, k6);
    }
#endif
    if (!hf1_state.enabled) {
        hf1_state.state = 0u;
        return 0;
    }

#ifdef HF5_H42
    k_ok = hf5_k_in_ring(k);
    hf1_state.last42_k = k;
    hf1_state.last42_ptr = k_ok ? rd32(k + 0x14Cu) : 0u;
#endif

#ifdef HF1_DIAG
#ifdef HF5
    hf1_diag.p_entry_view = (uint8_t)RV_WORD(0x205d9c00u);
    hf1_diag.q_bits = (uint8_t)((outer == HF_OUTER ? 1u : 0u) | (entry == HF_ENTRY ? 2u : 0u));
#ifndef HF5_H42
    hf1_diag.p_h40_view = hf1_diag.p_entry_view;
#endif
#else
    {
        unsigned i;
        for (i = 0u; i < 8u; ++i) {
            hf1_diag.v_disp[i] = hf1_diag.v_rec[i];
            hf1_diag.v_rec[i] = 0u;
        }
        hf1_diag.v_rec_n = 0u;
        hf1_diag.q_mode = RV_BYTE(HF_MODE_BYTE);
        hf1_diag.p_view = (uint8_t)RV_WORD(0x205d9c00u);
    }
#endif
#endif

    view = eng_validated_view();
    if (!view || view->selected_module != 1u) why = 1u;
    else if (outer != HF_OUTER) why = 2u;
    else if (entry != HF_ENTRY) why = 3u;
#ifdef HF5_H42
    else if (!k_ok) why = 4u;
#elif defined(HF5)
    else if (!hf5_k_in_ring(k)) why = 4u;
#else
    else if (k < HF_RING || (k & 3u) || k - HF_RING >= HF_SLOTS * HF_SLOT || (k - HF_RING) % HF_SLOT) why = 4u;
#endif
    else {
        uint16_t stride = rd16(k + 0x154u), width = rd16(k + 0x156u), height = rd16(k + 0x158u);
        uint32_t base, len, end, bytes;
        ptr = rd32(k + 0x14Cu);
        if (width != HF_W || height != HF_H || stride != HF_STRIDE) why = 5u;
        else if (ptr != HF_A && ptr != HF_B) why = 6u;
        else {
            bytes = HF_STRIDE * HF_H;
            end = ptr + bytes;
            base = rd32(HF_REGION);
            len = rd32(HF_REGION + 4u);
            if (base != HF_BASE || len != HF_LEN) why = 7u;
            else if (end < ptr || ptr < base || end > base + len) why = 12u;
            else if (!hf1_irq_enabled() || !hf1_tick()) why = 8u;
            else if (!image_follow) why = 9u;
        }
    }
#ifdef HF1_DIAG
    hf1_diag.p_why = why;
#ifndef HF5
    hf1_diag.p_diff = cap_u8(hf1_state.h40_count - hf1_state.ref_count);
#endif
#endif
    if (why) {
        hf1_state.last_reason = why;
        hf1_state.last_event = 3u;
        hf1_state.state = 0u;
        return 0;
    }

    other = (ptr == HF_A) ? HF_B : HF_A;
    snap(&bind, ctx);

    if (hf1_state.state != 1u) {
#ifdef HF4
        return hf4_reg_shot1(ptr, k, &bind, ctx);
#else
        uint32_t sum = 0u;
        hf1_state.ref_buf = ptr;
        hf1_state.ref_count = hf1_state.h40_count;
#ifdef HF1_DIAG
        hf1_diag.q_slot1 = (uint8_t)((k - HF_RING) / HF_SLOT);
        hf1_diag.p_diff = 0u;
#endif
        if (strip_sum(ptr, &bind, ctx, &sum)) {
            hf1_state.state = 0u;
            return 0;
        }
        hf1_state.ref_sum = sum;
        hf1_state.state = 1u;
        return 0;
#endif
    }

    {
        uint8_t fb = 0u;
        uint32_t prev = k - 2u * HF_SLOT;
        uint32_t sum = 0u;
#ifdef HF1_DIAG
        hf1_diag.q_slot2 = (uint8_t)((k - HF_RING) / HF_SLOT);
#endif
        if (hf1_state.h40_count != hf1_state.ref_count + 1u) fb |= 1u;
        if (other != hf1_state.ref_buf) fb |= 2u;
        if (prev < HF_RING) prev += HF_SLOTS * HF_SLOT;
        if (rd32(prev + 0x14Cu) != other) fb |= 4u;
        if (rd16(prev + 0x154u) != HF_STRIDE ||
            rd16(prev + 0x156u) != HF_W ||
            rd16(prev + 0x158u) != HF_H) {
            fb |= 8u;
        }
        if (strip_sum(other, &bind, ctx, &sum)) fb |= 32u;
        else if (sum != hf1_state.ref_sum) fb |= 16u;
#ifdef HF10_PORTRAIT
        fb |= hfo_h42_fb(k);   /* 0x40 unreadable, 0x80 orientation changed: photo 2 starts a new pair */
#endif

        if (fb) {
#ifdef HF4
            hf1_state.last_reason = fb;
            hf1_state.last_event = 2u;
#ifdef HF1_DIAG
            hf1_diag.p_fb = fb;
#endif
            return hf4_reg_shot1(ptr, k, &bind, ctx);
#else
            hf1_state.state = 0u;
            hf1_state.last_reason = fb;
            hf1_state.last_event = 2u;
#ifdef HF1_DIAG
            hf1_diag.p_fb = fb;
#endif
            return 0;
#endif
        }
    }

    {
        uint32_t t0, now, dt, y;
        int stopped = 0;
#ifdef HF10_PORTRAIT
        int swap = (hfo.o1 == 3u || hfo.o1 == 8u);   /* chosen once per pair, not per row */
#endif
        ((volatile RvRoot *)RV_PTR(ctx->root_address))->image_state = IMG_TOUCHED;
        t0 = hf1_tick();
        for (y = 0u; y < HF_H; ++y) {
            if ((y & 7u) == 0u && live(&bind, ctx)) {
                hf1_state.last_reason = 25u;
                stopped = 1;
                break;
            }
#ifdef HF10_PORTRAIT
            if (swap) compose_row_swap(ptr + y * HF_STRIDE, other + y * HF_STRIDE);
            else
#endif
            compose_row(ptr + y * HF_STRIDE, other + y * HF_STRIDE);
        }
        now = hf1_tick();
        dt = now - t0;
        if (dt > 9999u) dt = 9999u;
        hf1_state.last_ms = dt;
#ifdef HF1_DIAG
        hf1_diag.q_ms8 = cap_u8(dt >> 3);
#endif
        if (!stopped) {
            hf1_state.pairs++;
            hf1_state.last_event = 1u;
            hf1_state.last_reason = 0u;
            hf1_state.state = 2u;
#ifdef HF7_H43
            hf7_pair_k = k;
#endif
#ifdef HF1_DIAG
            hf1_diag.p_fb = 0u;
#endif
        } else {
            hf1_state.last_event = 2u;
            hf1_state.state = 0u;
#ifdef HF1_DIAG
            hf1_diag.p_fb = 0x20u;
#endif
        }
        hf1_state.done_tick = now;
        return 1;
    }
}

#ifdef HF4
int hf1_on_h40(const void *ctx_void, uint32_t k, uint32_t outer, uint32_t entry, int image_follow)
{
    int rc = hf1_on_h40_core(ctx_void, k, outer, entry, image_follow);
    if (hf1_state.enabled) {
        int ours = hf4_slot_ours();
#if defined(HF1_DIAG) && !defined(HF5)
        if (ours) hf1_diag.l_gg |= 8u;
        else hf1_diag.l_gg &= (uint8_t)~8u;
#endif
        if (hf4_slot_ok() && ours) {
            *(volatile uint8_t *)RV_PTR(HF4_SLOT + 1u) = (hf1_state.state == 1u) ? (uint8_t)'2' : (uint8_t)'1';
#if defined(HF1_DIAG) && !defined(HF5)
            if (hf1_diag.l_cc < 255u) ++hf1_diag.l_cc;
#endif
        }
    }
    return rc;
}

#ifdef HF5_H42
void hf5_on_h40(uint32_t k, uint32_t outer, uint32_t entry)
{
#if defined(HF1_DIAG) && HF5_DIAG_TRIM < 1
    if (hf5_k_in_ring(k)) {
        uint8_t k6 = RV_BYTE(k + 6u);
        if (k6 != 0u && k6 != 1u) hf5_rec_x(k, k6);
    }
#endif
    if (hf1_state.enabled) {
        int same_k = (k != 0u && k == hf1_state.last42_k);
#ifdef HF1_DIAG
        int same_ptr = (same_k && hf5_k_in_ring(k) && rd32(k + 0x14Cu) == hf1_state.last42_ptr);
        int h40_ok = (outer == 0x201558A8u && entry == 0x2016583Cu);
        hf1_diag.p_h40_view = (uint8_t)RV_WORD(0x205d9c00u);
        hf1_diag.q_bits = (uint8_t)((hf1_diag.q_bits & 3u) |
            (same_k ? 4u : 0u) |
            (same_ptr ? 8u : 0u) |
            ((same_k && h40_ok) ? 16u : 0u));
        if (!same_k && hf1_diag.miss42 < 15u) ++hf1_diag.miss42;
#else
        (void)outer;
        (void)entry;
        (void)same_k;
#endif
        hf1_state.last42_k = 0u;
    }
}
#endif
#endif

#ifdef HF7_H43
#if !defined(HF4) || !defined(HF5_H42)
#error "HF7_H43 needs HF4 and HF5_H42"
#endif
/* H43 (r6 stub: after native small image 0x2015DF5C, before thumbnail 0x2015E494).
 * Photo 1 of a pair: blacken words [0,81) and [239,320) of the 424 content rows
 * of the 640x480 small image (K+0x17C = K+0x180 + 28 rows) with the native black
 * word, so the small image, thumbnail and embedded preview show the right-half
 * strip of the future diptych. Photo 2: record only (H42 composed before the
 * native small image, so the native resize already carries the diptych).
 * Gates in order (research/halfframe_h43_method_r1/REPORT.md 5.2); any failure:
 * no write, why = gate code, RV_PASS. */
enum {
    HF7_VS = 1280u, HF7_VW = 640u, HF7_VH = 480u, HF7_BAND = 28u,
#ifdef HF10_SEAM25
    /* 250: sides black words [0,82) and [238,320) = the half of the 2.61% diptych (REPORT 4) */
    HF7_ROWS = 424u, HF7_XL = 82u, HF7_XR = 238u, HF7_WORDS = 320u
#else
    HF7_ROWS = 424u, HF7_XL = 81u, HF7_XR = 239u, HF7_WORDS = 320u
#endif
};
#define HF7_ALLOC_A 0x2057ACE0u
#define HF7_ALLOC_B 0x2057ACE4u
#define HF7_SP_LO 0x20000000u
#define HF7_SP_HI (0x20800000u - 8u)
#define HF7_HALF(a) (*(volatile uint16_t *)RV_PTR(a))

#ifdef HF1_DIAG
static struct {
    uint8_t n43, why, bits, ms;   /* h row */
    uint8_t rows, ace, k6, dims;  /* k row: H43-time readings of gates 3, 5, 6 */
} hf7_diag;

#if !defined(HF9_DIAG) || HF9_DIAG_TRIM < 2 /* 247 drops the H43 read-back and gutter probes */
/* Read-back of rows 0, 212, 423: 2 = both side bands all black;
 * 4 = word 81 and word 238 not black (strip edges; record only). */
static uint8_t hf7_check(uint32_t content)
{
    static const uint16_t rows[3] = {0u, 212u, 423u};
    uint32_t j, i;
    uint8_t bits = 6u;
    for (j = 0u; j < 3u; ++j) {
        const volatile uint32_t *r = (const volatile uint32_t *)RV_PTR(content + rows[j] * HF7_VS);
        for (i = 0u; i < HF7_WORDS; ++i)
            if ((i < HF7_XL || i >= HF7_XR) && r[i] != HF_BLACK) bits &= (uint8_t)~2u;
        if (r[HF7_XL] == HF_BLACK || r[HF7_XR - 1u] == HF_BLACK) bits &= (uint8_t)~4u;
    }
    return bits;
}

/* Photo 2 probe: luma of columns 318..321 in rows 100, 212, 324 all <= 24. */
static uint8_t hf7_gutter(uint32_t content)
{
    static const uint16_t rows[3] = {100u, 212u, 324u};
    uint32_t j, x;
    for (j = 0u; j < 3u; ++j) {
        const volatile uint8_t *r = (const volatile uint8_t *)RV_PTR(content + rows[j] * HF7_VS);
        for (x = 318u; x < 322u; ++x) if (r[4u * (x >> 1) + (x & 1u)] > 24u) return 0u;
    }
    return 8u;
}
#endif
#endif

#ifdef HF9_REVIEW
/* Photo 1 strip checksum: words HF7_XL..HF7_XR-1 (81..238; 250: 82..237) of all 480 rows
 * (1280 B apart) of the 640x480 small image at base, s = rol(s, 5) + word, seed 0x48463952
 * (REPORT 4.3 item 5). */
static uint32_t hf9_sum(uint32_t base)
{
    uint32_t s = 0x48463952u, y, i;
    for (y = 0u; y < HF7_VH; ++y) {
        const volatile uint32_t *p = (const volatile uint32_t *)RV_PTR(base + y * HF7_VS);
        for (i = HF7_XL; i < HF7_XR; ++i) s = ((s << 5) | (s >> 27)) + p[i];
    }
    return s;
}
#endif

int hf7_on_h43(const void *ctx_void, uint32_t k, uint32_t sp, uint32_t r0)
{
    const RvPrivateContext *ctx = ctx_void;
    Hf1Bind bind;
    uint32_t y, i, t180 = 0u, content = 0u;
    uint8_t why, k6 = 0xffu, ace = 0u, dims = 0u;
    int kin = hf5_k_in_ring(k);
#ifdef HF1_DIAG
    uint32_t t0;
#endif
    /* One read of what gates 3, 5 and 6 look at (also the 242 k row).
     * dims: 1 K+0x184 == 1280, 2 K+0x186 == 640, 4 K+0x188 == 480,
     *       8 *(sp) == 0x20172BCC (sp in RAM, aligned),
     *       0x10 K+0x17C == K+0x180 + 28 rows, 0x20 [K+0x180, +480 rows) in the image area.
     * ace: 0xE0 / 0xE4 when K+0x180 equals *(0x2057ACE0) / *(0x2057ACE4), else 0. */
    if (sp >= HF7_SP_LO && sp <= HF7_SP_HI && !(sp & 3u) && RV_WORD(sp) == HF_OUTER) dims = 8u;
    if (kin) {
        t180 = RV_WORD(k + 0x180u);
        content = RV_WORD(k + 0x17Cu);
        k6 = RV_BYTE(k + 6u);
        if (HF7_HALF(k + 0x184u) == HF7_VS) dims |= 1u;
        if (HF7_HALF(k + 0x186u) == HF7_VW) dims |= 2u;
        if (HF7_HALF(k + 0x188u) == HF7_VH) dims |= 4u;
        if (content == t180 + HF7_BAND * HF7_VS) dims |= 0x10u;
        if (t180 >= HF_BASE && t180 - HF_BASE <= HF_LEN - HF7_VH * HF7_VS) dims |= 0x20u;
        if (t180 == RV_WORD(HF7_ALLOC_A)) ace = 0xE0u;
        else if (t180 == RV_WORD(HF7_ALLOC_B)) ace = 0xE4u;
    }
#ifdef HF1_DIAG
    if (hf7_diag.n43 < 255u) ++hf7_diag.n43;
    /* rows: (K+0x17C - K+0x180) / 1280, 0xFF if K is not a ring slot, negative or >= 255 */
    y = (content - t180) / HF7_VS;
    hf7_diag.rows = (uint8_t)(!kin || content < t180 || y >= 255u ? 0xffu : y);
    hf7_diag.ace = ace;
    hf7_diag.k6 = k6;
    hf7_diag.dims = dims;
#endif
    if (!hf4_active()) why = 1u;
    else if (r0 != 0u) why = 2u;
    else if (!(dims & 8u)) why = 3u;
    else if (!kin || k != hf1_state.last42_k) why = 4u;
    else if (k6 != 1u || (dims & 7u) != 7u) why = 5u;
    else if (!ace || (dims & 0x30u) != 0x30u) why = 6u;
    else if (!hf1_irq_enabled() || !hf1_tick()) why = 8u;
    else if (hf1_state.state == 2u && hf7_pair_k == k) why = 0x20u;
    else if (hf1_state.state != 1u || hf1_state.ref_count != hf1_state.h40_count ||
             hf1_state.ref_buf != RV_WORD(k + 0x14Cu)) why = 9u;
    else why = 0u;
    if (why) {
#ifdef HF1_DIAG
        hf7_diag.why = why;
#if !defined(HF9_DIAG) || HF9_DIAG_TRIM < 2
        if (why == 0x20u) hf7_diag.bits |= hf7_gutter(content);
#endif
#endif
        return 0;
    }
    snap(&bind, ctx);
    ((volatile RvRoot *)RV_PTR(ctx->root_address))->image_state = IMG_TOUCHED;
#ifdef HF1_DIAG
    hf7_diag.bits = 0u;
    t0 = hf1_tick();
#endif
    for (y = 0u; y < HF7_ROWS; ++y) {
        volatile uint32_t *r = (volatile uint32_t *)RV_PTR(content + y * HF7_VS);
        if ((y & 63u) == 0u && live(&bind, ctx)) {
            why = 25u;
            break;
        }
        for (i = 0u; i < HF7_XL; ++i) r[i] = HF_BLACK;
        for (i = HF7_XR; i < HF7_WORDS; ++i) r[i] = HF_BLACK;
    }
#ifdef HF1_DIAG
    t0 = hf1_tick() - t0;
    hf7_diag.ms = cap_u8(t0);
    hf7_diag.why = why;
#if !defined(HF9_DIAG) || HF9_DIAG_TRIM < 2
    if (!why) hf7_diag.bits = (uint8_t)(1u | hf7_check(content));
#else
    if (!why) hf7_diag.bits = 1u;
#endif
#endif
#ifdef HF9_REVIEW
    /* Both side loops ran to the end (a live() stop leaves why = 25): record photo 1's
     * small image for photo 2's review (re-checked at photo 2's first half-press word). */
#ifdef HF10_PORTRAIT
    /* 250: record only if this K's orientation equals the one read at its H42 (same info block,
     * no writer in between: REPORT 1.3); otherwise no record (ok stays 0 from H42) and o1 = 0,
     * so photo 2 is voided at H42 and its review shows mode 1: file and review agree. */
    if (!why) {
        uint8_t o = hfo_read(k);
        if (!o || o != hfo.o1) {
            hfo.o1 = 0u;
            why = 0x30u;
        } else {
            hf9.o = o;
        }
    }
#endif
    if (!why) {
        hf9.src = t180;
        hf9.k1 = k;
        hf9.ref = hf1_state.ref_count;
        hf9.sum = hf9_sum(t180);
        hf9.ok = 1u;
        hf9.clean = 1u;
#ifdef HF9_CHECKED
        hf9.checked = 0u;   /* new record: the next pre word re-checks it */
#endif
    }
#endif
    return 1;
}
#endif

#ifdef HF4
static void hf4_fill(uint32_t base)
{
    uint32_t y, x, i, k;
    for (y = HF4_Y0; y < HF4_Y1; ++y) {
        volatile uint8_t *row = RV_PTR(base + y * 640u);
        for (x = 0u; x < 80u; ++x) {
            volatile uint8_t *p;
            volatile uint32_t *w;
            uint32_t a, c;
            if (x == HF_BAR_GL) x = HF_BAR_GR;
            p = row + 8u * x;
            w = (volatile uint32_t *)p;
            a = w[0];
            c = w[1];
            if (!(a | c)) {
                w[0] = w[1] = 0xCECECECEu;
                continue;
            }
#ifdef HF5
            if ((a == 0xCECECECEu && c == 0xCECECECEu) ||
                (a == 0xFEFEFEFEu && c == 0xFEFEFEFEu)) continue;
#else
            if (a == 0xCECECECEu && c == 0xCECECECEu) continue;
#endif
            for (i = 0u; i < 8u; ++i) {
                uint8_t v = p[i];
                if (v == 0u || v == 2u) {
                    p[i] = 206u;
                } else {
                    for (k = 0u; k < 8u; ++k) {
                        if (v == hf4_from[k]) {
                            p[i] = hf4_to[k];
                            break;
                        }
                    }
                }
            }
        }
    }
}

static void hf4_clear(uint32_t base)
{
    uint32_t y, x, i, k;
    for (y = HF4_Y0; y < HF4_Y1; ++y) {
        volatile uint8_t *row = RV_PTR(base + y * 640u);
        for (x = 0u; x < 80u; ++x) {
            volatile uint8_t *p;
            volatile uint32_t *w;
            uint32_t a, c;
            if (x == HF_BAR_GL) x = HF_BAR_GR;
            p = row + 8u * x;
            w = (volatile uint32_t *)p;
            a = w[0];
            c = w[1];
            if (!(a | c)) continue;
            if (a == 0xCECECECEu && c == 0xCECECECEu) {
                w[0] = w[1] = 0u;
                continue;
            }
            for (i = 0u; i < 8u; ++i) {
                uint8_t v = p[i];
                if (v == 206u) {
                    p[i] = 0u;
                } else {
                    for (k = 0u; k < 8u; ++k) {
                        if (v == hf4_to[k]) {
                            p[i] = hf4_from[k];
                            break;
                        }
                    }
                }
            }
        }
    }
}

void hf1_suspend(void)
{
#ifdef HF5
    fx_hf_hw_release();
#endif
    if (bars_active && fx_sw_layer1_ok(0)) {
        hf4_clear(RV_WORD(0x205a1998u));
        bars_active = 0u;
    }
    if (scan_active && fx_hw_scan_ok()) {
        hf4_clear(HF_SCAN);
        scan_active = 0u;
    }
}

#ifdef HF6
int hf1_release_for_xpan(void)
{
    if (bars_active || scan_active || !fx_hf_hw_clean()) {
        hf1_suspend();
    }
    return !bars_active && !scan_active && fx_hf_hw_clean();
}
#endif
#else
static void clear_bars(uint32_t base)
{
    uint32_t y, x, i;
    for (y = 0u; y < 480u; ++y) {
        volatile uint8_t *row = RV_PTR(base + y * 640u);
        int pip_y = (y >= 200u && y < 280u);
        for (x = 0u; x < 80u; ++x) {
            volatile uint8_t *p;
            volatile uint32_t *w;
            uint32_t a, c;
            if (x == 20u) x = 60u;
            p = row + 8u * x;
            w = (volatile uint32_t *)p;
            a = w[0];
            c = w[1];
            if (!(a | c)) continue;
            if (a == 0xffffffffu && c == 0xffffffffu) {
                w[0] = w[1] = 0u;
                continue;
            }
            {
                int in_pip = pip_y && ((x >= 5u && x < 9u) || (x >= 11u && x < 15u));
                for (i = 0u; i < 8u; ++i) {
                    uint8_t v = p[i];
                    if (v == 255u || (in_pip && v == 60u)) p[i] = 0u;
                }
            }
        }
    }
}

static void fill_bars(uint32_t base)
{
    uint32_t y, x, i;
    for (y = 0u; y < 480u; ++y) {
        volatile uint8_t *row = RV_PTR(base + y * 640u);
        for (x = 0u; x < 80u; ++x) {
            volatile uint8_t *p;
            volatile uint32_t *w;
            uint32_t a, c;
            if (x == 20u) x = 60u;
            p = row + 8u * x;
            w = (volatile uint32_t *)p;
            a = w[0];
            c = w[1];
            if (a == 0xffffffffu && c == 0xffffffffu) continue;
            if (!(a | c)) {
                w[0] = w[1] = 0xffffffffu;
                continue;
            }
            for (i = 0u; i < 8u; ++i) {
                if (p[i] == 0u) p[i] = 255u;
            }
        }
    }
}

static void draw_pip(uint32_t base, uint32_t x0, uint8_t inner)
{
    uint32_t y, dx;
    for (y = 200u; y < 280u; ++y) {
        volatile uint8_t *p = RV_PTR(base + y * 640u + x0);
        int border_y = (y < 202u || y >= 278u);
        for (dx = 0u; dx < 32u; ++dx) {
            uint8_t cur = p[dx];
            if (cur == 0u || cur == 255u || cur == 60u) {
                p[dx] = (border_y || dx < 2u || dx >= 30u) ? 60u : inner;
            }
        }
    }
}

static void update_pip(uint32_t base, uint8_t vis, uint8_t *shown)
{
    if (RV_BYTE(base + 200u * 640u + 40u) != 60u ||
        RV_BYTE(base + 279u * 640u + 71u) != 60u ||
        RV_BYTE(base + 200u * 640u + 88u) != 60u ||
        RV_BYTE(base + 279u * 640u + 119u) != 60u) {
        *shown = 0u;
    }
    if (*shown != (uint8_t)(vis + 1u)) {
        draw_pip(base, 40u, vis >= 1u ? 60u : 255u);
        draw_pip(base, 88u, vis >= 2u ? 60u : 255u);
        *shown = (uint8_t)(vis + 1u);
    }
}

void hf1_suspend(void)
{
    if ((bars_active || hf1_state.shown_state) && fx_sw_layer1_ok(0)) {
        clear_bars(RV_WORD(0x205a1998u));
        bars_active = 0u;
        hf1_state.shown_state = 0u;
    }
    if ((scan_active || hw_shown_state) && fx_hw_scan_ok()) {
        clear_bars(HF_SCAN);
        scan_active = 0u;
        hw_shown_state = 0u;
    }
}
#endif

#ifdef HF1_DIAG
#ifndef HF5
static void diag_rec_view(uint8_t vw)
{
    uint32_t i;
    for (i = 0u; i < hf1_diag.v_rec_n && i < 8u; ++i) {
        if (hf1_diag.v_rec[i] == vw) return;
    }
    if (hf1_diag.v_rec_n < 8u) {
        hf1_diag.v_rec[hf1_diag.v_rec_n++] = vw;
    } else {
        hf1_diag.v_rec[7] = 0xffu;
        hf1_diag.v_rec_n = 9u;
    }
}

static uint8_t probe_col(uint32_t base)
{
    uint32_t i, c = 0u;
    for (i = 0u; i < 64u; ++i) {
#ifdef HF4
        if (RV_BYTE(base + (100u + 4u * i) * 640u + 8u) == 206u) ++c;
#else
        if (RV_BYTE(base + (100u + 4u * i) * 640u + 8u) == 255u) ++c;
#endif
    }
    return (uint8_t)c;
}

#ifdef HF4
static uint8_t hf4_count_twins(void)
{
    uint32_t y, x, c = 0u;
    for (y = HF4_Y0; y < HF4_Y1; ++y) {
        const volatile uint8_t *row = RV_PTR(HF_SCAN + y * 640u);
        for (x = 0u; x < 160u; ++x) {
            uint8_t v = row[x];
            if ((v >= 201u && v <= 206u) || (v >= 210u && v <= 212u)) ++c;
        }
        for (x = 480u; x < 640u; ++x) {
            uint8_t v = row[x];
            if ((v >= 201u && v <= 206u) || (v >= 210u && v <= 212u)) ++c;
        }
    }
    return cap_u8(c >> 4);
}
#else
static uint8_t count_pre255(void)
{
    uint32_t y, x, c = 0u;
    for (y = 0u; y < 480u; ++y) {
        const volatile uint8_t *row = RV_PTR(HF_SCAN + y * 640u);
        for (x = 0u; x < 160u; ++x) if (row[x] == 255u) ++c;
        for (x = 480u; x < 640u; ++x) if (row[x] == 255u) ++c;
    }
    return cap_u8(c >> 4);
}
#endif
#else
#ifndef HF8_DIAG
#if HF5_DIAG_TRIM < 4
static void hf5_scan_z(uint8_t *out02, uint8_t *out254)
{
    uint32_t y, x, c02 = 0u, c254 = 0u;
    for (y = HF4_Y0; y < HF4_Y1; ++y) {
        const volatile uint8_t *row = RV_PTR(HF_SCAN + y * 640u);
        for (x = 0u; x < 640u; ++x) {
            uint8_t v;
            if (x == 160u) x = 480u;
            v = row[x];
            if (v == 0u || v == 2u) ++c02;
            else if (v == 254u || (v >= 220u && v <= 222u)) ++c254;
        }
    }
    *out02 = cap_u8(c02 >> 4);
    *out254 = cap_u8(c254 >> 4);
}
#else
static uint8_t hf5_scan_z(void)
{
    uint32_t y, x, c02 = 0u;
    for (y = HF4_Y0; y < HF4_Y1; ++y) {
        const volatile uint8_t *row = RV_PTR(HF_SCAN + y * 640u);
        for (x = 0u; x < 640u; ++x) {
            uint8_t v;
            if (x == 160u) x = 480u;
            v = row[x];
            if (v == 0u || v == 2u) ++c02;
        }
    }
    return cap_u8(c02 >> 4);
}
#endif

static void hf5_diag_s(uint32_t hb, uint32_t view)
{
    Hf1Diag *d = &hf1_diag;
    if ((hb & 128u) && d->s_b7 < 255u) ++d->s_b7;
    if (hb & 64u) {
        if (d->s_b6 < 255u) ++d->s_b6;
        d->s_b6_view = (uint8_t)view;
    }
    d->s_and &= (uint8_t)(hb & 0x3fu);
}

static void hf5_diag_u(uint8_t v, uint8_t p)
{
    Hf1Diag *d = &hf1_diag;
    if (v == 56u) return;
#if HF5_DIAG_TRIM < 3
    if (d->u_n == 0u || d->u_v0 != v || d->u_p0 != p) {
        d->u_v1 = d->u_v0;
        d->u_p1 = d->u_p0;
        d->u_v0 = v;
        d->u_p0 = p;
        d->u_n = 1u;
    }
#else
    d->u_v0 = v;
    d->u_p0 = p;
#endif
}
#endif /* !HF8_DIAG */

static void hf5_diag_r_v21(uint32_t drawn)
{
    Hf1Diag *d = &hf1_diag;
#if HF5_DIAG_TRIM < 2
    if (d->r_cnt_21 < 255u) ++d->r_cnt_21;
#endif
    if (!d->r_v21_done) {
        const volatile uint32_t *m = RV_PTR(0x20229364u);
        uint32_t m0, m1;
        uint8_t rgm = (uint8_t)drawn;
#ifndef ENG_HOST
        __asm__("" : "+r"(m));
#endif
        m0 = m[0];
        m1 = m[1];
        if (fx_session_ok()) rgm |= 1u;
        if (fx_hw_scan_ok()) rgm |= 2u;
        if (m0 == 0u) rgm |= 4u;
        if (m1 == 1u) rgm |= 8u;
        if (RV_BYTE(0x205a280eu) & 1u) rgm |= 16u;
        if (hf1_state.state == 1u) rgm |= 64u;
        d->r_gm = rgm;
        d->r_mask = (uint8_t)(((m0 & 0x0fu) << 4) | (m1 & 0x0fu));
        d->r_v21_done = 1u;
    }
}
#endif
#endif

#if defined(HF8_DIAG) && !(defined(HF9_DIAG) && HF9_DIAG_TRIM >= 3) /* 247 may drop y */
/* 245 x and y rows (record only, never a gate). */
static struct {
    uint8_t xn, xbits, xk5, xk6;   /* x: review buffer read-back at H42 */
    uint8_t yv, y15, yms, ylate;   /* y: when the bars come off after a shot */
} hf8_diag;

/* y: an undo that has work to do (our bars on layer 1 or in the scan buffer; the native
 * subwindow/CLUT hold is only taken together with scan_active) at a shot word 15, 16, 21
 * or 32: yv = that view word (expect 0F), y15 = such undos at 15, yms = that undo's ticks
 * (1 tick = 1 ms, expect <= 0F), ylate = such undos at 16/21/32 (expect 00). Other views
 * (menus, playback) are not recorded. The hf1_suspend call is the same as without diag. */
static void hf8_undo(uint32_t view)
{
    uint32_t t0;
    int rec = (view == 15u || view == 16u || view == 21u || view == 32u) &&
              (bars_active || scan_active);
    t0 = rec ? hf1_tick() : 0u;
    hf1_suspend();
    if (!rec) return;
    hf8_diag.yms = cap_u8(hf1_tick() - t0);
    hf8_diag.yv = (uint8_t)view;
    if (view == 15u) {
        if (hf8_diag.y15 < 255u) ++hf8_diag.y15;
    } else if (hf8_diag.ylate < 255u) {
        ++hf8_diag.ylate;
    }
}

/* x: at H42 of a photo with K+6 not 0 or 1 (16:9 family incl. XPan, 1:1; same filter as
 * the X row), one word of rows 0, 119, 120, 240, 360, 479 of the review buffer *(K+0x160)
 * (640x480, 1280 B rows; R2 v2 paints rows 0-119 and 360-479 with 0x00008080 before H42).
 * bits: b0 row 0 black, b1 row 119 black, b2 row 120 not black, b3 row 240 not black,
 * b4 row 360 black, b5 row 479 black (all six = 3F); 80 = pointer outside the image area
 * or unaligned (nothing read). xn counts such photos; xk5/xk6 = K+5/K+6 of the last.
 * K only has to lie in the K ring (read-only; slot alignment is not needed for a read).
 * 247: the v row replaces x (XPan review bands answered on the 245 field). */
#ifndef HF9_DIAG
void hf8_rec_review(uint32_t k)
{
    static const uint16_t rows[6] = {0u, 119u, 120u, 240u, 360u, 479u};
    uint32_t base, j, bits = 0x80u;
    uint8_t k6;
    if ((k & 3u) || k - HF_RING >= HF_SLOTS * HF_SLOT) return;
    k6 = RV_BYTE(k + 6u);
    if (k6 < 2u) return;
    base = RV_WORD(k + 0x160u);
    if (hf8_diag.xn < 255u) ++hf8_diag.xn;
    hf8_diag.xk5 = RV_BYTE(k + 5u);
    hf8_diag.xk6 = k6;
    if (!(base & 3u) && base - HF_BASE <= HF_LEN - 480u * 1280u) {
        bits = 0u;
        for (j = 0u; j < 6u; ++j)
            if ((RV_WORD(base + rows[j] * 1280u) == HF_BLACK) == (j != 2u && j != 3u)) bits |= 1u << j;
    }
    hf8_diag.xbits = (uint8_t)bits;
}
#endif
#endif

#ifdef HF5
/* 0 = undo; 1 = keep and draw (scan buffer + native subwindow);
 * 2 = keep, touch nothing (15/16: H42 lands here, H51 must stay short).
 * 0x205D9C04 = native previous view (0x202B0A74). */
#ifdef HF8_UNDO15
/* 244/245 (research/postshot_review_r2 2.2): keep only the half-press set; from the
 * shutter word 15 on, every view undoes (227 field rule), so no bars stay on layer 1
 * or the scan buffer through the shot and the review. */
static uint32_t hf5_keep(uint32_t v)
{
    return fx_halfpress_hold_view(v) ? 1u : 0u;
}
#else
static uint32_t hf5_keep(uint32_t v)
{
    uint32_t p = RV_WORD(0x205d9c04u) & 0xffu, s = hf1_state.state;
#ifdef MERGED_R1
    if (fx_halfpress_hold_view(v)) return 1u;
#else
    if (v == 12u || v == 13u || v == 14u || v == 35u) return 1u;
    if (v == 32u && (p == 13u || p == 35u)) return 1u;
#endif
    if (v == 15u || v == 16u) return s != 2u ? 2u : 0u;
    if (v == 21u || (v == 32u && p == 21u)) return s == 1u ? 1u : 0u;
    return 0u;
}
#endif

static void hf5_draw_scan(uint32_t view)
{
    uint32_t hb;
#if defined(HF1_DIAG) && !defined(HF8_DIAG)
#if HF5_DIAG_TRIM < 4
    uint8_t c02 = 0u, c254 = 0u;
    hf5_scan_z(&c02, &c254);
#else
    uint8_t c02 = hf5_scan_z();
#endif
    if (view == 5u) {
        if (c02 > hf1_diag.z_v5_max) hf1_diag.z_v5_max = c02;
    } else if (c02 > hf1_diag.z_hold_max) {
        hf1_diag.z_hold_max = c02;
        hf1_diag.z_hold_view = (uint8_t)view;
    }
#endif
    hb = fx_hf_hw_hold();
#if defined(HF1_DIAG) && !defined(HF8_DIAG)
#if HF5_DIAG_TRIM < 4
    if (!hf1_diag.z_pre_done && (hb & 128u)) {
        hf1_diag.z_pre254 = c254;
        hf1_diag.z_pre_done = 1u;
    }
#endif
    hf5_diag_s(hb, view);
#else
    (void)hb;
    (void)view;
#endif
    hf4_fill(HF_SCAN);
    scan_active = 1u;
}
#elif defined(HF3)
/* Half-press family, field-proven on XPan 218 (16:9) and seen in 3:2 on
 * half-frame 223 (V row 0C 0E 0D). 35 = released before focus (native
 * setter 0x202F566C). 0x205D9C04 = native previous view (0x202B0A74). */
static int hf3_hold_view(uint32_t v)
{
    return v==12u||v==13u||v==14u||v==35u||(v==32u&&(RV_WORD(0x205d9c04u)&0xffu)==13u);
}
#endif

void hf1_frame_key(uint32_t code)
{
    uint32_t view = RV_WORD(0x205d9c00u);
    uint8_t gm = 0u;
    (void)code;
    if (!hf1_state.enabled) {
        hf1_suspend();
        return;
    }
#ifdef HF5
    if (!hf4_active()) {
        hf1_suspend();
        return;
    }
#if defined(HF1_DIAG) && HF5_DIAG_TRIM < 2
    if (view == 15u && hf1_diag.r_last_view != 15u) {
        hf1_diag.r_cnt_1516 = 0u;
        hf1_diag.r_cnt_21 = 0u;
        hf1_diag.r_v21_done = 0u;
    }
    hf1_diag.r_last_view = (uint8_t)view;
#endif
    if (view != 5u) {
        uint32_t keep = hf5_keep(view);
#if defined(HF1_DIAG) && HF5_DIAG_TRIM < 2
        if ((view == 15u || view == 16u) && hf1_diag.r_cnt_1516 < 255u) ++hf1_diag.r_cnt_1516;
#endif
        if (keep == 2u) {
#if defined(HF1_DIAG) && HF5_DIAG_TRIM >= 2
            hf1_diag.r_v21_done = 0u;
#endif
            return;
        }
        {
            uint32_t drawn = 0u;
            if (keep == 1u && fx_session_ok() && fx_hw_scan_ok() && !fx_aspect_169()) {
                hf5_draw_scan(view);
                drawn = 32u;
            }
#ifdef HF1_DIAG
            if (view == 21u) hf5_diag_r_v21(drawn);
#else
            (void)drawn;
#endif
            if (keep == 1u) return;
        }
#if defined(HF1_DIAG) && !defined(HF8_DIAG)
        hf5_diag_u((uint8_t)view, (uint8_t)(RV_WORD(0x205d9c04u) & 0xffu));
#endif
#if defined(HF8_DIAG) && !(defined(HF9_DIAG) && HF9_DIAG_TRIM >= 3)
        hf8_undo(view);
#else
        hf1_suspend();
#endif
        return;
    }
    (void)gm;
    if (RV_WORD(0x205d9bf8u) == 0u && fx_session_ok() && fx_sw_layer1_ok(1) && !fx_aspect_169()) {
        uint32_t base = RV_WORD(0x205a1998u);
        if (hf1_state.state == 2u) {
            uint32_t now = hf1_tick();
            if ((uint32_t)(now - hf1_state.done_tick) >= 1000u) hf1_state.state = 0u;
        }
        if (fx_hw_scan_ok()) hf5_draw_scan(view);
        hf4_fill(base);
        bars_active = 1u;
    } else {
        hf1_suspend();
    }
#else
#ifdef HF1_DIAG
    diag_rec_view((uint8_t)view);
#endif
#ifdef HF4
    {
        int active = hf4_active();
#ifdef HF1_DIAG
        if (fx_aspect_byte() == 1u) hf1_diag.l_gg |= 16u;
        else hf1_diag.l_gg &= (uint8_t)~16u;
        if (active) hf1_diag.l_gg |= 32u;
        else hf1_diag.l_gg &= (uint8_t)~32u;
#endif
        if (!active) {
            hf1_suspend();
            return;
        }
    }
#endif
    if (view != 5u) {
#ifdef HF3
        if (hf3_hold_view(view)) {
            uint8_t wgm = 0u;
            if (fx_session_ok()) wgm |= 1u;
            if (fx_hw_scan_ok()) wgm |= 2u;
            if (!fx_aspect_169()) wgm |= 4u;
            if (wgm == 7u) {
#ifdef HF4
                if (hf1_state.state == 2u) {
                    uint32_t now = hf1_tick();
                    if ((uint32_t)(now - hf1_state.done_tick) >= 1000u) hf1_state.state = 0u;
                }
#ifdef HF1_DIAG
                if (!hf1_diag.k_pre_done) {
                    hf1_diag.k_pre255 = hf4_count_twins();
                    hf1_diag.k_pre_done = 1u;
                }
#endif
                hf4_fill(HF_SCAN);
                scan_active = 1u;
                wgm |= 128u;
#else
                uint8_t vis = hf1_state.state;
                if (vis == 2u) {
                    uint32_t now = hf1_tick();
                    if ((uint32_t)(now - hf1_state.done_tick) >= 1000u) {
                        hf1_state.state = 0u;
                        vis = 0u;
                    }
                }
                fill_bars(HF_SCAN);
                update_pip(HF_SCAN, vis, &hw_shown_state);
                scan_active = 1u;
                wgm |= 128u;
#endif
            }
#ifdef HF1_DIAG
            if (hf1_diag.w_calls < 255u) ++hf1_diag.w_calls;
            hf1_diag.w_gm_last = wgm;
            hf1_diag.w_gm_and &= wgm;
            hf1_diag.w_last_view = (uint8_t)view;
#ifndef HF4
            hf1_diag.hw_shown = hw_shown_state;
#endif
#endif
            return;
        }
#endif
        hf1_suspend();
        return;
    }
    if (RV_WORD(0x205d9bf8u) == 0u) gm |= 1u;
    if (fx_session_ok()) gm |= 2u;
    if (fx_sw_layer1_ok(0)) gm |= 4u;
    if (fx_sw_layer1_ok(1)) gm |= 8u;
    if (fx_hw_scan_ok()) gm |= 16u;
    if (!fx_aspect_169()) gm |= 32u;

#ifdef HF1_DIAG
    if (bars_active && (gm & 4u)) hf1_diag.k_sw = probe_col(RV_WORD(0x205a1998u));
    if (scan_active && (gm & 16u)) {
        uint8_t ks = probe_col(HF_SCAN);
        hf1_diag.k_scan = ks;
        if (ks < hf1_diag.k_scan_min) hf1_diag.k_scan_min = ks;
    }
    hf1_diag.b_vis = RV_BYTE(0x205a280eu);
#ifdef HF4
    hf1_diag.l_hh = RV_BYTE(0x205d9d4du);
#else
    hf1_diag.n_mode_94 = (uint8_t)RV_WORD(0x205a1594u);
    hf1_diag.n_mode_50 = (uint8_t)RV_WORD(0x20229350u);
    hf1_diag.n_mask = (uint8_t)(((RV_WORD(0x20229364u) & 0x0fu) << 4) | (RV_WORD(0x20229368u) & 0x0fu));
    hf1_diag.n_aspect = fx_aspect_byte();
#endif
#endif

    if ((gm & 0x2bu) == 0x2bu) {
        uint32_t base = RV_WORD(0x205a1998u);
#ifdef HF4
        if (hf1_state.state == 2u) {
            uint32_t now = hf1_tick();
            if ((uint32_t)(now - hf1_state.done_tick) >= 1000u) hf1_state.state = 0u;
        }
        hf4_fill(base);
        bars_active = 1u;
        gm |= 64u;
        if (gm & 16u) {
#ifdef HF1_DIAG
            if (!hf1_diag.k_pre_done) {
                hf1_diag.k_pre255 = hf4_count_twins();
                hf1_diag.k_pre_done = 1u;
            }
#endif
            hf4_fill(HF_SCAN);
            scan_active = 1u;
            gm |= 128u;
        }
#else
        uint8_t vis = hf1_state.state;
        if (vis == 2u) {
            uint32_t now = hf1_tick();
            if ((uint32_t)(now - hf1_state.done_tick) >= 1000u) {
                hf1_state.state = 0u;
                vis = 0u;
            }
        }
        fill_bars(base);
        update_pip(base, vis, &hf1_state.shown_state);
        bars_active = 1u;
        gm |= 64u;
        if (gm & 16u) {
#ifdef HF1_DIAG
            if (!hf1_diag.k_pre_done) {
                hf1_diag.k_pre255 = count_pre255();
                hf1_diag.k_pre_done = 1u;
            }
#endif
            fill_bars(HF_SCAN);
            update_pip(HF_SCAN, vis, &hw_shown_state);
            scan_active = 1u;
            gm |= 128u;
        }
#endif
    } else {
        hf1_suspend();
    }

#ifdef HF1_DIAG
    if (hf1_diag.b_calls < 255u) ++hf1_diag.b_calls;
    hf1_diag.b_gm_last = gm;
    hf1_diag.b_gm_and &= gm;
#ifndef HF4
    hf1_diag.hw_shown = hw_shown_state;
#endif
#endif
#endif
}

#ifdef HF9_REVIEW
/* Write the flag block only while the whole L2N table is verified (the block is stock code
 * until zoom E3 is written) and only when it differs; order mode 0, src, E, mode, so the
 * hole never sees mode 1/2 with stale src/E. A K-ring value in the mode word means the hole
 * acted on that K since our last write (247 v row records it before it is overwritten). */
static void hf9_put(uint32_t mode, uint32_t src, uint32_t e)
{
    volatile uint32_t *f = (volatile uint32_t *)RV_PTR(HF9_FLAG);
    if (!hf9_table_ok()) return;
#ifdef HF9_DIAG
    {
        uint32_t used = f[0], ue = f[2];
        if (hf5_k_in_ring(used)) {
            hf9.seen = (uint8_t)((used - HF_RING) / HF_SLOT + 1u);
            hf9.dmode = hf9.mode;
            hf9.eslot = (uint8_t)(hf9.mode == 2u && hf5_k_in_ring(ue) ? (ue - HF_RING) / HF_SLOT + 1u : 0u);
        }
    }
#endif
    hf9.mode = (uint8_t)mode;
    if (f[0] == mode && f[1] == src && f[2] == e) return;
    f[0] = 0u;
    f[1] = src;
    f[2] = e;
    f[0] = mode;
}

void hf9_disarm(void)
{
    hf9_put(0u, 0u, 0u);
}

/* After fx_frame_key and hf1_frame_key on every frame key (REPORT 3 table):
 * 0 = half-frame off or not 3:2 / not the half-frame unit; 1 = photo 1 or any doubt;
 * 2 = photo 2 in its half-press/shutter words with photo 1's strip re-checked once at the
 * first such word. Any view outside {half-press set, 15, 16, 5, 21, 32} after photo 1
 * (playback, menus) clears clean: photo 2 then shows its own strip with black sides. */
void hf9_frame_key(void)
{
    uint32_t view = RV_WORD(0x205d9c00u), m = 0u, src = 0u, e = 0u;
    int pre = fx_halfpress_hold_view(view) || view == 15u || view == 16u;
    if (!pre && view != 5u && view != 21u && view != 32u) hf9.clean = 0u;
#ifdef HF9_CHECKED
    if (!pre) hf9.checked = 0u;
#endif
    if (hf4_active()) {
        m = 1u;
        if (pre && hf1_state.state == 1u && hf9.ok && hf9.clean && hf9.ref == hf1_state.ref_count) {
#ifdef HF9_CHECKED
            if (!hf9.checked) {
#else
            if (!hf9.in_pre) {
#endif
#ifdef HF9_DIAG
                uint32_t t0 = hf1_tick();
#endif
                hf9.ok = (uint8_t)(hf9_sum(hf9.src) == hf9.sum);
#ifdef HF9_DIAG
                t0 = hf1_tick() - t0;
                hf9.ver = (uint8_t)((t0 > 127u ? 127u : t0) | (hf9.ok ? 0u : 128u));
#endif
#ifdef HF9_CHECKED
                hf9.checked = 1u;   /* whatever the result: it is in ok */
#endif
            }
#ifdef HF10_PORTRAIT
            if (hf9.ok && hf9.checked && hfo_pre_ok()) {
                /* 250: photo 1 on the right for EXIF 3/8 (hole HF10 mode 3), as the file
                 * (step 1: photo 2 assumed to keep photo 1's orientation, REPORT 3.4) */
                m = (hf9.o == 3u || hf9.o == 8u) ? 3u : 2u;
#else
#ifdef HF9_CHECKED
            if (hf9.ok && hf9.checked) {
#else
            if (hf9.ok) {
#endif
                m = 2u;
#endif
                src = hf9.src;
                e = hf9.k1 + 2u * HF_SLOT;
                if (e >= HF_RING + HF_SLOTS * HF_SLOT) e -= HF_SLOTS * HF_SLOT;
            }
        }
    }
#ifndef HF9_CHECKED
    hf9.in_pre = (uint8_t)pre;
#endif
    hf9_put(m, src, e);
}
#endif

void hf1_toggle(void)
{
    if (!hf1_state.enabled) {
        pn_zero(&hf1_state, sizeof(hf1_state));
        hf1_state.enabled = 1u;
#ifdef HF1_DIAG
        pn_zero(&hf1_diag, sizeof(hf1_diag));
#if defined(HF5) && !defined(HF8_DIAG)
        hf1_diag.s_and = 0xffu;
#elif !defined(HF5)
        hf1_diag.b_gm_and = 0xffu;
        hf1_diag.k_scan_min = 0xffu;
#ifdef HF3
        hf1_diag.w_gm_and = 0xffu;
#endif
#endif
#endif
#ifdef HF4
        {
            int r5_ok = hf4_slot_ok();
            const Gxr2View *view = eng_validated_view();
            int mod_ok = (view && view->selected_module == 1u);
            int s32_ok = hf4_bytes_eq(RV_PTR(HF4_SLOT), hf4_s32, 5u);
#if defined(HF1_DIAG) && !defined(HF5)
            hf1_diag.l_gg = (uint8_t)((r5_ok ? 1u : 0u) | (mod_ok ? 2u : 0u) | (s32_ok ? 4u : 0u));
#endif
            if (r5_ok && mod_ok && s32_ok) {
                volatile uint8_t *slot = RV_PTR(HF4_SLOT);
                unsigned i;
                for (i = 0u; i < 4u; ++i) slot[i] = hf4_s12[i];
#if defined(HF1_DIAG) && !defined(HF5)
                hf1_diag.l_cc = 1u;
#endif
            }
        }
#endif
    } else {
        hf1_state.enabled = 0u;
        hf1_state.state = 0u;
        hf1_suspend();
#ifdef HF9_REVIEW
        hf9_disarm();
#endif
#ifdef HF4
        if (hf4_slot_ok() && hf4_slot_ours()) {
            volatile uint8_t *slot = RV_PTR(HF4_SLOT);
            unsigned i;
            for (i = 0u; i < 4u; ++i) slot[i] = hf4_s32[i];
#if defined(HF1_DIAG) && !defined(HF5)
            if (hf1_diag.l_cc < 255u) ++hf1_diag.l_cc;
#endif
        }
#endif
    }
}

#if defined(HF1_DIAG) || !defined(HF4)
static void hex2(char *p, unsigned v)
{
    static const char d[] = "0123456789ABCDEF";
    p[0] = d[(v >> 4) & 15u];
    p[1] = d[v & 15u];
}
#endif

#ifndef HF4
static void d2(char *p, unsigned v)
{
    p[0] = (char)('0' + (v / 10u) % 10u);
    p[1] = (char)('0' + v % 10u);
}

static void d4(char *p, unsigned v)
{
    unsigned i;
    for (i = 4u; i; --i) {
        p[i - 1u] = (char)('0' + v % 10u);
        v /= 10u;
    }
}
#endif

void hf1_row_text(char out[14])
{
    unsigned i;
    for (i = 0u; i < 14u; ++i) out[i] = 0;
#ifdef HF4
    if (!hf1_state.enabled)      pn_copy(out, " Half Frame", 12);
    else if (hf4_active())       pn_copy(out, ">Half Frame", 12);
    else                         pn_copy(out, "!Half Frame", 12);
#else
    if (!hf1_state.enabled) {
        pn_copy(out, " HF Off", 8);
        return;
    }
    if (fx_aspect_169()) {
        pn_copy(out, "!HF 3:2Req", 11);
        return;
    }
#ifdef HF1_DIAG
    pn_copy(out, " HF b--", 8);
    if (hf1_diag.b_calls) hex2(out + 5, hf1_diag.b_gm_last);
    if (hf1_state.state == 1u) {
        pn_copy(out + 7, " 1/2", 5);
    } else if (hf1_state.last_event == 1u) {
        pn_copy(out + 7, " t0000", 7);
        d4(out + 9, hf1_state.last_ms);
    } else if (hf1_state.last_event == 2u) {
        out[7] = ' '; out[8] = 'F';
        hex2(out + 9, hf1_state.last_reason);
    } else if (hf1_state.last_event == 3u) {
        out[7] = ' '; out[8] = 'R';
        d2(out + 9, hf1_state.last_reason);
    }
#else
    if (hf1_state.state == 1u) {
        pn_copy(out, " HF 1/2", 8);
        return;
    }
    if (hf1_state.last_event == 1u) {
        pn_copy(out, " HF On t0000", 13);
        d4(out + 8, hf1_state.last_ms);
        return;
    }
    if (hf1_state.last_event == 2u) {
        pn_copy(out, " HF On F00", 11);
        hex2(out + 8, hf1_state.last_reason);
        return;
    }
    if (hf1_state.last_event == 3u) {
        pn_copy(out, " HF On R00", 11);
        d2(out + 8, hf1_state.last_reason);
        return;
    }
    pn_copy(out, " HF On", 7);
#endif
#endif
}

#ifdef HF1_DIAG
static void fmt4(char out[14], char tag, uint8_t a, uint8_t b, uint8_t c, uint8_t d)
{
    uint8_t v[4];
    unsigned i;
    v[0] = a; v[1] = b; v[2] = c; v[3] = d;
    out[0] = tag;
    for (i = 0u; i < 4u; ++i) {
        out[1u + 3u * i] = ' ';
        hex2(out + 2u + 3u * i, v[i]);
    }
    out[13] = 0;
}

void hf1_diag_line(unsigned row, char out[14])
{
#ifdef HF5
    if (row == 0u) {
        fmt4(out, 'H', cap_u8(hf1_state.h40_count), cap_u8(hf1_state.pairs),
             hf1_state.state, (uint8_t)(((hf1_diag.miss42 & 0x0fu) << 4) | (hf1_state.enabled & 0x0fu)));
#if defined(HF8_DIAG)
    } else {
#if HF5_DIAG_TRIM >= 1 /* 247: no X fields, rows H R P Q */
        static const char tags[3] = "RPQ";
        unsigned r = (row > 3u) ? 2u : (row - 1u);
#else
        static const char tags[4] = "RPQX";
        unsigned r = (row > 4u) ? 3u : (row - 1u);
#endif
        const uint8_t *p = &hf1_diag.r_gm + 4u * r;
        fmt4(out, tags[r], p[0], p[1], p[2], p[3]);
    }
#elif HF5_DIAG_TRIM >= 1
    } else if (row >= 7u) {
        fmt4(out, 'X', 0u, 0u, 0u, 0u);
    } else {
        static const char tags[6] = "SZURPQ";
        unsigned r = row - 1u;
        const uint8_t *p = &hf1_diag.s_b7 + 4u * r;
        fmt4(out, tags[r], p[0], p[1], p[2], p[3]);
    }
#else
    } else {
        static const char tags[7] = "SZURPQX";
        unsigned r = (row > 7u) ? 6u : (row - 1u);
        const uint8_t *p = &hf1_diag.s_b7 + 4u * r;
        fmt4(out, tags[r], p[0], p[1], p[2], p[3]);
    }
#endif
#else
    switch (row) {
    case 0:
        fmt4(out, 'H', cap_u8(hf1_state.h40_count), cap_u8(hf1_state.pairs),
             hf1_state.state, (uint8_t)(((hf1_state.shown_state & 0x0fu) << 4) | (hf1_state.enabled & 0x0fu)));
        break;
    case 1:
        fmt4(out, 'B', hf1_diag.b_calls, hf1_diag.b_gm_last, hf1_diag.b_gm_and, hf1_diag.b_vis);
        break;
    case 2:
#ifdef HF4
        fmt4(out, 'L', hf1_diag.l_gg, hf1_diag.l_cc, RV_BYTE(HF4_SLOT + 1u), hf1_diag.l_hh);
#else
        fmt4(out, 'N', hf1_diag.n_mode_94, hf1_diag.n_mode_50, hf1_diag.n_mask, hf1_diag.n_aspect);
#endif
        break;
    case 3:
        fmt4(out, 'K', hf1_diag.k_sw, hf1_diag.k_scan, hf1_diag.k_scan_min, hf1_diag.k_pre255);
        break;
    case 4:
        fmt4(out, 'P', hf1_diag.p_why, hf1_diag.p_fb, hf1_diag.p_diff, hf1_diag.p_view);
        break;
    case 5:
        fmt4(out, 'Q', hf1_diag.q_mode, hf1_diag.q_slot1, hf1_diag.q_slot2, hf1_diag.q_ms8);
        break;
    case 6:
        fmt4(out, 'V', hf1_diag.v_disp[0], hf1_diag.v_disp[1], hf1_diag.v_disp[2], hf1_diag.v_disp[3]);
        break;
    default:
#ifdef HF3
        fmt4(out, 'W', hf1_diag.w_calls, hf1_diag.w_gm_last, hf1_diag.w_gm_and, hf1_diag.w_last_view);
#else
        fmt4(out, 'V', hf1_diag.v_disp[4], hf1_diag.v_disp[5], hf1_diag.v_disp[6], hf1_diag.v_disp[7]);
#endif
        break;
    }
#endif
}
#ifdef HF7_H43
void hf7_diag_line(unsigned row, char out[14])
{
    if (row == 0u) fmt4(out, 'h', hf7_diag.n43, hf7_diag.why, hf7_diag.bits, hf7_diag.ms);
    else fmt4(out, 'k', hf7_diag.rows, hf7_diag.ace, hf7_diag.k6, hf7_diag.dims);
}
#endif
#ifdef HF8_DIAG
void hf8_diag_line(unsigned row, char out[14])
{
#ifdef HF9_DIAG
    /* v (replaces x): slot of the K the hole last acted on (FF = not yet), mode armed then,
     * E slot then (FF unless mode 2), last re-check ms (b7 = checksum mismatch) */
    if (!row) {
        fmt4(out, 'v', (uint8_t)(hf9.seen - 1u), hf9.dmode, (uint8_t)(hf9.eslot - 1u), hf9.ver);
        return;
    }
#if HF9_DIAG_TRIM < 3
    fmt4(out, 'y', hf8_diag.yv, hf8_diag.y15, hf8_diag.yms, hf8_diag.ylate);
#endif
#else
    const uint8_t *p = row ? &hf8_diag.yv : &hf8_diag.xn;
    fmt4(out, row ? 'y' : 'x', p[0], p[1], p[2], p[3]);
#endif
}
#endif
#endif

__asm__(
".section .text,\"ax\"\n.balign 4\n.global hf1_tick\n.hidden hf1_tick\n"
"hf1_tick:\n push r8\n push r9\n push r10\n push r11\n push r12\n push r13\n push lr\n"
" seth r0,#0x2005\n or3 r0,r0,#0xf164\n jl r0\n pop lr\n pop r13\n pop r12\n pop r11\n pop r10\n pop r9\n pop r8\n jmp lr\n"
".balign 4\n.global hf1_irq_enabled\n.hidden hf1_irq_enabled\n"
"hf1_irq_enabled:\n mvfc r0,psw\n and3 r0,r0,#0x40\n jmp lr\n nop\n"
);
#endif
