#include "resident.h"
extern const uint8_t rv_skip_01[],rv_skip_02[],rv_skip_05[],rv_skip_06[],rv_skip_07[],rv_skip_08[];
static RvSession *owned(RvRoot *r)
{
    uint32_t array=RV_WORD(0x205a27d8),count=RV_BYTE(0x205a27d4),state;
    RvSession *s=rv_session(r);
    if(!s||r->state!=RV_READY){rv_ui_abort(r);return 0;}
    if(!r->ui_restore[6]||RV_WORD(0x2022f5a8)!=r->ui_restore[6]||
       RV_WORD(0x205d9bf8)!=8||RV_WORD(0x205d9c00)!=56||RV_BYTE(0x205a280f)!=2||
       !array||count<1||count>2||RV_BYTE(array+8*(count-1))!=33)return 0;
    state=RV_WORD(array+8*(count-1)+4);
    if(state!=0x2022f71c&&state!=r->ui_restore[4]&&state!=s->view_state)return 0;
    return RV_BYTE(state)==5?s:0;
}
void rv_hook_observe(RvRoot *r,uint32_t hook,uint32_t *f)
{
    uint32_t reason;const uint8_t *skip=0;RvSession *s;
    RvRequest q;RvReply reply;int32_t result=RV_PASS;
    if(hook<1||hook>9||hook==3||hook==4)return;
    if(r->magic!=RV_ROOT_MAGIC||r->version!=RV_ROOT_VERSION){
        if(hook!=1)return;
        rv_retire(r,RV_CHECK_ROOT);rv_reset(r);
    }
    if(r->inflight||(r->flags&RF_BUSY))return;
    reason=rv_check(r);
    if(reason)rv_retire(r,reason);
    if(hook==9){rv_grain(r,RV_PTR(f[10]));return;}
    rv_clear(&q,sizeof(q));rv_record(r,hook,0,f[4],f[10]);
    if(hook==1){
        if(r->state!=RV_READY||!(s=rv_session(r))){if(rv_load(r,&rv_trust))return;}
        s=rv_session(r);if(!s)return;
        result=rv_engine(r,s->entries.menu_open,&q,&reply);
        if(result==RV_CONSUMED&&(s=owned(r))){f[15]=s->cursor;skip=rv_skip_01;}
    }else if(hook==2&&owned(r)){f[7]=f[15];skip=rv_skip_02;}
    else if(hook==5&&owned(r)){f[13]=r->ui_restore[7];skip=rv_skip_05;}
    else if((s=owned(r))){
        /* H10 is excluded. A panel cannot receive a full key stream, so Fn2
         * remains a consumed list guard until a replacement route is chosen. */
        if(hook==6){
            if(!(s->capabilities&(CAP_S|CAP_W|CAP_FILE_WRITE))){q.args[8]=0x25;(void)rv_engine(r,s->entries.panel_open,&q,&reply);}
            f[7]=0;skip=rv_skip_06;
        }
        if(hook==7){q.args[8]=7;q.args[9]=f[11];result=rv_engine(r,s->entries.event,&q,&reply);
            if(result<=RV_CONSUMED){f[15]=0;skip=rv_skip_07;}}
        if(hook==8){q.args[8]=RV_BYTE(0x2022f726);result=s->rows==16?
            rv_engine(r,s->entries.apply_step,&q,&reply):RV_CONSUMED;
            if(result==RV_CONSUMED){f[7]=0;skip=rv_skip_08;}}
    }
    if(skip)f[1]=(uint32_t)(uintptr_t)skip;
}
