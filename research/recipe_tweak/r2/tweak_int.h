#ifndef RECIPE_TWEAK_R2_INT_H
#define RECIPE_TWEAK_R2_INT_H
#include <stdint.h>

#define RT_ALGORITHM "gxr-recipe-tweak/odds-q12-v2"
#define RT_DEFAULT_LIMIT 5
#define RT_EXTENDED_LIMIT 8
enum { RT_CONTRAST, RT_SATURATION, RT_HIGHLIGHT, RT_SHADOW, RT_WARMTH, RT_TINT, RT_PARAMETER_COUNT };

/* Immutable default rows in, separate staging rows out. No I/O or heap.
 * Return -1 on invalid input. The owner validates recipe identity and masks.
 * Tone uses only uint32 arithmetic; rounded curves are non-decreasing.
 * Saturation returns flags: 1=colour headroom, 2=matrix headroom, 4=disabled.
 * gains receives requested, allocated colour, allocated matrix Q12 gains.
 * WB requires an explicit, independently verified lane/sign binding.
 * Its result is two bytes in S+0x6dd / S+0x6de order, never a device write.
 */
int rt_tone(const uint8_t a[62], const uint8_t b[33], int pivot,
            int contrast, int highlight, int shadow, uint8_t out[33]);
int rt_saturation(const uint8_t colour[96], const uint8_t matrix[56],
                  int level, int enabled, uint8_t out_colour[96],
                  uint8_t out_matrix[56], uint16_t gains[3]);
int rt_wb(int base_ab, int base_gm, int warmth, int tint,
          int ab_lane, int ab_sign, int gm_sign, uint8_t encoded[2]);
#endif
