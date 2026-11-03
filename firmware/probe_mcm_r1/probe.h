#ifndef MCM_R1_PROBE_H
#define MCM_R1_PROBE_H
#include "services/engine_services.h"
#include "kernel.h"
#include "local/version.h"
enum { PAGE_MAIN,PAGE_REF,PAGE_BENCH,PAGE_RESULT,PAGE_HISTORY };
enum { NEW,REF_ARMED,REF_RUN,REF_DONE,ADMISSION,BENCH,DONE,ERROR };
enum { ERR_IO=1,ERR_P1,ERR_INVALID,ERR_IRQ,ERR_TICK,ERR_GUARD,ERR_CRC,ERR_BUDGET,ERR_BASE };
enum { BASE_BYTES=260,MAX_SAMPLES=48,MAX_REFS=3 };
typedef struct { uint32_t start,end,delta,valid,run; } ProbeReference;
typedef struct { uint32_t start,end,count,kind,target,crc,valid; } ProbeSample;
typedef struct {
    const RvApi *api;RvPrivateContext *ctx;RvRequest request;
    uint32_t phase,page,cursor,view,error,busy,is50,run,ref_count,used,result_index,history_index;
    uint32_t baseline_valid,baseline_status,ref_start,budget,admit_l,admit_d,admit_l_done,admit_d_done,low_res;
    uint32_t work_base,work_token,work_bytes;
    uint32_t admission_l[4],admission_d[4],binding[7];
    ProbeReference refs[MAX_REFS];ProbeSample samples[MAX_SAMPLES],admission[8];
    uint8_t baseline[BASE_BYTES];
    char rows[8][40];uint8_t glyphs[8][84];uint32_t labels[8],refs_ui[8],details[8][3];
    union { uint32_t align;uint8_t bytes[80]; } wire;
} ProbeState;
_Static_assert(sizeof(ProbeState)<=6144,"probe state must fit v3.6 state budget");
void pn_zero(void *,uint32_t);
void pn_copy(void *,const void *,uint32_t);
int pn_equal(const void *,const void *,uint32_t);
uint32_t gxr2_crc32(const uint8_t *,size_t);
uint32_t gxr2_crc_add(uint32_t,const uint8_t *,size_t);
int probe_baseline(ProbeState *,int);
int32_t es_ui_abort(RvRoot *);
RvSession *es_session(RvRoot *);
int es_range(RvRoot *,uint32_t,uint32_t,uint32_t);
int32_t p0_bootstrap(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t p0_init(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t p0_menu(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t p0_event(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t p0_apply(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t p0_close(const RvApi *,uint32_t,const RvRequest *,RvReply *);
#endif
