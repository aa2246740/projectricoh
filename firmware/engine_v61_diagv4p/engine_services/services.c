#include "engine_services.h"


static int header(const void *p,uint32_t n)
{ const RvBufferHeader *h=p;return n>=8&&h->version==1&&h->bytes==n&&!h->flags; }
static int identity(RvRoot *r,const RvRequest *q)
{
    GxrceUnit unit;const uint8_t *p=RV_PTR(0x2040f81c);
    memcpy(unit.name,p,8);unit.main_version=rv_be16(p+44);unit.cmp_version=rv_be16(p+46);
    return !(r->flags&RF_STOP)&&rv_session(r)&&rv_equal(&unit,&r->unit,sizeof(unit))&&q->args[0]==r->lease&&q->args[2]==r->epoch[RV_BOOT_E]&&
        q->args[3]==r->epoch[RV_HEAP_E];
}
static int current(RvRoot *r,const RvRequest *q)
{return identity(r,q)&&q->args[4]==r->epoch[RV_LINK_E]&&q->args[5]==r->epoch[RV_UNIT_E]&&
        q->args[6]==r->epoch[RV_VIEW_E]&&q->args[7]==r->epoch[RV_S_E];}

uint32_t rv_diag_snapshot_address(RvRoot *r)
{RvSession *s=rv_session(r);return s?s->context.state_address:0;}

void rv_settings_entry(RvRoot *r,unsigned entry)
{
    RvSession *s=rv_session(r);
    if(!s)return;
    s->context.input_fields=entry;s->context.input_sequence=r->entry_serial;
}
static RvUiSnapshot *ui_prepare(RvRoot *r)
{
    uint32_t address=rv_diag_snapshot_address(r);RvUiSnapshot *u=RV_PTR(address);
    if(r->ui_block||!address||!rv_range(r,r->lease,address,sizeof(*u)))return 0;
    return u;
}
static int ui_seed(RvRoot *r,RvUiSnapshot *u,uint32_t source)
{
    uint32_t table=RV_WORD(0x2022f720);
    (void)r;
    if(RV_BYTE(source)!=5||table<0x20000000u||table>0x20704800u-72||
       (RV_BYTE(0x2022f71c)!=5&&table!=0x2022f56c))return 0;
    memcpy(u->state,RV_PTR(0x2022f71c),32);memcpy(u->descriptors,RV_PTR(table),72);
    u->state[0]=5;
    RV_WORD((uint32_t)(uintptr_t)u+4)=(uint32_t)(uintptr_t)u+offsetof(RvUiSnapshot,descriptors);
    u->state[9]=RV_BYTE(source+9);u->state[10]=RV_BYTE(source+10);
    return 1;
}
static int32_t __attribute__((noinline)) ui_list(RvRoot *r,uint32_t op,RvUiList *u)
{
    RvSession *s=rv_session(r);RvUiSnapshot *native;uint32_t base,i,j,x,y,*lengths=s->ui_lengths,irq;
    if(op==4)return rv_ui_abort(r);
    if(!s||u->rows!=8||u->cursor>=u->rows||u->state_bytes<16||
       !rv_range(r,u->lease_token,u->state_address,u->state_bytes)||
       !rv_range(r,u->lease_token,u->label_table,u->rows*4)||
       !rv_range(r,u->lease_token,u->details,u->rows*12))return RV_RANGE;
    
    for(i=0;i<u->rows*3;++i)if(RV_WORD(u->details+4*i))return RV_UNSUPPORTED;
    for(i=0;i<u->rows;++i){
        x=RV_WORD(u->label_table+4*i);if(!rv_range(r,u->lease_token,x,4))return RV_RANGE;
        y=RV_WORD(x);
        for(j=0;j<96;++j){if(!rv_range(r,u->lease_token,y+j,1))return RV_RANGE;if(!RV_BYTE(y+j))break;}
        if(j==96)return RV_RANGE;
        lengths[i]=j+1;
    }
    if(op!=1&&(u->view_token!=r->epoch[RV_VIEW_E]||s->view_source!=u->state_address))return RV_STALE;
    native=ui_prepare(r);if(!native)return RV_IO;base=(uint32_t)(uintptr_t)native;
    irq=rv_irq_save();
    
    if(RV_WORD(0x205d9bf8)!=8||RV_WORD(0x205d9c00)!=56){rv_irq_restore(irq);return RV_STALE;}
    if(op==1) {
        uint32_t array=RV_WORD(0x205a27d8),count=RV_BYTE(0x205a27d4),top;
        
        if((!count&&(s->context.input_fields!=1||s->context.input_sequence!=r->entry_serial))||
           ((uint32_t)RV_BYTE(0x205a280f)-1u>1u)||
           array!=RV_NATIVE_VIEWS||count>2){rv_irq_restore(irq);return RV_STALE;}
        if(count){
            top=array+8*(count-1);
            if(!(count==1&&RV_BYTE(array)==32)&&
               (RV_BYTE(top)!=33||RV_WORD(top+4)!=0x2022f71c))
                {rv_irq_restore(irq);return RV_STALE;}
        }
        if(RV_WORD(0x2022f5a8)!=(r->ui_restore[0]?s->list:0x2022d610)||
           RV_BYTE(0x2022f5ac)!=(r->ui_restore[0]?8u:7u))
            {rv_irq_restore(irq);return RV_STALE;}
    }
    
    if((op==2||op==3)&&!rv_view_owned(r,u,0)){rv_irq_restore(irq);return RV_STALE;}
    
    if(!r->ui_restore[0]&&((uint32_t)RV_BYTE(0x2022f725)-1u>6u||(uint32_t)RV_BYTE(0x2022f726)-1u>6u))
        {rv_irq_restore(irq);return RV_CONFLICT;}
    if(!rv_ui_capture(r,op==1)){rv_irq_restore(irq);return RV_STALE;}
    if(!ui_seed(r,native,u->state_address)){rv_irq_restore(irq);return RV_UNAVAILABLE;}
    for(i=0;i<u->rows;++i){
        y=RV_WORD(RV_WORD(u->label_table+4*i));memcpy(native->glyphs[i],RV_PTR(y),lengths[i]);
        native->refs[i]=base+offsetof(RvUiSnapshot,glyphs)+96*i;
        native->labels[i]=base+offsetof(RvUiSnapshot,refs)+4*i;
    }
    s->view_source=u->state_address;s->view_state=base;s->view_lease=u->lease_token;
    s->list=base+offsetof(RvUiSnapshot,labels);s->details=base+offsetof(RvUiSnapshot,details);
    s->rows=u->rows;s->cursor=u->cursor;native->state[9]=native->state[10]=u->cursor+1;
    RV_BYTE(0x2022f725)=RV_BYTE(0x2022f726)=u->cursor+1;
    RV_WORD(base+offsetof(RvUiSnapshot,descriptors)+60)=s->list;
    RV_BYTE(base+offsetof(RvUiSnapshot,descriptors)+64)=u->rows;
    RV_WORD(base+offsetof(RvUiSnapshot,descriptors)+68)=0;
    r->ui_restore[6]=s->list;r->ui_restore[7]=s->details;
    RV_WORD(0x2022f5a8)=s->list;RV_BYTE(0x2022f5ac)=u->rows;
    u->view_token=r->epoch[RV_VIEW_E];rv_irq_restore(irq);
    if(op==3){
        irq=rv_irq_save();
        if(!rv_view_owned(r,u,0)){rv_irq_restore(irq);return RV_STALE;}
        s->redraw=1;rv_native_draw(2,s->view_state,0);
        if(rv_session(r))s->redraw=0;
        rv_irq_restore(irq);
    }
    return RV_OK;
}

int32_t rv_service(RvRoot *r,uint32_t id,uint32_t op,const RvRequest *q,RvReply *p)
{
    RvSession *s=rv_session(r);void *buffer=0;uint32_t bytes,a,b,i,x,used=0;int32_t result=RV_UNSUPPORTED;
    if(!q||!p||((uintptr_t)q&3)||((uintptr_t)p&3))return RV_ARGUMENT;
    rv_clear(p,32);p->version=1;p->bytes=32;
    if(q->version!=1||q->bytes!=64||q->flags){result=RV_ARGUMENT;goto finish;}
    
    if(id!=RV_UI_LIST&&id!=RV_UI_TEXT)goto finish;
    if(!current(r,q)){result=RV_STALE;goto finish;}
    if(!r->inflight||rv_native_context()!=0){result=RV_OWNER;goto finish;}
    if((r->flags&RF_OWNER)){result=RV_BUSY;goto finish;}
    s=rv_session(r);a=q->args[8];b=q->args[9];bytes=q->args[11];
    switch(id){
    case RV_UI_LIST:used=op==4?31:30;break;
    case RV_UI_TEXT:used=op==1?12:0;break;
    }
    for(i=0;i<6;++i)if(q->args[8+i]&&!(used&(1u<<i))){result=RV_ARGUMENT;goto finish;}
    if(q->args[13]||(q->args[12]&&id!=RV_UI_LIST)||(!bytes&&q->args[10])){result=RV_ARGUMENT;goto finish;}
    if(bytes) {
        if(!rv_range(r,q->args[1],q->args[10],bytes)||(q->args[10]&3)){result=RV_RANGE;goto finish;}
        buffer=RV_PTR(q->args[10]);
        if(!header(buffer,bytes)){result=RV_ARGUMENT;goto finish;}
    }
    r->flags|=RF_OWNER;
    switch(id) {
    case RV_UI_LIST:case RV_UI_TEXT:
        if(r->state!=RV_READY||!(s->capabilities&CAP_UI)){result=RV_CAPABILITY;break;}
        if(id==RV_UI_LIST&&op==4){
            x=bytes==40?((RvUiList *)buffer)->view_token:a;
            result=x==r->epoch[RV_VIEW_E]?rv_ui_abort(r):RV_STALE;
        }
        if(id==RV_UI_LIST&&op>=1&&op<=3&&bytes==40){
            RvUiList *u=buffer;
            result=b==u->rows&&(!q->args[12]||q->args[12]==u->rows)?ui_list(r,op,u):RV_ARGUMENT;
            if(!result){p->token=u->view_token;p->epoch=r->epoch[RV_VIEW_E];}
        }
        if(id==RV_UI_TEXT&&op==2){p->detail=rv_native_language();result=RV_OK;}
        if(id==RV_UI_TEXT&&op==1&&bytes==40) {
            RvUiText *u=buffer;
            if(!u->source_bytes||u->source_bytes>255||u->glyph_capacity<2*u->source_bytes+1||
               !rv_range(r,u->source_lease,u->source_address,u->source_bytes+1)||!rv_range(r,u->glyph_lease,u->glyph_address,u->glyph_capacity)){result=RV_RANGE;break;}
            for(i=0;i<u->source_bytes;++i){x=RV_BYTE(u->source_address+i);if(x<32||x>126)break;}
            if(i!=u->source_bytes||RV_BYTE(u->source_address+i)){result=RV_ARGUMENT;break;}
            if(u->source_address>=u->glyph_address?u->source_address-u->glyph_address<u->glyph_capacity:u->glyph_address-u->source_address<u->source_bytes+1){result=RV_ARGUMENT;break;}
            p->native_result=rv_native_ascii(RV_PTR(u->source_address),u->source_bytes,RV_PTR(u->glyph_address),u->language);
            if(!current(r,q)){result=RV_STALE;break;}
            if(p->native_result<0){result=RV_IO;break;}
            for(i=0;i<u->glyph_capacity&&RV_BYTE(u->glyph_address+i);++i){}
            if(i==u->glyph_capacity){result=RV_VERIFY;break;}
            u->actual_bytes=i+1;result=RV_OK;
        }break;
    }
    r->flags&=~RF_OWNER;
    if(!current(r,q))result=RV_STALE;
finish:
    p->status=result;return result;
}
