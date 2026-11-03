#include "resident.h"


void rv_reset(RvRoot *r)
{
    rv_clear(r,sizeof(*r));r->magic=RV_ROOT_MAGIC;r->version=1;
    r->epoch[RV_BOOT_E]=1;r->flags[F_NEXT]=1;r->capabilities=RV_READ_CAPS;
}
RvSession *rv_session(RvRoot *r)
{
    if(!r->reserved[0]||r->reserved[1]!=~r->reserved[0]||!rv_heap_span(r->reserved[0],RV_BLOCK_BYTES)||
       r->flags[F_BOOT]!=r->epoch[RV_BOOT_E]||r->flags[F_HEAP]!=r->epoch[RV_HEAP_E]) return 0;
    return RV_PTR(r->reserved[0]);
}
int rv_range(RvRoot *r,uint32_t token,uint32_t base,uint32_t bytes)
{
    RvSession *s=rv_session(r);unsigned i;
    if(s) for(i=0;i<RV_LEASES;++i) {
        RvLease *l=&s->leases[i];
        if(l->token&&l->token==token&&l->inverse==~token&&base>=l->base&&
           base-l->base<=l->length&&bytes<=l->length-(base-l->base)) return 1;
    }
    return 0;
}
void rv_record(RvRoot *r,uint32_t hook,uint32_t phase,uint32_t a,uint32_t b)
{
    uint32_t irq=rv_irq_save(),seq=r->event_head+1;RvEvent *e;
    if(!seq) {r->state=RV_FENCED;r->fault=RV_RANGE;r->flags[F_GRAIN]=0;r->flags[F_STOP]=1;}
    else {
        e=&r->events[(seq-1)&15];e->hook=hook;e->phase=phase;e->a=a;e->b=b;
        __asm__ __volatile__("" ::: "memory");e->sequence=seq;r->event_head=seq;
        if(seq>16) ++r->dropped;
    }
    rv_irq_restore(irq);
}
void rv_ui_abort(RvRoot *r)
{
    uint32_t irq=rv_irq_save(),*v=r->ui_restore;
    if(v[6]&&RV_WORD(0x2022f5a8)==v[6]) {
        RV_WORD(0x2022f5a8)=0x2022d610;RV_BYTE(0x2022f5ac)=7;
        if(RV_BYTE(0x2022f726)>6) RV_BYTE(0x2022f726)=0;
    }
    if(v[0]&&v[1]&&v[1]<=2&&RV_WORD(0x205a27d8)==v[0]&&RV_BYTE(0x205a27d4)==v[1]) {
        volatile uint32_t *top=RV_PTR(v[0]+8*(v[1]-1));
        if(top[0]==v[2]&&top[1]==v[4]) {top[0]=v[2];top[1]=0x2022f71c;}
    }
    rv_clear(v,32);r->flags[F_GRAIN]=0;rv_irq_restore(irq);
}
void rv_epochs(RvRoot *r,uint32_t mask)
{
    unsigned i;
    for(i=0;i<RV_EPOCH_COUNT;++i) if(mask&(1u<<i)) {
        if(r->epoch[i]==~0u) {r->state=RV_FENCED;r->fault=RV_RANGE;r->flags[F_STOP]=1;}
        else ++r->epoch[i];
    }
}
void rv_notify(RvRoot *r,uint32_t h,uint32_t phase,int32_t value)
{
    uint32_t mask=0;
    rv_record(r,h,phase,(uint32_t)value,r->inflight);
    if(phase) {
        if(h==20&&value==0&&(r->flags[F_RX]&1)){if(r->flags[F_RX]==~0u){r->flags[F_STOP]=1;r->fault=RV_RANGE;}else ++r->flags[F_RX];}
        if(h==22) r->flags[F_SD]=value==0;
        return;
    }
    switch(h) {
    case 11:case 12: mask=1u<<RV_VIEW_E;break;
    case 13:case 14: mask=(1u<<RV_S_E)|(1u<<RV_VIEW_E);break;
    case 15:mask=(1u<<RV_BOOT_E)|(1u<<RV_HEAP_E)|(1u<<RV_IO_E);break;
    case 16:mask=(1u<<RV_HEAP_E)|(1u<<RV_IO_E);break;
    case 17:case 18:mask=1u<<RV_SEG_E;if(value<2) mask|=(1u<<RV_BOOT_E)|(1u<<RV_HEAP_E)|(1u<<RV_IO_E);break;
    case 19:case 21:mask=(1u<<RV_LINK_E)|(1u<<RV_UNIT_E);break;
    case 20:mask=1u<<RV_UNIT_E;if(r->flags[F_RX]>=0xfffffffeu){r->flags[F_STOP]=1;r->fault=RV_RANGE;}else r->flags[F_RX]+=(r->flags[F_RX]&1)?2:1;break;
    case 22:mask=(1u<<RV_SD_E)|(1u<<RV_IO_E);r->flags[F_SD]=0;break;
    case 23:case 24:case 29:case 30:case 33:case 34:case 35:case 36:
        mask=(1u<<RV_MODE_E)|(1u<<RV_S_E)|(1u<<RV_VIEW_E);break;
    case 25:mask=(1u<<RV_POWER_E)|(1u<<RV_LINK_E);break;
    case 31:mask=(1u<<RV_IROM_E)|(1u<<RV_SD_E)|(1u<<RV_IO_E);break;
    case 32:mask=(1u<<RV_IROM_E)|(1u<<RV_IO_E)|(1u<<RV_UNIT_E);break;
    default:return;
    }
    if((h==11||h==12)&&rv_session(r)&&rv_session(r)->redraw) return;
    rv_ui_abort(r);rv_epochs(r,mask);
    if(mask&((1u<<RV_BOOT_E)|(1u<<RV_HEAP_E))) {
        r->reserved[0]=r->reserved[1]=0;r->image_address=0;r->lease=0;
        r->state=RV_FENCED;r->flags[F_STOP]=r->inflight!=0||r->fault==(uint32_t)RV_RANGE;
    } else if(mask&((1u<<RV_LINK_E)|(1u<<RV_UNIT_E)|(1u<<RV_SEG_E))) r->state=RV_FENCED;
    if(h==25||h==31||h==32) r->flags[F_STOP]=1;
    if(r->inflight&&(h==16||h==17||h==18||h==15)) r->fault=RV_UNCERTAIN;
    if(mask&(1u<<RV_IO_E)) {r->files[0].token=0;r->files[1].token=0;}
}
int32_t rv_unit(RvRoot *r,GxrceUnit *u)
{
    uint32_t epoch=r->epoch[RV_UNIT_E],link=r->epoch[RV_LINK_E],rx=r->flags[F_RX],address=rv_native_unit(1);const uint8_t *p;
    if((r->flags[F_RX]&1)||!address||!RV_WORD(0x2040f804)||!rv_native_rpc_ready()) return RV_STALE;
    p=RV_PTR(address);memcpy(u->name,p+4,8);u->main_version=rv_be16(p+0x30);u->cmp_version=rv_be16(p+0x32);
    return epoch==r->epoch[RV_UNIT_E]&&link==r->epoch[RV_LINK_E]&&rx==r->flags[F_RX]?RV_OK:RV_STALE;
}
int32_t rv_engine(RvRoot *r,uint32_t offset,RvRequest *q,RvReply *p)
{
    uint32_t irq=rv_irq_save();RvSession *s=rv_session(r);uint32_t boot=r->epoch[RV_BOOT_E],heap=r->epoch[RV_HEAP_E],address;int32_t result;
    if(!s||r->inflight||r->flags[F_STOP]||offset<s->code_begin||offset>s->code_end-4||(offset&3)) {rv_irq_restore(irq);return RV_FAULT;}
    q->version=1;q->bytes=64;q->flags=0;q->args[0]=r->lease;q->args[1]=r->lease;
    q->args[2]=boot;q->args[3]=heap;q->args[4]=r->epoch[RV_LINK_E];q->args[5]=r->epoch[RV_UNIT_E];
    q->args[6]=r->epoch[RV_VIEW_E];q->args[7]=r->epoch[RV_S_E];
    rv_clear(p,sizeof(*p));p->version=1;p->bytes=32;r->inflight=1;address=r->image_address+offset;rv_irq_restore(irq);
    result=rv_invoke(address,&rv_api,r->lease,q,p);
    r->inflight=0;
    if(boot!=r->epoch[RV_BOOT_E]||heap!=r->epoch[RV_HEAP_E]||!rv_session(r)||r->flags[F_STOP]||q->args[4]!=r->epoch[RV_LINK_E]||q->args[5]!=r->epoch[RV_UNIT_E]) return RV_FAULT;
    if(result<0||result>RV_FAULT||p->version!=1||p->bytes!=32) result=RV_FAULT;
    if(result>=RV_CLOSE_AND_PASS) rv_ui_abort(r);
    if(result==RV_FAULT) {r->state=RV_FENCED;r->fault=RV_FAULTED;}
    return result;
}
void rv_grain_commit(RvRoot *r,uint32_t mode,uint32_t enabled)
{
    uint32_t irq=rv_irq_save();r->flags[F_GRAIN]=r->state==RV_READY&&!r->flags[F_UNCERTAIN]&&enabled&&mode<=6 ? 0x100|mode:0;rv_irq_restore(irq);
}
void rv_grain(RvRoot *r,uint8_t *p)
{
    uint32_t g=r->flags[F_GRAIN],address=RV_WORD(0x200c0dac),size,level;
    const volatile uint8_t *s=RV_PTR(address);
    if(!g||r->state!=RV_READY||r->flags[F_UNCERTAIN]||!address||RV_WORD(0x200c0db0)<0xc9e||s[0x36e]!=(g&255)||
       (RV_BYTE(0x205d9a7f)!=0&&RV_BYTE(0x205d9a7f)!=4)||
       (p[0x1a]|p[0x14]|p[0x75]|p[0x1e]|p[0x26])) return;
    size=s[0x3aa];if(size>16||!((0x11126u>>size)&1))return;
    level=s[0xc9d];p[0x1a]=21;p[0x10]=0;p[0x32]=1;p[0x6f]=level-1<3?level:1;
}
#ifndef RV_HOST
int32_t rv_call(uint32_t id,uint32_t op,const RvRequest *q,RvReply *p)
{ return rv_service(RV_PTR(RV_ROOT),id,op,q,p); }
#else
int32_t rv_call(uint32_t id,uint32_t op,const RvRequest *q,RvReply *p)
{ return rv_service(rv_host_root,id,op,q,p); }
#endif
#define D(i,m) {i,64,m}
const RvApi rv_api={1,sizeof(RvApi),16,RV_READ_CAPS,512,rv_call,{0},
 {D(1,0x1fe),D(2,14),D(3,2),D(4,62),D(5,2),D(6,14),D(7,2),D(8,2),
  D(9,0x1fff),D(10,30),D(11,6),D(12,14),D(13,6),D(14,15),D(15,2),D(16,0)}};
