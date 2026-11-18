#ifndef LUTREAL_KERNEL_H
#define LUTREAL_KERNEL_H
#include <stdint.h>
/* One main-image word is a horizontal pixel pair: [Y0][Y1][Cb][Cr], big endian,
 * full range, chroma centred on 128. 4288 x 2848, stride 8576 B (2144 words). */
enum { LR_GRID=17, LR_NODES=17*17*17, LR_WIDTH=4288, LR_HEIGHT=2848,
       LR_ROW_PAIRS=LR_WIDTH/2, LR_PAIRS=LR_ROW_PAIRS*LR_HEIGHT, LR_STRIDE=LR_WIDTH*2 };
/* In place is allowed: source == destination. Each word is read before it is written. */
void lr_kernel(const uint32_t *source, uint32_t *destination, uint32_t pairs,
               const volatile uint16_t *table, const uint32_t *coordinates);
void lr_empty(void);
extern const uint16_t lr_lut[LR_NODES*3];
extern const uint32_t lr_coordinates[256];
#endif
