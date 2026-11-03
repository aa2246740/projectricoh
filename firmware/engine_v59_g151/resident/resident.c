#include "resident.h"
void rv_reset(RvRoot *r)
{
    uint32_t irq=rv_irq_save();
    rv_clear(r,offsetof(RvRoot,pins));r->version=RV_ROOT_VERSION;
    {uint32_t *e=r->epoch;do{*e++=1;}while(e!=r->epoch+RV_EPOCH_COUNT);}
    r->next_token=1;r->flags=RF_SD;
    __asm__ __volatile__("" ::: "memory");r->magic=RV_ROOT_MAGIC;
    rv_irq_restore(irq);
}
void rv_unit_snapshot(GxrceUnit *u)
{
    const uint8_t *p=RV_PTR(0x2040f818);
    memcpy(u->name,p+4,8);u->main_version=rv_be16(p+0x30);u->cmp_version=rv_be16(p+0x32);
}
uint32_t rv_code_guard(uint32_t address,uint32_t bytes)
{
    uint32_t i,step=((bytes-4)>>4)&~3u,crc=~0u;
    for(i=0;i<16;++i)crc=rv_crc_update(crc,RV_PTR(address+(i==15?bytes-4:i*step)),4);
    return ~crc;
}
uint32_t rv_check(RvRoot *r)
{
    RvSession *s;GxrceUnit unit;uint32_t reason=0;
    if(r->magic!=RV_ROOT_MAGIC||r->version!=RV_ROOT_VERSION)reason=RV_CHECK_ROOT;
    else if(!r->block)return 0;
    else if((r->flags&RF_STOP)||!(s=rv_session(r))||!r->code_bytes||r->code_bytes>RV_MAX_CODE||
       !rv_heap_span(r->code_address,r->code_bytes)||!rv_equal(&s->unit,&r->unit,sizeof(r->unit)))reason=RV_CHECK_SESSION;
    else if(r->ui_block&&!rv_ui_snapshot(r))reason=RV_CHECK_UI;
    else if(rv_code_guard(r->code_address,r->code_bytes)!=r->code_crc)reason=RV_CHECK_CODE;
    else {rv_unit_snapshot(&unit);if(!rv_equal(&unit,&r->unit,sizeof(unit)))reason=RV_CHECK_UNIT;}
    r->check_failure=reason;
    return reason;
}
void rv_retire(RvRoot *r,uint32_t reason)
{
    /* The allocator header has no allocation generation. Even a plausible
     * session may now belong to native code. Published blocks never free. */
    r->state=RV_DISABLED_UNTIL_REBOOT;r->flags|=RF_STOP|RF_ATTEMPTED;
    (void)rv_ui_abort(r);
    r->block=r->inverse=r->lease=r->lease_inverse=0;
    r->code_address=r->code_bytes=r->code_crc=0;
    r->fault=RV_STALE;r->check_failure=reason;
}
int32_t rv_engine(RvRoot *r,uint32_t offset,RvRequest *q,RvReply *p)
{
    uint32_t irq,reason,address,lease;RvSession *s;int32_t result;
    if(r->inflight)return RV_FAULT;
    reason=rv_check(r);
    if(reason){rv_retire(r,reason);return RV_FAULT;}
    irq=rv_irq_save();
    if(r->inflight){rv_irq_restore(irq);return RV_BUSY;}
    s=rv_session(r);
    if(!s||(r->flags&RF_STOP)||r->entry_serial==~0u||offset<s->code_begin||offset>s->code_end-4||(offset&3)){
        rv_irq_restore(irq);rv_retire(r,RV_CHECK_SESSION);return RV_FAULT;
    }
    ++r->entry_serial;lease=r->lease;
    q->version=1;q->bytes=64;q->flags=0;q->args[0]=q->args[1]=lease;
    /* Frozen with IRQs off: args[2..7] = epoch[BOOT,HEAP,LINK,UNIT,VIEW,S]. */
    _Static_assert(RV_BOOT_E==0&&RV_HEAP_E==1&&RV_LINK_E==2&&RV_UNIT_E==3&&
                   RV_VIEW_E==6&&RV_S_E==7,"epoch map [0,1,2,3,6,7]");
    memcpy(&q->args[2],r->epoch,16);q->args[6]=r->epoch[RV_VIEW_E];q->args[7]=r->epoch[RV_S_E];
    q->args[10]=r->block+offsetof(RvSession,context);q->args[11]=sizeof(RvPrivateContext);
    rv_clear(p,sizeof(*p));p->version=1;p->bytes=32;r->inflight=1;
    address=s->image_address+offset;rv_irq_restore(irq);
    result=rv_invoke(address,0,lease,q,p);r->inflight=0;
    reason=rv_check(r);
    if(reason||r->lease!=lease){rv_retire(r,reason?reason:RV_CHECK_SESSION);return RV_FAULT;}
    if((r->flags&RF_STOP)||result<0||result>RV_FAULT||p->version!=1||p->bytes!=32)result=RV_FAULT;
    if(result==RV_FAULT||(result==RV_CLOSE_AND_PASS&&p->status!=RV_OK))rv_retire(r,RV_CHECK_SESSION);
    return result;
}
