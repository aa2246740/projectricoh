#include "abi.h"
extern const uint8_t bv4_skip_01[],bv4_skip_02[],bv4_skip_05[],bv4_skip_06[],bv4_skip_08[],bv4_close_07[];
const uint8_t bv4_blank_details[192]={0};
void bv4_emergency(uint32_t hook,uint32_t *frame)
{
    static const uint8_t *const safety[3]={bv4_skip_06,bv4_close_07,bv4_skip_08};
    if(hook-6<=2){frame[1]=RV4_ADDRESS(safety[hook-6]);frame[7]=0;}
    else if(hook==5){frame[1]=RV4_ADDRESS(bv4_skip_05);frame[13]=RV4_ADDRESS(bv4_blank_details);}
    else if(hook==1){frame[1]=RV4_ADDRESS(bv4_skip_01);frame[15]=1;}
    else if(hook==2){frame[1]=RV4_ADDRESS(bv4_skip_02);frame[7]=1;}
}
static int live(const Bv4Root *r)
{
    Bv4Lifetime now;uint8_t digest[32];
    if(bv4_native_lifetime(&now)||now.boot_instance!=r->scope.boot_instance||
       now.heap_epoch!=r->scope.heap_epoch||now.heap_begin!=r->heap_begin||now.heap_end!=r->heap_end||
       now.heap_begin!=RV4_WORD(RV4_HEAP_BEGIN)||now.heap_end!=RV4_WORD(RV4_HEAP_END)||
       !r->base||r->inverse!=~r->base||r->file_bytes<BV4_HEADER_BYTES||
       r->file_bytes>BV4_MAX_FILE||r->bss_bytes>BV4_MAX_BSS||
       !rv4_allocation(r->base,r->file_bytes+r->bss_bytes,r->alloc_bytes)||
       r->code_offset<BV4_HEADER_BYTES||(r->code_offset&3)||r->code_bytes<4||
       r->code_offset>r->file_bytes||r->code_bytes>r->file_bytes-r->code_offset||
       (r->hook_offset&3)||r->hook_offset<r->code_offset||
       r->hook_offset>r->code_offset+r->code_bytes-4)return 0;
    bv4_sha256(RV4_PTR(r->base+r->code_offset),r->code_bytes,digest);
    return rv4_equal(digest,r->code_sha256,32);
}
void bv4_hook_observe(Bv4Root *r,uint32_t hook,uint32_t *frame)
{
    uint32_t irq,base,entry,bss,saved[17];int32_t status=RV4_STALE;
    if(!frame||hook<1||hook>38||hook==3||hook==4)return;
    irq=rv4_irq_save();
    if(r->magic!=BV4_MAGIC||r->state!=BV4_READY||
       r->active_calls==~0u||r->serial==~0u){
        uint32_t factory=r->magic==BV4_MAGIC&&(r->flags&BV4_FACTORY);
        if(r->magic==BV4_MAGIC&&r->state==BV4_READY){
            r->state=BV4_DISABLED;r->flags|=BV4_QUARANTINED;r->fault=(uint32_t)RV4_RANGE;
        }
        rv4_irq_restore(irq);if(!factory)bv4_emergency(hook,frame);return;
    }
    /* These pins protect trusted resident code, not a DAT busy flag. Nested
     * calls still reach the extension's safety/admission layer. Heap reset must
     * be blocked by the native lifetime protocol until every pin has returned. */
    ++r->active_calls;++r->serial;base=r->base;entry=base+r->hook_offset;
    bss=base+r->file_bytes;RV4_BARRIER();rv4_irq_restore(irq);
    memcpy(saved,frame,sizeof(saved));
    if(live(r)){
        status=bv4_invoke_hook(entry,hook,frame,bss);
        if(r->magic!=BV4_MAGIC||r->state!=BV4_READY||r->base!=base||!live(r))status=RV4_STALE;
    }
    irq=rv4_irq_save();
    if(!r->active_calls)status=RV4_STALE;else --r->active_calls;
    if(status){r->state=BV4_DISABLED;r->flags=(r->flags&~BV4_FACTORY)|BV4_QUARANTINED;r->fault=(uint32_t)status;}
    RV4_BARRIER();rv4_irq_restore(irq);
    if(status){memcpy(frame,saved,sizeof(saved));bv4_emergency(hook,frame);}
}
