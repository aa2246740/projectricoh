#ifndef BODY_R5_HF1_H
#define BODY_R5_HF1_H
#include <stdint.h>

typedef struct {
    uint8_t enabled, state, last_reason, shown_state; /* state: 0 IDLE, 1 WAIT2, 2 DONE */
    uint32_t h40_count, ref_count, ref_buf, ref_sum; /* under HF5_H42, h40_count counts H42 entries */
    uint32_t last_ms, done_tick, pairs;
    uint8_t last_event, pad[3]; /* last_event: 0 none, 1 compose, 2 invalidate, 3 gate_reject */
#ifdef HF5_H42
    uint32_t last42_k, last42_ptr;
#endif
} Hf1State;

extern Hf1State hf1_state;

#ifdef HF1_DIAG
#ifdef HF5
#ifndef HF5_DIAG_TRIM
#define HF5_DIAG_TRIM 4
#endif
#if defined(HF8_DIAG) && (!defined(HF8_UNDO15) || !defined(HF7_H43))
#error "HF8_DIAG needs HF8_UNDO15 and HF7_H43"
#endif
typedef struct {
#ifndef HF8_DIAG /* 245 drops the S, Z, U rows (half-frame flicker, fixed on 232) */
    uint8_t s_b7, s_b6, s_b6_view, s_and;
    uint8_t z_v5_max, z_hold_max, z_hold_view, z_pre254;
    uint8_t u_v0, u_p0, u_v1, u_p1;
#endif
    uint8_t r_gm, r_mask, r_cnt_1516, r_cnt_21;
    uint8_t p_why, p_fb, p_entry_view, p_h40_view;
    uint8_t q_ms8, q_bits, q_slot1, q_slot2;
#if HF5_DIAG_TRIM < 1
    uint8_t x_k6, x_w16c, x_off, x_ac8c;
#endif
#if HF5_DIAG_TRIM < 4 && !defined(HF8_DIAG)
    uint8_t z_pre_done;
#endif
#if HF5_DIAG_TRIM < 3 && !defined(HF8_DIAG)
    uint8_t u_n;
#endif
#if HF5_DIAG_TRIM < 2
    uint8_t r_v21_done, r_last_view;
#else
    uint8_t r_v21_done;
#endif
    uint8_t miss42;
} Hf1Diag;
#else
typedef struct {
    uint8_t b_calls, b_gm_last, b_gm_and, b_vis;
#ifdef HF4
    uint8_t l_gg, l_cc, l_hh, l_pad;
#else
    uint8_t n_mode_94, n_mode_50, n_mask, n_aspect;
#endif
    uint8_t k_sw, k_scan, k_scan_min, k_pre255;
    uint8_t p_why, p_fb, p_diff, p_view;
    uint8_t q_mode, q_slot1, q_slot2, q_ms8;
    uint8_t v_disp[8];
    uint8_t v_rec[8];
    uint8_t v_rec_n, k_pre_done, hw_shown, pad[1];
#ifdef HF3
    uint8_t w_calls, w_gm_last, w_gm_and, w_last_view;
#endif
} Hf1Diag;
#endif

extern Hf1Diag hf1_diag;
void hf1_diag_line(unsigned row, char out[14]);
#ifdef HF7_H43
void hf7_diag_line(unsigned row, char out[14]);
#endif
#ifdef HF8_DIAG
void hf8_diag_line(unsigned row, char out[14]);
void hf8_rec_review(uint32_t k);
#endif
#endif

int hf1_on_h40(const void *ctx, uint32_t k, uint32_t outer, uint32_t entry, int image_follow);
#ifdef HF5_H42
void hf5_on_h40(uint32_t k, uint32_t outer, uint32_t entry);
#endif
void hf1_frame_key(uint32_t code);
void hf1_suspend(void);
#ifdef HF6
int hf1_release_for_xpan(void);
#endif
void hf1_toggle(void);
#ifdef HF9_REVIEW
void hf9_frame_key(void);
void hf9_disarm(void);
#endif
#ifdef HF7_H43
int hf7_on_h43(const void *ctx, uint32_t k, uint32_t sp, uint32_t r0);
#endif
void hf1_row_text(char out[14]);
#endif
