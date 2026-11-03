#ifndef LUT_P0_KERNEL_H
#define LUT_P0_KERNEL_H
#include <stdint.h>
enum { P0_N=17, P0_NODES=17*17*17, P0_PAIRS=4096, P0_SAMPLES=72 };
void p0_kernel(uint32_t *,uint32_t,const uint16_t *,const uint32_t *);
void p0_empty(uint32_t *,uint32_t,const uint16_t *,const uint32_t *);
void p0_decrement(uint32_t *,uint32_t,const uint16_t *,const uint32_t *);
uint32_t p0_tick(void);
uint32_t p0_irq_enabled(void);
extern const uint16_t p0_table[P0_NODES*3];
extern const uint32_t p0_coord[256];
extern const uint32_t p0_expected_crc[4];
extern const uint32_t p0_input_crc[4];
uint32_t p0_input(uint32_t);
#endif
