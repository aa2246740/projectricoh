#ifndef LUT_P0_PROBE_H
#define LUT_P0_PROBE_H
#include "local/services114/candidate/engine_services/engine_services.h"
#include "kernel.h"
typedef struct { uint32_t start,end,pairs,kind,crc; } P0Sample;
enum { P0_NEW,P0_REFERENCE,P0_BENCH,P0_DONE,P0_ERROR };
enum { P0_REF_STARTED=1, P0_REF_CONFIRMED=2, P0_REF_INTERRUPTED=4,
       P0_ADMISSION_STEPS=4, P0_LOG_PROTOCOL=0x50305233u };
typedef struct {
    const RvApi *api; RvPrivateContext *ctx;
    RvRequest request;
    uint32_t phase,reference_start,reference_end,reference_delta,view,cursor,used,flush_ok,error;
    uint32_t reference_flags,admitted,admission_budget,admission_ticks[4];
    P0Sample samples[P0_SAMPLES];
    uint32_t scratch[P0_PAIRS];
    char rows[16][32]; uint8_t glyphs[16][70];
    uint32_t labels[16],refs[16],details[16][3];
    union { uint32_t align; uint8_t bytes[80]; } wire;
} P0State;
void pn_zero(void *,uint32_t);
void pn_copy(void *,const void *,uint32_t);
int pn_equal(const void *,const void *,uint32_t);
uint32_t gxr2_crc32(const uint8_t *,size_t);
uint32_t gxr2_crc_add(uint32_t,const uint8_t *,size_t);
void ig_bx_init(RvPrivateContext *);
void ig_bx_event(unsigned,unsigned,uint32_t,uint32_t,uint32_t,int32_t);
int ig_bx_flush(unsigned);
int32_t p0_bootstrap(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t p0_init(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t p0_menu(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t p0_event(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t p0_apply(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t p0_close(const RvApi *,uint32_t,const RvRequest *,RvReply *);
#ifdef RV_HOST
void p0_host_reset(void);
P0State *p0_host_state(void);
uint32_t p0_host_address(const void *);
#endif
#endif
