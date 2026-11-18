/* Tier A L2N folded-metadata verifier and remaining RAM table applicator. */
#if defined(L2N_R2V2) && defined(XPAN_ZOOM_R1)
#error "L2N_R2V2 replaces the XPAN_ZOOM_R1 table"
#endif
#ifdef L2N_R2V2
/* 244/245: 9 RAM rows (tier A + R2 v2), 245 17 rows (+ Z7 and zoom plan B re-encoded),
 * so the state bitmaps are 32-bit and a row's bit is its index (1 << i). Rows are packed:
 * old bytes at l2n_pool[off], new bytes right after them (245 does not fit with 72-byte
 * rows). Applicator steps unchanged; only the byte accessors differ. */
#define FOLD_MASK_T uint32_t
#define FOLD_BIT(p, i) ((uint32_t)1u << (i))
typedef struct {
    uint32_t addr;
    uint8_t len, group;
    uint16_t off;
} FoldPatch;
_Static_assert(sizeof(FoldPatch) == 8, "FoldPatch row size");
#include "l2n_r2v2_tables.inc.c"
#define FOLD_OLD(p) (&l2n_pool[(p)->off])
#define FOLD_NEW(p) (&l2n_pool[(p)->off + (p)->len])
#elif defined(XPAN_ZOOM_R1)
/* 242/243: 14 RAM rows, so the per-row mask and the state bitmaps are 16-bit.
 * Same 72-byte row: mask takes the old mask+pad bytes. */
#define FOLD_MASK_T uint16_t
typedef struct {
    uint32_t addr;
    uint8_t len, group;
    uint16_t mask;
    uint8_t old_bytes[32], new_bytes[32];
} FoldPatch;
_Static_assert(sizeof(FoldPatch) == 72, "FoldPatch row size");
#include "l2n_zoom_tables.inc.c"
#else
#define FOLD_MASK_T uint8_t
typedef struct {
    uint32_t addr;
    uint8_t len, group, mask, pad;
    uint8_t old_bytes[32], new_bytes[32];
} FoldPatch;

#include "l2n_fold_tables.inc.c"
#endif
#ifndef FOLD_BIT
#define FOLD_BIT(p, i) ((p)->mask)
#define FOLD_OLD(p) ((p)->old_bytes)
#define FOLD_NEW(p) ((p)->new_bytes)
#endif

typedef struct {
    uint8_t attempted;
    uint8_t err;
    uint8_t folded;
#if defined(XPAN_ZOOM_R1) || defined(L2N_R2V2)
    uint8_t valid;
    FOLD_MASK_T inherited;
    FOLD_MASK_T write_attempted;
    FOLD_MASK_T verified;
#else
    uint8_t inherited;
    uint8_t write_attempted;
    uint8_t verified;
    uint8_t valid;
#endif
} L2nFoldState;

volatile L2nFoldState fold_state __attribute__((used));

void l2n_fold_apply_once(void)
{
    uint32_t i, j, irq;
    FOLD_MASK_T pending = 0u;
    RvRoot *r = RV_PTR(RV_ROOT);
    if (fold_state.attempted || RV_WORD(0x205d9c00u) != 5u || RV_WORD(0x205d9bf8u) ||
        RV_BYTE(0x205da00bu) || !session_ok() ||
        (r->flags & RF_BUSY) || r->image_state != IMG_IDLE) {
        return;
    }
    fold_state.attempted = 1u;
    for (i = 0u; i < sizeof(l2n_folded_sites) / sizeof(l2n_folded_sites[0]); ++i) {
        const FoldPatch *p = &l2n_folded_sites[i];
        if (bytes_eq(RV_PTR(p->addr), FOLD_NEW(p), p->len)) {
            fold_state.folded |= FOLD_BIT(p, i);
        } else if (bytes_eq(RV_PTR(p->addr), FOLD_OLD(p), p->len)) {
            fold_state.err = (uint8_t)(0x20u + i);
            return;
        } else {
            fold_state.err = (uint8_t)(0x30u + i);
            return;
        }
    }
    if (!is_xpan_unit() || RV_WORD(0x2057ac38u) != 4288u || RV_WORD(0x2057ac3cu) != 1584u) {
        fold_state.err = 14u;
        return;
    }
    for (i = 0u; i < sizeof(l2n_ram_sites) / sizeof(l2n_ram_sites[0]); ++i) {
        const FoldPatch *p = &l2n_ram_sites[i];
        if (bytes_eq(RV_PTR(p->addr), FOLD_NEW(p), p->len)) {
            fold_state.inherited |= FOLD_BIT(p, i);
        } else if (bytes_eq(RV_PTR(p->addr), FOLD_OLD(p), p->len)) {
            pending |= FOLD_BIT(p, i);
        } else {
            fold_state.err = (uint8_t)(0x40u + i);
            return;
        }
    }
    if (pending) {
        irq = rv_irq_save();
        for (i = 0u; i < sizeof(l2n_ram_sites) / sizeof(l2n_ram_sites[0]); ++i) {
            const FoldPatch *p = &l2n_ram_sites[i];
            volatile uint8_t *dst = RV_PTR(p->addr);
            if (!(pending & FOLD_BIT(p, i))) continue;
            for (j = 0u; j < p->len; ++j) dst[j] = FOLD_NEW(p)[j];
        }
        rv_cache_sync();
        rv_irq_restore(irq);
        fold_state.write_attempted = pending;
    }
    for (i = 0u; i < sizeof(l2n_ram_sites) / sizeof(l2n_ram_sites[0]); ++i) {
        const FoldPatch *p = &l2n_ram_sites[i];
        if (!bytes_eq(RV_PTR(p->addr), FOLD_NEW(p), p->len)) {
            fold_state.err = (uint8_t)(0x60u + i);
            return;
        }
        fold_state.verified |= FOLD_BIT(p, i);
    }
    fold_state.valid = 1u;
}
#ifdef HF9_REVIEW
/* 246/247: the half-frame flag block 0x200FB8CC is written only while all 18 rows are verified */
int hf9_table_ok(void)
{
    return fold_state.valid == 1u;
}
#endif
#if defined(XPAN_ZOOM_R1) && defined(HF1_DIAG)
/* 242 diagnostic rows (record only; native words read when the page draws).
 * Z: 239 format, request block 0x204F0740 low 16 (Y), 0x204F0704 (target H),
 *    0x204F0710 (V scale numerator)            e.g. "Z01FE 1E0 352"
 * z: 0x204F073C low 16 (X), 0x204F0700 (target W), 0x204F070C (H scale numerator)
 *                                              e.g. "z06E8 280 352"
 * A: L2N RAM table: written mask, already-new mask, err ("--" = not attempted)
 *                                              e.g. "A3FFF 0000 00"
 * a: verified mask, folded nibble, valid, 1000-flags (b0: 0x204F0714 == 1000,
 *    b1: 0x204F0718 == 1000)                   e.g. "a3FFF F1 3" */
static void l2n_hexn(char *p, uint32_t v, unsigned n)
{
    static const char d[] = "0123456789ABCDEF";
    while (n) {
        p[--n] = d[v & 15u];
        v >>= 4;
    }
}

void l2n_fold_diag_line(unsigned row, char out[14])
{
    static const uint32_t za[2][3] = {{0x204f0740u, 0x204f0704u, 0x204f0710u},
                                      {0x204f073cu, 0x204f0700u, 0x204f070cu}};
    /* per row: position and hex width of the three fields */
    static const uint8_t lay[4][6] = {{1u, 4u, 6u, 3u, 10u, 3u}, {1u, 4u, 6u, 3u, 10u, 3u},
                                      {1u, 4u, 6u, 4u, 11u, 2u}, {1u, 4u, 6u, 2u, 9u, 1u}};
    uint32_t v[3];
    unsigned i;
    for (i = 0u; i < 13u; ++i) out[i] = ' ';
    out[13] = 0;
    out[0] = "ZzAa"[row];
    if (row < 2u) {
        for (i = 0u; i < 3u; ++i) v[i] = RV_WORD(za[row][i]);
    } else if (row == 2u) {
        v[0] = fold_state.write_attempted;
        v[1] = fold_state.inherited;
        v[2] = fold_state.err;
    } else {
        v[0] = fold_state.verified;
        v[1] = ((uint32_t)fold_state.folded << 4) | fold_state.valid;
        v[2] = (RV_WORD(0x204f0714u) == 1000u ? 1u : 0u) | (RV_WORD(0x204f0718u) == 1000u ? 2u : 0u);
    }
    for (i = 0u; i < 3u; ++i) l2n_hexn(out + lay[row][2u * i], v[i], lay[row][2u * i + 1u]);
    if (row == 2u && !fold_state.attempted) out[11] = out[12] = '-';
}
#endif
#if defined(L2N_R2V2) && defined(HF8_DIAG)
#if defined(HF9_DIAG) && HF9_DIAG_TRIM >= 1
#define L2N_DIAG_ZZ 0 /* 247: Z z dropped (zoom passed on the 245 field); 18-row masks fit 5 digits */
#else
#define L2N_DIAG_ZZ 1
#endif
/* 245 diagnostic rows (record only; native words read when the page draws). 17-row table,
 * so the masks take 5 hex digits and err moves to the a row (13 visible characters).
 * Z, z: as 242 (zoom request block), shown only with XPAN_ZOOM_R2.
 * A: L2N RAM table: written mask, already-new mask        e.g. "A1FFFF 00000"
 * a: verified mask, err ("--" = not attempted), folded nibble, valid, 1000-flags
 *    (b0: 0x204F0714 == 1000, b1: 0x204F0718 == 1000)     e.g. "a1FFFF 00 F13" */
static void l2n_hexn(char *p, uint32_t v, unsigned n)
{
    static const char d[] = "0123456789ABCDEF";
    while (n) {
        p[--n] = d[v & 15u];
        v >>= 4;
    }
}

void l2n_fold_diag_line(unsigned row, char out[14])
{
#if L2N_DIAG_ZZ
    static const uint32_t za[2][3] = {{0x204f0740u, 0x204f0704u, 0x204f0710u},
                                      {0x204f073cu, 0x204f0700u, 0x204f070cu}};
#endif
    /* per row: position and hex width of the three fields */
    static const uint8_t lay[4][6] = {{1u, 4u, 6u, 3u, 10u, 3u}, {1u, 4u, 6u, 3u, 10u, 3u},
                                      {1u, 5u, 7u, 5u, 12u, 0u}, {1u, 5u, 7u, 2u, 10u, 3u}};
    uint32_t v[3];
    unsigned i;
    for (i = 0u; i < 13u; ++i) out[i] = ' ';
    out[13] = 0;
    out[0] = "ZzAa"[row];
#if L2N_DIAG_ZZ
    if (row < 2u) {
        for (i = 0u; i < 3u; ++i) v[i] = RV_WORD(za[row][i]);
    } else
#endif
    if (row == 2u) {
        v[0] = fold_state.write_attempted;
        v[1] = fold_state.inherited;
        v[2] = 0u;
    } else {
        v[0] = fold_state.verified;
        v[1] = fold_state.err;
        v[2] = ((uint32_t)fold_state.folded << 8) | ((uint32_t)fold_state.valid << 4) |
               (RV_WORD(0x204f0714u) == 1000u ? 1u : 0u) | (RV_WORD(0x204f0718u) == 1000u ? 2u : 0u);
    }
    for (i = 0u; i < 3u; ++i) l2n_hexn(out + lay[row][2u * i], v[i], lay[row][2u * i + 1u]);
    if (row == 3u && !fold_state.attempted) out[7] = out[8] = '-';
}
#endif
