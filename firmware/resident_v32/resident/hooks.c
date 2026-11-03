#include "resident.h"
extern const uint8_t rv_skip_01[],rv_skip_02[],rv_skip_05[],rv_skip_06[],rv_skip_07[],rv_skip_08[],rv_close_07[];
/* These checks read resident records and native UI state only. In particular,
 * the shared H05 path never opens the session, samples code, or retires. */
static int owned(RvRoot *r)
{
    uint32_t array,count,state;
    if(r->magic!=RV_ROOT_MAGIC||r->version!=RV_ROOT_VERSION||r->state!=RV_READY||
       (r->flags&(RF_STOP|RF_BUSY))||!r->ui_restore[0]||
       RV_WORD(0x2022f5a8)!=r->ui_restore[6]||RV_WORD(0x205d9bf8)!=8||
       RV_WORD(0x205d9c00)!=56||RV_BYTE(0x205a280f)!=2)return 0;
    array=RV_WORD(0x205a27d8);count=RV_BYTE(0x205a27d4);
    if(array!=RV_NATIVE_VIEWS||count<1||count>2||RV_BYTE(array+8*(count-1))!=33)return 0;
    state=RV_WORD(array+8*(count-1)+4);
    return state==0x2022f71c||state==r->ui_block;
}
static void close_owned(RvRoot *r,uint32_t keep)
{
    if(keep)return;
    if(rv_ui_abort(r)!=RV_OK)return;
    /* Stage2l rfw_apply_action: hide layer 2, clear overlay, and withdraw
     * our cache. Do not execute the stock seven-item setter. */
    (void)rv_native_layer(2,1,0);RV_WORD(0x2037f3bc)=0;
}
void rv_hook_observe(RvRoot *r,uint32_t hook,uint32_t *f)
{
    uint32_t reason,row,offset,keep;const uint8_t *skip=0;RvSession *s;
    RvRequest *q;RvReply *reply;int32_t result;
    if(hook<1||hook>9||hook==3||hook==4)return;
    if(hook==9) {
        if(r->magic==RV_ROOT_MAGIC&&r->version==RV_ROOT_VERSION&&r->state==RV_READY&&r->grain)
            rv_grain(r,RV_PTR(f[10]));
        return;
    }
    if(hook==5) {
        if(owned(r)){f[13]=r->ui_restore[7];f[1]=(uint32_t)(uintptr_t)rv_skip_05;}
        return;
    }
    if(r->state==RV_DISABLED_UNTIL_REBOOT)return;
    if(r->magic!=RV_ROOT_MAGIC||r->version!=RV_ROOT_VERSION){
        if(hook!=1)return;
        /* Only an untouched flash-FF root is a cold initialization. */
        for(row=0;row<offsetof(RvRoot,pins);++row)if(((uint8_t *)r)[row]!=255)break;
        if(row!=offsetof(RvRoot,pins)){rv_retire(r,RV_CHECK_ROOT);return;}
        if(RV_BYTE(0x2022f5ac)>7&&RV_WORD(0x2022f5a8)!=0x2022d610) {
            uint32_t array=RV_WORD(0x205a27d8),count=RV_BYTE(0x205a27d4);
            RV_WORD(0x2022f5a8)=0x2022d610;RV_BYTE(0x2022f5ac)=7;
            RV_BYTE(0x2022f725)=RV_BYTE(0x2022f726)=1;
            if(array==RV_NATIVE_VIEWS&&count<=2)
                for(row=0;row<count;++row)if(RV_BYTE(array+8*row)==33)RV_WORD(array+8*row+4)=0x2022f71c;
            r->state=RV_DISABLED_UNTIL_REBOOT;return;
        }
        rv_reset(r);
    }
    if(r->inflight||(r->flags&RF_BUSY))return;
    reason=rv_check(r);if(reason){rv_retire(r,reason);return;}
    if(hook==1){
        if(r->state!=RV_READY&&rv_load(r,&rv_trust))return;
    }else if(!owned(r))return;
    s=rv_session(r);if(!s)return;
    q=&s->call_request;reply=&s->call_reply;rv_clear(q,sizeof(*q));
    if(hook==1){
        result=rv_engine(r,s->entries.menu_open,q,reply);
        if(result==RV_CONSUMED&&owned(r)){f[15]=s->cursor+1;skip=rv_skip_01;}
    }else if(hook==2){f[7]=s->cursor+1;skip=rv_skip_02;}
    else {
        keep=hook==7?f[11]:1;
        q->args[12]=f[16];q->args[13]=f[7];
        if(hook==6){q->args[8]=0x25;offset=s->entries.panel_open;skip=rv_skip_06;}
        else if(hook==7){q->args[8]=7;q->args[9]=keep;offset=s->entries.event;skip=rv_skip_07;}
        else {
            row=RV_BYTE(0x2022f726);skip=rv_skip_08;
            if(row<1||row>s->rows){rv_retire(r,RV_CHECK_UI);f[7]=0;f[1]=(uint32_t)(uintptr_t)skip;return;}
            q->args[8]=row-1;offset=s->entries.apply_step;
        }
        result=rv_engine(r,offset,q,reply);
        if(result==RV_PASS||result==RV_CLOSE_AND_PASS||result==RV_FAULT){
            if(hook==7)(void)rv_ui_abort(r);else close_owned(r,0);
            /* Stock replay is allowed only after its own rows are restored. */
            if(result==RV_PASS&&hook!=7&&r->state!=RV_DISABLED_UNTIL_REBOOT)skip=0;
        }else if(hook==7&&keep==0)(void)rv_ui_abort(r);
        if(hook==7&&(result==RV_CLOSE_AND_PASS||result==RV_FAULT||keep==0))skip=rv_close_07;
        if(hook==7)f[15]=1;else if(skip)f[7]=0;
    }
    if(skip)f[1]=(uint32_t)(uintptr_t)skip;
}
