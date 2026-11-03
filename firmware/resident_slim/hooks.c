#include "resident.h"
extern const uint8_t rv_skip_01[],rv_skip_02[],rv_skip_05[],rv_skip_06[],rv_skip_07[],rv_skip_08[],rv_skip_10[];
extern const uint8_t rv_post_17[],rv_post_18[],rv_post_20[],rv_post_22[];
static int owned(RvRoot *r)
{
    uint32_t array=RV_WORD(0x205a27d8),count=RV_BYTE(0x205a27d4),state;
    RvSession *s=rv_session(r);
    if(!s||r->state!=RV_READY){rv_ui_abort(r);return 0;}
    if(!r->ui_restore[6]||RV_WORD(0x2022f5a8)!=r->ui_restore[6]||
       RV_WORD(0x205d9bf8)!=8||RV_WORD(0x205d9c00)!=56||RV_BYTE(0x205a280f)!=2||
       !array||count<1||count>2||RV_BYTE(array+8*(count-1))!=33)return 0;
    state=RV_WORD(array+8*(count-1)+4);
    if(state!=0x2022f71c&&state!=r->ui_restore[4]&&state!=s->view_state)return 0;
    return RV_BYTE(state)==5;
}
void rv_hook_observe(RvRoot *r,uint32_t hook,uint32_t *f)
{
    uint32_t h=hook&255,index=4;const uint8_t *post=0,*skip=0;RvSession *s;
    RvRequest q;RvReply reply;int32_t result=RV_PASS;
    rv_clear(&q,sizeof(q));
    if(r->magic!=RV_ROOT_MAGIC||r->version!=1)rv_reset(r);
    if(h-17<6){
        static const uint8_t indices[6]={0,1,4,2,4,3};
        static const uint8_t *const posts[4]={rv_post_17,rv_post_18,rv_post_20,rv_post_22};
        index=indices[h-17];if(index<4)post=posts[index];
    }
    if(hook&256){
        if(index<4){f[16]=r->post[index];r->post[index]=0;}
        rv_notify(r,h,1,(int32_t)f[15]);return;
    }
    if(index<4&&!((h==17||h==18)&&f[11]<2)){
        if(r->post[index]){r->flags|=RF_STOP;rv_record(r,h,2,0,0);}
        else {r->post[index]=f[16];f[16]=(uint32_t)(uintptr_t)post;}
    }
    if(h==9){rv_grain(r,RV_PTR(f[10]));return;}
    if(h>=11){
        if((h==11||h==12)&&(s=rv_session(r))&&s->redraw)return;
        rv_notify(r,h,0,(int32_t)f[11]);return;
    }
    rv_record(r,h,0,f[4],f[10]);
    if(h==1){
        if(r->state!=RV_READY||!(s=rv_session(r))||!rv_equal(s->bindings,r->epoch,48)){
            if(rv_load(r,&rv_trust))return;
        }
        s=rv_session(r);if(!s)return;
        result=rv_engine(r,s->entries.menu_open,&q,&reply);
        if(result==RV_CONSUMED&&owned(r)){f[15]=s->cursor;skip=rv_skip_01;}
    }else if(h==2&&owned(r)){f[7]=f[15];skip=rv_skip_02;}
    else if(h==5&&owned(r)){f[13]=r->ui_restore[7];skip=rv_skip_05;}
    else if(owned(r)&&!r->inflight){
        s=rv_session(r);if(!s)return;
        if(h==6){q.args[8]=0x25;result=rv_engine(r,s->entries.panel_open,&q,&reply);if(result==RV_CONSUMED){f[7]=0;skip=rv_skip_06;}}
        if(h==7){q.args[8]=h;q.args[9]=f[11];result=rv_engine(r,s->entries.event,&q,&reply);if(result==RV_CONSUMED){f[15]=0;skip=rv_skip_07;}}
        if(h==8){q.args[8]=RV_BYTE(0x2022f726);result=s->rows==16?rv_engine(r,s->entries.apply_step,&q,&reply):RV_CONSUMED;if(result==RV_CONSUMED){f[7]=0;skip=rv_skip_08;}}
        if(h==10){q.args[8]=f[4];q.args[9]=f[24];q.args[12]=f[25];q.args[13]=f[26];
            s->context.input_fields=15;++s->context.input_sequence;
            s->context.input[0]=f[4];s->context.input[1]=f[24];s->context.input[2]=f[25];s->context.input[3]=f[26];
            result=rv_engine(r,s->rows==16&&(f[4]==0x22||f[4]==0x25)?s->entries.panel_open:
                             s->rows==16?s->entries.event:s->entries.panel_event,&q,&reply);
            if(result==RV_CONSUMED)skip=rv_skip_10;
        }
    }
    if(skip)f[1]=(uint32_t)(uintptr_t)skip;
}
