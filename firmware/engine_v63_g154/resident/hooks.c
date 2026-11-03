#include "resident.h"
extern const uint8_t rv_skip_01[],rv_skip_02[],rv_skip_05[],rv_skip_06[],rv_skip_07[],rv_skip_08[],rv_close_07[];
/* These checks read resident records and native UI state only. In particular,
 * the shared H05 path never opens the session, samples code, or retires. */
static int owned(RvRoot *r,uint32_t hook)
{
    uint32_t array,count,state;
    if(r->magic!=RV_ROOT_MAGIC||r->version!=RV_ROOT_VERSION||r->state!=RV_READY||
       (r->flags&(RF_STOP|RF_BUSY))||!r->ui_restore[0]||
       RV_WORD(0x2022f5a8)!=r->ui_restore[6]||RV_WORD(0x205d9bf8)!=8||
       RV_WORD(0x205d9c00)!=56)return 0;
    /* Part 2 is the menu layer. Part 1 is the shooting layer left active
     * while this same Image list is rebuilt. Part 0 and part 4 stay rejected,
     * and every stack / name / activity check below still has to pass. */
    if(RV_BYTE(0x205a280f)!=2&&RV_BYTE(0x205a280f)!=1)return 0;
    array=RV_WORD(0x205a27d8);count=RV_BYTE(0x205a27d4);
    if(array!=RV_NATIVE_VIEWS||count>2)return 0;
    /* H01/H02 precede the Image tag-33 push. */
    if(hook<=2){if(!count)return RV_BYTE(0x2022f5ac)==8;if(count==1&&RV_BYTE(array)==32)return 1;}
    else if(!count)return 0;
    if(RV_BYTE(array+8*(count-1))!=33)return 0;
    state=RV_WORD(array+8*(count-1)+4);
    return state==0x2022f71c||state==r->ui_block;
}
/* The entry validates the root before every early() call. H07 retains
 * its published-session close. H06/H08 may skip only while eight rows are
 * live; rv_check failure calls early() before retire restores seven rows.
 * The entry filter leaves only H01,H02,H06,H07,H08 for this helper. */
static void __attribute__((noinline)) early(RvRoot *r,uint32_t hook,uint32_t *f)
{
    const uint8_t *skip;
    if(!(r->flags&RF_PUBLISHED))return;
    if(hook==7)skip=rv_close_07;
    else {
        if(RV_BYTE(0x2022f5ac)!=8)return;
        if(hook<6)return;
        skip=hook==6?rv_skip_06:rv_skip_08;
        f[7]=0;
    }
    f[1]=(uint32_t)(uintptr_t)skip;
}
static void close_owned(RvRoot *r,uint32_t keep)
{
    if(keep)return;
    if(rv_ui_abort(r)!=RV_OK)return;
    /* Stage2l rfw_apply_action: hide layer 2, clear overlay, and withdraw
     * our cache. Do not execute the stock seven-item setter. */
    (void)rv_native_layer(2,1,0);RV_WORD(0x2037f3bc)=0;
}
/* ---- Body entries (H09, H10, H40/H41), r7 contract (resident side):
 * - One lane. inflight is the only owner: it is tested before a request is
 *   written (ui_call, image_hook) and claimed again under IRQ in rv_engine.
 *   UI entries (H09/H10, task 6) use call_request/call_reply; H40/H41 use
 *   image_request/image_reply. All entries receive the session's private
 *   context in args[10..11] and epoch[0,1,2,3,6,7] frozen in args[2..7].
 * - H09/H10/H40 reach the DAT only while READY and CAP_BODY is published.
 *   H10 passes the event code by value (args[9]); a code < 256 returned in
 *   reply.detail on CONSUMED replaces r11. H09 passes the 144 B parameter
 *   block address; edits come back by value and are applied only on CONSUMED.
 * - H40: args[9]=K, args[12]=native SP (outer return address at +4),
 *   args[13]=r0. H41: args[13]=the encoder status word 0x201BC3AC. The
 *   resident saves K+0x14C..0x15B and K+0x190..0x19B and puts them back
 *   unless the DAT returns CONSUMED with detail IMG_REPLY_DONE.
 * - If the DAT stored IMG_TOUCHED and did not return DONE, the encoder is
 *   skipped (r0=0, the trampoline returns -1) and IMG_LATCH keeps H40/H41 on
 *   the stock path until reboot. This closure needs no working DAT. */
static __attribute__((noinline)) RvSession *body_ready(RvRoot *r)
{
    RvSession *s=r->state==RV_READY&&!(r->flags&(RF_STOP|RF_BUSY))?rv_session(r):0;
    return s&&(s->capabilities&CAP_BODY)?s:0;
}
static int32_t ui_call(RvRoot *r,RvSession *s,uint32_t hook,uint32_t value)
{
    RvRequest *q=&s->call_request;
    if(r->inflight)return RV_BUSY;
    rv_clear(q,sizeof(*q));q->args[8]=hook;q->args[9]=value;
    return rv_engine(r,s->entries.panel_event,q,&s->call_reply);
}
static void image_hook(RvRoot *r,uint32_t hook,uint32_t *f)
{
    RvSession *s=body_ready(r);RvRequest *q;uint32_t k=f[7],st=r->image_state,*save;int32_t res;
    if(!s||st>=IMG_LATCH||r->inflight||(hook==41&&st!=IMG_DONE)||k-0x205757a4u>=18u*588u)return;
    /* K, native sp (outer caller frame) and r0 / encoder status by value. The DAT stores only
     * IMG_TOUCHED into the fixed root word before its first pixel write. */
    q=&s->image_request;rv_clear(q,sizeof(*q));save=s->k_save;
    q->args[8]=hook;q->args[9]=k;/* args[10..11] belong to rv_engine (private context); image values use
     * args[12] = native SP (outer return address at +4) and args[13] = r0 at
     * H40 / the encoder status word at H41 (the wrapper itself returns 0). */
    q->args[12]=(uint32_t)(uintptr_t)f+68;q->args[13]=hook==40?f[15]:RV_WORD(0x201bc3ac);
    if(hook==40){memcpy(save,RV_PTR(k+0x14c),16);memcpy(save+4,RV_PTR(k+0x190),12);r->image_state=IMG_ENTERED;}
    res=rv_engine(r,s->entries.panel_abort,q,&s->image_reply);
    st=r->image_state;r->image_state=IMG_IDLE;
    if(hook==41)return;
    if(res==RV_CONSUMED&&s->image_reply.detail==IMG_REPLY_DONE)r->image_state=IMG_DONE;
    else if(st==IMG_TOUCHED){f[15]=0;r->image_state=IMG_LATCH;}
    else {memcpy(RV_PTR(k+0x14c),save,16);memcpy(RV_PTR(k+0x190),save+4,12);}
}
/* H09: the DAT reads the 144 B block and answers with up to 8 byte edits
 * (u16 offset<<8|value in reply.actual..capabilities, count in detail). The
 * resident applies them only on CONSUMED, so a failing DAT changes nothing. */
static void h09(RvRoot *r,uint32_t *f)
{
    RvSession *s=body_ready(r);uint32_t i,e;uint8_t *p=RV_PTR(f[10]);
    if(!s||ui_call(r,s,9,f[10])!=RV_CONSUMED||s->call_reply.detail>8)return;
    for(i=0;i<s->call_reply.detail;++i){
        e=(&s->call_reply.actual)[i>>1]>>(i&1?0:16);
        if((e>>8&255)<144)p[e>>8&255]=(uint8_t)e;
    }
}
static void h10(RvRoot *r,uint32_t *f)
{
    RvSession *s=body_ready(r);
    if(s&&ui_call(r,s,10,f[4])==RV_CONSUMED&&s->call_reply.detail<256)f[4]=s->call_reply.detail;
}
__attribute__((optimize("no-jump-tables")))
void rv_hook_observe(RvRoot *r,uint32_t hook,uint32_t *f)
{
    uint32_t reason,row,offset,keep;const uint8_t *skip=0;RvSession *s;
    RvRequest *q;RvReply *reply;int32_t result;
    uint32_t view=RV_WORD(0x205d9c00);
    if(hook>=40){image_hook(r,hook,f);return;}
    if(hook==9){h09(r,f);return;}
    /* H10 is inert outside standby (5) and the Image list (56): no root
     * initialization, retire, load or DAT call in start-up/update states. */
    if(hook==10){if(view==5||view==56)h10(r,f);return;}
    if(hook<1||hook==3||hook==4)return;
    if(hook==5) {
        if(owned(r,hook)){f[13]=r->ui_restore[7];f[1]=(uint32_t)(uintptr_t)rv_skip_05;}
        return;
    }
    if(r->magic!=RV_ROOT_MAGIC||r->version!=RV_ROOT_VERSION){
        if(hook!=1||r->state==RV_DISABLED_UNTIL_REBOOT)return;
        /* Only an untouched flash-FF root is a cold initialization.
         * The loaded image already has the stock 7-row list at 0x2022f5a8,
         * so a cold root cannot observe a published 8-row list. */
        for(row=0;row<offsetof(RvRoot,pins);++row)if(((uint8_t *)r)[row]!=255)break;
        if(row!=offsetof(RvRoot,pins)){rv_retire(r,RV_CHECK_ROOT);return;}
        rv_reset(r);
    }
    if(r->state==RV_DISABLED_UNTIL_REBOOT){early(r,hook,f);return;}
    if(r->inflight||(r->flags&RF_BUSY)){early(r,hook,f);return;}
    reason=rv_check(r);if(reason){early(r,hook,f);rv_retire(r,reason);return;}
    if(hook==1){
        if(r->state!=RV_READY&&rv_load(r,&rv_trust))return;
    }else if(!owned(r,hook)){early(r,hook,f);return;}
    s=rv_session(r);if(!s){early(r,hook,f);return;}
    q=&s->call_request;reply=&s->call_reply;rv_clear(q,sizeof(*q));
    if(hook==1){
        result=rv_engine(r,s->entries.menu_open,q,reply);
        if(result==RV_CONSUMED&&owned(r,hook)){f[15]=s->cursor+1;skip=rv_skip_01;}
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
