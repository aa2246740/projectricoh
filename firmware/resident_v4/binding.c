#include "resident.h"
int rv4_root_valid(const Rv4Root *r)
{return r&&r->header.magic==RV4_ROOT_MAGIC&&r->header.version==4;}
int32_t rv4_cold_init(Rv4Root *r)
{
    uint32_t i,irq;
    if(!r)return RV4_ARGUMENT;
    irq=rv4_irq_save();
    /* Warm/unknown roots are never reset, including a root with old pins. */
    for(i=0;i<offsetof(Rv4Root,pins);++i)if(((const uint8_t *)r)[i]!=255){rv4_irq_restore(irq);return RV4_STALE;}
    for(i=0;i<3;++i)if(r->pins[i]!=rv4_pins[i]){rv4_irq_restore(irq);return RV4_IDENTITY;}
    for(i=0;i<5;++i)if(r->reserved[i]!=~0u){rv4_irq_restore(irq);return RV4_STALE;}
    rv4_clear(r,offsetof(Rv4Root,pins));
    for(i=0;i<12;++i)r->epochs[i]=1;
    r->header.version=4;r->header.boot_instance=1;r->header.next_token=1;
    if(RV4_WORD(RV4_UI_NAMES)==RV4_STOCK_NAMES&&RV4_BYTE(RV4_UI_ROWS)==7)r->header.flags=RV4_RESTORED;
    r->header.magic=RV4_ROOT_MAGIC;RV4_BARRIER();rv4_irq_restore(irq);return RV4_OK;
}
int32_t rv4_binding(Rv4Root *r)
{
    uint32_t unit[3];Rv4Image *a;
    if(!rv4_root_valid(r))return RV4_STALE;
    a=&r->image;
    if((r->header.flags&RV4_STOP)||!r->header.session_token||!a->base||a->inverse!=~a->base||
       a->heap_epoch!=r->epochs[RV4_E_HEAP]||a->link_epoch!=r->epochs[RV4_E_LINK]||
       a->heap_begin!=RV4_WORD(RV4_HEAP_BEGIN)||a->heap_end!=RV4_WORD(RV4_HEAP_END)||
       a->file_bytes<256||a->file_bytes>RV4_MAX_FILE||a->bss_bytes>RV4_MAX_IMAGE_BSS-a->file_bytes||
       !rv4_allocation(a->base,a->file_bytes+a->bss_bytes,a->alloc_bytes)||
       a->code_bytes<4||a->code_bytes>RV4_MAX_CODE||a->code_offset<256||(a->code_offset&3)||
       !rv4_span(a->base+a->code_offset,a->code_bytes,a->base,a->file_bytes))return RV4_STALE;
    rv4_native_unit(unit);
    if(!rv4_equal(unit,&a->unit_name0,12)||
       rv4_crc(RV4_PTR(a->base+a->code_offset),a->code_bytes)!=a->code_crc)return RV4_STALE;
    return RV4_OK;
}
void rv4_retire(Rv4Root *r,int32_t reason)
{
    uint32_t irq;
    if(!rv4_root_valid(r))return;
    irq=rv4_irq_save();r->header.flags|=RV4_STOP|RV4_ATTEMPTED|RV4_RESTORING;
    r->header.state=RV4_DISABLED;r->header.capabilities=0;r->header.fault=(uint32_t)reason;
    if(r->view.ticket)r->view.retiring=r->view.ticket;
    r->draw.pending=1;r->job.cancel=1;RV4_BARRIER();rv4_irq_restore(irq);
    /* Keep image anchors and all old pins until their actual returns. */
    (void)rv4_view_withdraw(r,r->view.ticket);
}
int32_t rv4_invalidate(Rv4Root *r,uint32_t epoch)
{
    uint32_t irq;
    if(!rv4_root_valid(r)||epoch>=12)return RV4_ARGUMENT;
    irq=rv4_irq_save();r->header.flags|=RV4_STOP|RV4_RESTORING;
    if(r->epochs[epoch]!=~0u)++r->epochs[epoch];
    r->header.state=RV4_DISABLED;rv4_irq_restore(irq);
    rv4_retire(r,RV4_STALE);return RV4_STALE;
}
int32_t rv4_call(Rv4Root *r,uint32_t slot,uint32_t context,const Rv4Event *q,Rv4Reply *p)
{
    Rv4Event event;Rv4HostApi host;uint32_t irq,token,owner,address,ticket;
    int32_t result;
    if(!rv4_root_valid(r)||!q||!p||slot>=12)return RV4_ARGUMENT;
    if(slot>=RV4_ENTRY_CAPTURE_INTENT&&slot<=RV4_ENTRY_UI_RENDER)return RV4_UNSUPPORTED;
    if(context!=(slot==RV4_ENTRY_INIT?RV4_CONTEXT_INIT:RV4_CONTEXT_UI))return RV4_ARGUMENT;
    if(!rv4_event_identity(r,q,slot,context)||q->phase>1||
       q->view_generation!=r->epochs[RV4_E_VIEW])return RV4_ARGUMENT;
    if(rv4_binding(r)){rv4_retire(r,RV4_STALE);return RV4_STALE;}
    if((slot==RV4_ENTRY_INIT&&r->header.state!=RV4_VALIDATED)||
       (slot!=RV4_ENTRY_INIT&&r->header.state!=RV4_READY))return RV4_STALE;
    address=r->entries[slot];
    if(!address)return RV4_UNSUPPORTED;
    if((address&3)||address<r->image.code_offset||address>r->image.code_offset+r->image.code_bytes-4){rv4_retire(r,RV4_LAYOUT);return RV4_LAYOUT;}
    event=*q;rv4_clear(p,sizeof(*p));p->version=4;p->bytes=32;
    rv4_clear(&host,sizeof(host));host.major=4;host.header_bytes=32;host.descriptor_bytes=16;
    host.total_bytes=32;host.capabilities_low=slot==RV4_ENTRY_INIT?RV4_CAP_QUERY:r->header.capabilities;
    host.host_call=RV4_ADDRESS(rv4_host_call);host.session_token=r->header.session_token;
    irq=rv4_irq_save();owner=rv4_native_context();
    if(!owner||r->header.inflight||(r->header.flags&RV4_STOP)||
       (context==RV4_CONTEXT_UI&&owner!=rv4_native_profile.ui_owner)||
       (context==RV4_CONTEXT_INIT&&owner!=rv4_native_profile.task8_owner)){
        rv4_irq_restore(irq);return owner?RV4_BUSY:RV4_UNKNOWN;
    }
    if(r->header.serial==~0u||r->draw.frame_pins==~0u){rv4_irq_restore(irq);rv4_retire(r,RV4_RANGE);return RV4_RANGE;}
    ++r->header.serial;r->header.inflight=1;r->header.owner=owner;token=r->header.session_token;
    ticket=r->view.ticket;if(ticket)++r->draw.frame_pins;
    RV4_BARRIER();rv4_irq_restore(irq);
    result=rv4_invoke(r->image.base+address,&host,token,&event,p);
    irq=rv4_irq_save();r->header.inflight=0;r->header.owner=0;
    if(ticket&&r->draw.frame_pins)--r->draw.frame_pins;
    rv4_irq_restore(irq);
    if(rv4_binding(r)||r->header.session_token!=token||rv4_native_context()!=owner||
       p->version!=4||p->bytes!=32||p->action>RV4_ACTION_KEEP_PANEL||p->token!=token||
       p->observed_generation!=r->image.generation||result||p->status){
        rv4_retire(r,RV4_STALE);return RV4_STALE;
    }
    rv4_ui_drain(r);return RV4_OK;
}
