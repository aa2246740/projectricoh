#include "engine_services.h"
int __attribute__((noinline)) rv_view_owned(RvRoot *r,const RvUiList *u,unsigned constructing)
{
    RvSession *s;uint32_t array,count,top,state;
    if(r->magic!=RV_ROOT_MAGIC||r->version!=RV_ROOT_VERSION||r->state!=RV_READY||
       (r->flags&(RF_STOP|RF_BUSY))||r->inflight!=1||!r->ui_restore[0]||
       !(s=rv_session(r))||u->lease_token!=r->lease||
       u->view_token!=r->epoch[RV_VIEW_E]||s->view_source!=u->state_address||
       s->view_lease!=u->lease_token||s->view_state!=rv_diag_snapshot_address(r)||
       r->ui_block||!rv_range(r,r->lease,s->view_state,sizeof(RvUiSnapshot))||
       s->list!=r->ui_restore[6]||s->rows!=u->rows||
       RV_WORD(0x2022f5a8)!=s->list||RV_BYTE(0x2022f5ac)!=s->rows||
       RV_WORD(0x205d9bf8)!=8||RV_WORD(0x205d9c00)!=56)return 0;
    
    if(RV_BYTE(0x205a280f)!=2&&RV_BYTE(0x205a280f)!=1)return 0;
    array=RV_WORD(0x205a27d8);count=RV_BYTE(0x205a27d4);
    if(array!=RV_NATIVE_VIEWS||count>2)return 0;
    if(!count)return constructing==1;
    if(constructing&&count==1&&RV_BYTE(array)==32)return 1;
    if(RV_BYTE(array+8*(count-1))!=33||(!constructing&&RV_WORD(0x2037f3bc)!=32))return 0;
    top=array+8*(count-1);state=RV_WORD(top+4);
    return state==0x2022f71c;
}
int32_t rv_native_seed(RvPrivateContext *c)
{
    uint32_t table=RV_WORD(0x2022f720);uint8_t *out;
    
    if(!c||c->ui_state_capacity<236||
       table<0x20000000u||table>0x20704800u-72||
       (RV_BYTE(0x2022f71c)!=5&&table!=0x2022f56c))return RV_UNAVAILABLE;
    out=RV_PTR(c->ui_state_address);
    memcpy(out,RV_PTR(0x2022f71c),32);memcpy(out+32,RV_PTR(table),72);
    out[0]=5;
    rv_clear(out+104,132);c->ui_state_bytes=236;return RV_OK;
}
