#include "resident.h"
/* Callers check their pointer boundary before this shared wire-identity check. */
int rv4_event_identity(const Rv4Root *r,const Rv4Event *q,uint32_t kind,uint32_t context)
{
    return q->version==4&&q->bytes==64&&q->event==kind&&!q->flags&&
        q->session_token==r->header.session_token&&q->session_generation==r->image.generation&&
        q->owner_context==context;
}
int32_t rv4_dispatch(Rv4Root *r,uint32_t hook,const Rv4Event *event,Rv4Reply *reply)
{
    uint32_t slot;int32_t result;
    if(!rv4_root_valid(r)||!event||!reply)return RV4_ARGUMENT;
    if(hook==1)slot=RV4_ENTRY_MENU_PREPARE;
    else if(hook-6<=2)slot=RV4_ENTRY_INPUT;
    else return RV4_UNSUPPORTED;
    result=rv4_call(r,slot,RV4_CONTEXT_UI,event,reply);if(result)return result;
    if(reply->action==RV4_ACTION_KEEP_PANEL&&
       (hook!=7||!(r->header.capabilities&RV4_CAP_UI_KEEP_OK)||event->native_event!=0x23||
        (event->native_caller!=0x202c2d74&&event->native_caller!=0x202c2d84)))return RV4_UNSUPPORTED;
    return RV4_OK;
}
int32_t rv4_host_call(uint32_t service,uint32_t token,const Rv4Event *event,Rv4Reply *reply)
{
    Rv4Root *r=RV4_PTR(RV4_ROOT_ADDRESS);uint32_t task,bytes,operation;int32_t result;Rv4Event request;
    if(!rv4_root_valid(r)||!event||!reply||service<1||service>8)return RV4_ARGUMENT;
    bytes=r->image.file_bytes+r->image.bss_bytes;
    if(!rv4_span(RV4_ADDRESS(event),64,r->image.base,bytes)||
       !rv4_span(RV4_ADDRESS(reply),32,r->image.base+r->image.file_bytes,r->image.bss_bytes)||
       ((RV4_ADDRESS(event)|RV4_ADDRESS(reply))&3))return RV4_RANGE;
    if(!rv4_event_identity(r,event,service,r->header.state==RV4_VALIDATED?RV4_CONTEXT_INIT:RV4_CONTEXT_UI)||
       event->session_token!=token)return RV4_ARGUMENT;
    task=rv4_native_context();
    if(!task||!r->header.inflight||task!=r->header.owner||rv4_binding(r))return RV4_STALE;
    if(r->header.state==RV4_VALIDATED&&service!=RV4_SERVICE_QUERY)return RV4_UNSUPPORTED;
    request=*event;event=&request;
    rv4_clear(reply,sizeof(*reply));reply->version=4;reply->bytes=32;
    operation=event->phase;result=RV4_UNSUPPORTED;
    if(service==RV4_SERVICE_QUERY&&operation==0){
        reply->actual=r->header.state==RV4_VALIDATED?RV4_CAP_QUERY:r->header.capabilities;
        reply->token=token;reply->observed_generation=r->image.generation;reply->detail=r->header.state==RV4_VALIDATED?1:0xb;
        result=RV4_OK;
    }else if(service==RV4_SERVICE_CONTEXT&&operation==0){
        reply->actual=task;reply->observed_generation=r->epochs[RV4_E_HEAP];result=RV4_OK;
    }else if(service==RV4_SERVICE_VIEW&&task==rv4_native_profile.ui_owner&&
             (r->header.capabilities&RV4_CAP_UI_PUBLISH)){
        if(event->view_generation!=r->epochs[RV4_E_VIEW])return RV4_STALE;
        if(operation==1){
            if(!rv4_span(event->args[0],sizeof(Rv4ViewInput),r->image.base,bytes))return RV4_RANGE;
            result=rv4_view_publish(r,RV4_PTR(event->args[0]),&reply->token);
        }else if(operation==2)result=rv4_view_withdraw(r,event->args[0]);
        else if(operation==3)result=rv4_view_draw(r,event->args[0],event->args[1]);
    }
    reply->status=result;return result;
}
