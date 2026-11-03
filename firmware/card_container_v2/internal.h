#ifndef GXR2_INTERNAL_H
#define GXR2_INTERNAL_H
#include "gxrce.h"
static inline uint16_t be16(const uint8_t *p)
{ return (uint16_t)((uint16_t)p[0]<<8 | p[1]); }
static inline uint32_t be32(const uint8_t *p)
{ return (uint32_t)p[0]<<24 | (uint32_t)p[1]<<16 | (uint32_t)p[2]<<8 | p[3]; }
static inline void put16(uint8_t *p,uint16_t v)
{ p[0]=(uint8_t)(v>>8); p[1]=(uint8_t)v; }
static inline void put32(uint8_t *p,uint32_t v)
{ p[0]=(uint8_t)(v>>24); p[1]=(uint8_t)(v>>16); p[2]=(uint8_t)(v>>8); p[3]=(uint8_t)v; }
static inline int equal(const uint8_t *a,const uint8_t *b,size_t n)
{ size_t i; for(i=0;i<n;++i) if(a[i]!=b[i]) return 0; return 1; }
static inline int zero(const uint8_t *p,size_t n)
{ size_t i; for(i=0;i<n;++i) if(p[i]) return 0; return 1; }
static inline void copy(uint8_t *d,const uint8_t *s,size_t n)
{ size_t i; for(i=0;i<n;++i) d[i]=s[i]; }
static inline int signed_byte(uint8_t x) { return x<128 ? (int)x : (int)x-256; }
static inline uint32_t align4(uint32_t n) { return (n+3u)&~3u; }
static inline int unit_equal(const uint8_t *p,const Gxr2Unit *u)
{ return equal(p,u->name,8) && be16(p+8)==u->main_version && be16(p+10)==u->cmp_version; }
static inline const uint8_t *directory(const Gxr2View *v,unsigned m)
{ return v->bytes+v->sections[2].offset+64u*m; }
static inline const uint8_t *metadata(const Gxr2View *v,unsigned m,unsigned s)
{ return v->bytes+be32(directory(v,m)+24)+(s-1u)*v->record_bytes; }
static inline const uint8_t *descriptor(const Gxr2View *v,unsigned m,unsigned n)
{ return v->bytes+be32(directory(v,m)+20)+16u+16u*n; }
/* Shared across gate and semantics. Bounds every bucket before any stock read. */
Gxr2Status gxr2_pool_layout(const Gxr2View *);
Gxr2Status gxr2_tweak_layout(const Gxr2View *,uint16_t *,uint16_t *);
Gxr2Row gxr2_raw_row(const Gxr2View *,const uint8_t *desc,unsigned row);
uint32_t gxr2_crc_begin(void);
uint32_t gxr2_crc_add(uint32_t,const uint8_t *,size_t);
uint32_t gxr2_crc_end(uint32_t);
uint32_t gxr2_crc_zeroed(const uint8_t *,size_t,size_t,size_t);
#endif
