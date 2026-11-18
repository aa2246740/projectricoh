#ifndef FX_POOL_H
#define FX_POOL_H
#include "src/firmware/card_container_v2/internal.h"
enum { FX_HEADER=32, FX_ENTRY=32, FX_NAME=12 };
const uint8_t *fx_area(const Gxr2View *);
const uint8_t *fx_entry(const Gxr2View *,unsigned index);
int fx_area_valid(const Gxr2View *);
unsigned fx_unit_mask(const Gxr2View *,const uint8_t *);
Gxr2Row fx_raw_row(const Gxr2View *,const uint8_t *,unsigned row);
Gxr2Status fx_expand(const Gxr2View *,unsigned index,uint8_t out[552]);
int fx_visible(const Gxr2View *,unsigned unit,unsigned ordinal);
unsigned fx_count(const Gxr2View *,unsigned unit);
void fx_name(const Gxr2View *,unsigned index,char out[FX_NAME+1]);
int a_valid(const uint8_t *,unsigned);
int matrix_valid(const uint8_t *);
int fx_row_valid(const uint8_t *,unsigned row,unsigned flags);
Gxr2Status gxr2_expand_descriptor(const Gxr2View *,const uint8_t *,unsigned effects,uint8_t out[552]);
#endif
