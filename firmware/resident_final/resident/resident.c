#include "resident.h"

void rv_reset(RvRoot *r)
{
    rv_clear(r,offsetof(RvRoot,pins));r->magic=RV_ROOT_MAGIC;r->version=1;
    {uint32_t *e=r->epoch;do{*e++=1;}while(e!=r->epoch+RV_EPOCH_COUNT);}r->next_token=1;
}
void rv_epochs(RvRoot *r,uint32_t mask)
{
    unsigned i;
    for(i=0;i<RV_EPOCH_COUNT;++i)if(mask&(1u<<i)){
        if(r->epoch[i]==~0u){r->state=RV_FENCED;r->fault=RV_RANGE;r->flags|=RF_STOP;r->grain=0;}
        else ++r->epoch[i];
    }
}
void rv_notify(RvRoot *r,uint32_t h,uint32_t phase,int32_t value)
{
    uint32_t mask=0;
    rv_record(r,h,phase,(uint32_t)value,r->inflight);
    if(phase){
        if(h==20&&value==0&&(r->rx&1)){
            if(r->rx==~0u){r->flags|=RF_STOP;r->fault=RV_RANGE;}
            else ++r->rx;
        }
        if(h==22&&value==0)r->flags|=RF_SD;
        return;
    }
    {static const uint16_t masks[22]={
        [11-11]=1u<<RV_VIEW_E,[12-11]=1u<<RV_VIEW_E,
        [13-11]=(1u<<RV_S_E)|(1u<<RV_VIEW_E),[14-11]=(1u<<RV_S_E)|(1u<<RV_VIEW_E),
        [15-11]=(1u<<RV_BOOT_E)|(1u<<RV_HEAP_E)|(1u<<RV_IO_E),
        [16-11]=(1u<<RV_HEAP_E)|(1u<<RV_IO_E),[17-11]=1u<<RV_SEG_E,[18-11]=1u<<RV_SEG_E,
        [19-11]=(1u<<RV_LINK_E)|(1u<<RV_UNIT_E),[20-11]=1u<<RV_UNIT_E,
        [21-11]=(1u<<RV_LINK_E)|(1u<<RV_UNIT_E),[22-11]=(1u<<RV_SD_E)|(1u<<RV_IO_E),
        [23-11]=(1u<<RV_MODE_E)|(1u<<RV_S_E)|(1u<<RV_VIEW_E),
        [25-11]=(1u<<RV_POWER_E)|(1u<<RV_LINK_E),
        [31-11]=(1u<<RV_IROM_E)|(1u<<RV_SD_E)|(1u<<RV_IO_E),
        [32-11]=(1u<<RV_IROM_E)|(1u<<RV_IO_E)|(1u<<RV_UNIT_E)};
     if(h-11>=22||!(mask=masks[h-11]))return;}
    if((h==17||h==18)&&value<2)mask|=(1u<<RV_BOOT_E)|(1u<<RV_HEAP_E)|(1u<<RV_IO_E);
    if(h==20){if(r->rx>=0xfffffffeu){r->flags|=RF_STOP;r->fault=RV_RANGE;}else r->rx+=(r->rx&1)?2:1;}
    if(h==22)r->flags&=~RF_SD;
    rv_epochs(r,mask);
    /* Tier two is notification only. The engine handles effects at its next
     * safe menu entry; no heap access, UI mutation or native work here. */
    if(h==13||h==14||h==23||h==25||h==31||h==32)return;
    rv_ui_abort(r);
    if(mask&((1u<<RV_BOOT_E)|(1u<<RV_HEAP_E))){
        r->block=r->inverse=r->lease=0;r->state=RV_FENCED;
        if(r->inflight||r->fault==RV_RANGE)r->flags|=RF_STOP;else r->flags&=~RF_STOP;
    }else if(mask&((1u<<RV_LINK_E)|(1u<<RV_UNIT_E)|(1u<<RV_SEG_E)))r->state=RV_FENCED;
    if(r->inflight&&(h==15||h==16||h==17||h==18))r->fault=RV_UNCERTAIN;
}
int32_t rv_engine(RvRoot *r,uint32_t offset,RvRequest *q,RvReply *p)
{
    uint32_t irq=rv_irq_save(),boot=r->epoch[RV_BOOT_E],heap=r->epoch[RV_HEAP_E],address;
    RvSession *s=rv_session(r);int32_t result;
    if(!s||r->inflight||(r->flags&RF_STOP)||offset<s->code_begin||offset>s->code_end-4||(offset&3)){
        rv_irq_restore(irq);rv_ui_abort(r);return RV_FAULT;
    }
    q->version=1;q->bytes=64;q->flags=0;q->args[0]=q->args[1]=r->lease;
    q->args[2]=boot;q->args[3]=heap;q->args[4]=r->epoch[RV_LINK_E];q->args[5]=r->epoch[RV_UNIT_E];
    q->args[6]=r->epoch[RV_VIEW_E];q->args[7]=r->epoch[RV_S_E];
    q->args[10]=r->block+offsetof(RvSession,context);q->args[11]=sizeof(RvPrivateContext);
    rv_clear(p,sizeof(*p));p->version=1;p->bytes=32;r->inflight=1;
    address=s->image_address+offset;rv_irq_restore(irq);
    /* The engine supplies its own service table using rv_services_init(). */
    result=rv_invoke(address,0,r->lease,q,p);r->inflight=0;
    if(boot!=r->epoch[RV_BOOT_E]||heap!=r->epoch[RV_HEAP_E]||!rv_session(r)||
       (r->flags&RF_STOP)||q->args[4]!=r->epoch[RV_LINK_E]||q->args[5]!=r->epoch[RV_UNIT_E])result=RV_FAULT;
    if(result<0||result>RV_FAULT||p->version!=1||p->bytes!=32)result=RV_FAULT;
    if(result>=RV_CLOSE_AND_PASS)rv_ui_abort(r);
    if(result==RV_FAULT){r->state=RV_FENCED;r->fault=RV_FAULTED;}
    return result;
}
void rv_grain(RvRoot *r,uint8_t *p)
{
    uint32_t g=r->grain,address=RV_WORD(0x200c0dac),size,level;
    const volatile uint8_t *s=RV_PTR(address);
    if(!g||r->state!=RV_READY||(r->flags&(RF_UNCERTAIN|RF_STOP))||!address||RV_WORD(0x200c0db0)<0xc9e||
       s[0x36e]!=(g&127)||(RV_BYTE(0x205d9a7f)!=0&&RV_BYTE(0x205d9a7f)!=4)||
       (p[0x1a]|p[0x14]|p[0x75]|p[0x1e]|p[0x26]))return;
    size=s[0x3aa];if(size>16||!((0x11126u>>size)&1))return;
    level=s[0xc9d];p[0x1a]=21;p[0x10]=0;p[0x32]=1;p[0x6f]=level-1<3?level:1;
}
