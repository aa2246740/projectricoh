#include "resident.h"
extern const uint8_t rv4_skip_01[],rv4_skip_02[],rv4_skip_05[],rv4_skip_06[],rv4_skip_08[],rv4_close_07[],rv4_keep_07[];
static __attribute__((noinline)) void safe(uint32_t hook,uint32_t *frame)
{
    static const uint8_t *const continuation[3]={rv4_skip_06,rv4_close_07,rv4_skip_08};
    if(hook-6<=2){frame[1]=RV4_ADDRESS(continuation[hook-6]);frame[7]=0;}
}
void rv4_hook_observe(Rv4Root *r,uint32_t hook,uint32_t *frame)
{
    Rv4Event event;Rv4Reply reply;uint32_t irq,protect,ticket;int32_t result;
    if(!frame||hook<1||hook>38||hook==3||hook==4)return;
    irq=rv4_irq_save();
    ticket=rv4_root_valid(r)?r->view.ticket:0;protect=rv4_protect(r,ticket);
    /* Decide this native frame's safe continuation before retire can restore 7 rows. */
    if(protect)safe(hook,frame);
    rv4_irq_restore(irq);
    if(hook==5){
        if(protect){frame[13]=rv4_details(r,ticket);frame[1]=RV4_ADDRESS(rv4_skip_05);}
        return;
    }
    if(!rv4_root_valid(r)){
        if(hook!=1||rv4_cold_init(r))return;
    }
    if(hook==23){(void)rv4_load(r,&rv4_trust);return;}
    if(hook>=10){
        /* Zero means no implemented native protocol, not a DAT delegation. */
        static const uint8_t route[39]={
            [13]=1,[14]=1,[15]=2,[17]=3,[18]=3,[19]=4,[20]=5,[28]=3,[34]=4
        };
        uint32_t action=route[hook];
        if(action==1)(void)rv4_ui_mutation(r,ticket);
        else if(action>=2&&action<=4){
            static const uint8_t epoch[3]={RV4_E_HEAP,RV4_E_UNIT,RV4_E_MEDIA};
            (void)rv4_invalidate(r,epoch[action-2]);
        }else if(action==5)rv4_retire(r,RV4_STALE);
        return;
    }
    if(hook==9)return; /* The original sender and RAW gates replay unchanged. */
    if(r->header.inflight||r->header.state!=RV4_READY||(r->header.flags&RV4_STOP))return;
    if(hook==2){
        if(rv4_binding(r)){rv4_retire(r,RV4_STALE);return;}
        if(ticket){frame[7]=1;frame[1]=RV4_ADDRESS(rv4_skip_02);}
        return;
    }
    rv4_clear(&event,sizeof(event));event.version=4;event.bytes=64;
    event.event=hook==1?RV4_ENTRY_MENU_PREPARE:RV4_ENTRY_INPUT;
    event.session_token=r->header.session_token;event.session_generation=r->image.generation;
    event.view_generation=r->epochs[RV4_E_VIEW];event.owner_context=RV4_CONTEXT_UI;
    event.native_event=hook==6?0x25:frame[7];event.native_caller=frame[16];
    event.args[0]=ticket;
    result=rv4_dispatch(r,hook,&event,&reply);
    if(result)return;
    if(hook==1&&reply.action==RV4_ACTION_CONSUME&&r->view.ticket){
        frame[15]=1;frame[1]=RV4_ADDRESS(rv4_skip_01);
    }else if(hook==7){
        if(reply.action==RV4_ACTION_KEEP_PANEL&&r->view.ticket&&
           !rv4_binding(r)&&r->view.ticket==ticket){frame[1]=RV4_ADDRESS(rv4_keep_07);}
        else{(void)rv4_view_withdraw(r,r->view.ticket);frame[1]=RV4_ADDRESS(rv4_close_07);}
    }else if(protect)safe(hook,frame);
}
