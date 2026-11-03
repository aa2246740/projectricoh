#ifndef RECIPE_TWEAK_INT_H
#define RECIPE_TWEAK_INT_H
#include <stdint.h>

/* Host reference only. The caller validates table identity/masks and supplies
 * immutable defaults. These functions perform no I/O and allocate no heap. */
int rt_tone(const uint8_t a[62], const uint8_t b[33], int pivot,
            int contrast, int highlight, int shadow, uint8_t out[33]);
int rt_colour(const uint8_t in[96], int level, uint8_t out[96]);
#endif
