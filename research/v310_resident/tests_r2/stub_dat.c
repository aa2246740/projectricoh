/* Test DAT only. It checks dispatch and the fixed-word contract, not colour
 * correctness, hardware timing, or production eligibility. No colour write
 * service is used. Mode 0 is the explicitly prepared host-model fixture. */
#include "resident.h"
#ifndef STUB_KIND
#define STUB_KIND 0
#endif

__attribute__((section(".text.stub_entry"),used))
int32_t stub_entry(const RvApi *api,uint32_t lease,const RvRequest *q,RvReply *p)
{
    RvRoot *r=(RvRoot *)(uintptr_t)RV_ROOT;
    RvSession *s=(RvSession *)(uintptr_t)r->block;
    volatile uint32_t *trace=(volatile uint32_t *)(uintptr_t)(s->image_address+s->image_bytes);
    volatile uint32_t *word=(volatile uint32_t *)(uintptr_t)q->args[9];
    (void)api;(void)lease;
    p->status=RV_OK;
    if(r->state==RV_VALIDATED){
        uint32_t i,*entries=&s->entries.init;
        s->entries.version=1;s->entries.bytes=40;
        for(i=0;i<9;++i)entries[i]=s->code_begin;
        ++trace[0];p->actual=40;p->detail=RV_INIT_DONE;p->capabilities=0;
        return RV_CONSUMED;
    }
    if(q->args[8]!=RV_BOOT_RUN){p->status=RV_UNSUPPORTED;return RV_PASS;}
    ++trace[1];trace[2]=q->args[9];trace[3]=r->reserved_lane;
    if(q->args[9]!=RV_ROOT+236){p->status=RV_ARGUMENT;return RV_FAULT;}
    if(STUB_KIND==0){p->status=RV_UNSUPPORTED;return RV_PASS;}
    /* M01 and C02 prove these raw byte locations. The accepted value 0 is
     * a model precondition, not proof of the physical dial binding. */
    if(*(volatile uint8_t *)0x205d9aa3u||*(volatile uint8_t *)0x205d9a7fu){
        p->detail=2;return RV_CONSUMED; /* not applicable, zero writes */
    }
    *word|=BO_DIRTY;trace[4]=*word;
    if(STUB_KIND==1){*word&=~BO_DIRTY;p->detail=1;return RV_CONSUMED;}
    if(STUB_KIND==2){p->status=RV_IO;p->detail=3;return RV_CONSUMED;}
    /* Change the already executed first code word. The real rv_engine
     * post-call code guard must retire this session before H51 resumes. */
    *(volatile uint32_t *)(uintptr_t)r->code_address^=1u;
    return RV_CONSUMED;
}
