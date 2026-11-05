"""Retain the g156 complete transaction; separate readback and annotate skips."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
C.setup();P=C.PRODUCT
p=P/'src/firmware/engine/core/eng_boot.inc.c'
s=p.read_text().replace('g.','g->')
end=s.index('static int boot_s_valid')
s='''/* Shared read path: no native colour eligibility is consulted here. */
static unsigned memory_decode(const uint8_t p[40],EngRecipeRef *ref,UvLevels *t,unsigned *user)
{
    const uint8_t *entry;unsigned index=p[5],i;
    for(i=0;i<40&&!p[i];++i){}if(i==40)return 2;
    if(!memory_owned(p,eng_crc(p,36)))return 5;
    if(p[4]!=MEMORY_VERSION||!equal(p+28,g->data.image+20,8))return 3;
    if(p[6]!=g->data.unit)return 4;
    clear(ref,sizeof(*ref));*user=0;ref->unit=g->data.unit;
    if(index>=1&&index<=8)ref->slot=(uint8_t)index;
    else if(index>=MEMORY_FX_FIRST&&index<MEMORY_FX_FIRST+GXR2_FX_MAX){
        index-=MEMORY_FX_FIRST;entry=fx_entry(&g->data.view,index);
        if(!entry||!(entry[18]>>g->data.unit&1u))return 4;
        ref->slot=entry[0];ref->effect=(uint8_t)(index+1);copy(ref->effect_crc,entry+4,4);
    }else if(index>=MEMORY_USER_FIRST&&index<MEMORY_USER_FIRST+MEMORY_USERS){
        index-=MEMORY_USER_FIRST;entry=uv_user(&g->data.view,index);
        if(!entry)return 5;
        ref->slot=entry[0];*user=index+1;
    }else return 5;
    eng_identity(eng_record(&g->data,ref->slot),ref->identity);copy(t,p+8,sizeof(*t));
    if(kv_data_request(&g->data.knobs,g->data.unit,ref->slot,t,&g->work.request))return 6;
    memory_build(g->staging,ref,t,*user);
    return equal(p,g->staging,40)?1:5;
}
void eng_read_saved(void)
{
    EngRecipeRef ref;UvLevels levels;unsigned user=0;uint8_t record[40];int32_t status;
    if(g->restore_done)return;
    g->memory_result=7;
    clear(&io.info,sizeof(io.info));io.info.header.version=1;io.info.header.bytes=sizeof(io.info);
    status=svc(RV_SETTINGS,1,0,0,&io.info,sizeof(io.info),0,&io.reply);
    if(status!=RV_OK)return;
    if(io.info.header.version==1&&io.info.header.bytes==sizeof(io.info)&&!io.info.header.flags&&io.info.token&&
       io.info.length==0x1000&&io.info.settings_epoch==g->epoch.settings&&memory_op(4,0,0,0)==RV_OK){
        copy(record,io.request.record.record,40);
        g->memory_result=(uint8_t)memory_decode(record,&ref,&levels,&user);
        g->restore_done=1;
        if(g->memory_result==1){g->saved=ref;g->saved_t=levels;g->saved_user=(uint8_t)user;
            g->saved_epoch=io.info.settings_epoch;g->saved_crc=eng_crc(record,40);}
    }
    if(svc(RV_SETTINGS,3,io.info.token,0,0,0,0,&io.reply)!=RV_OK){g->memory_result=7;g->restore_done=0;}
}
'''+s[end:]
s=s.replace('*detail=2;g->restore_done=1;','*detail=2;diag_engine(1);eng_read_saved();')
s=s.replace('if(!boot_acquire())goto clean;', 'if(!boot_acquire()){diag_reason(20,BF_NATIVE);goto clean;}')
s=s.replace('if(!memory_decode(record,&ref,&levels,&user)||compute(&ref,&levels,wb)!=ENG_OK)goto clean;',
    'if(memory_decode(record,&ref,&levels,&user)!=1||compute(&ref,&levels,wb)!=ENG_OK){diag_reason(21,BF_RECORD);goto clean;}')
s=s.replace('if(memory_op(4,0,0,0)!=RV_OK)goto clean;', 'if(memory_op(4,0,0,0)!=RV_OK){diag_reason(21,BF_RECORD);goto clean;}')
s=s.replace('if(memory_op(4,0,0,0)!=RV_OK||!equal(record,io.request.record.record,40))goto clean;',
    'if(memory_op(4,0,0,0)!=RV_OK||!equal(record,io.request.record.record,40)){diag_reason(30,BF_EPOCH);goto clean;}')
s=s.replace('if(live_check(&mismatch,0)!=ENG_OK||mismatch||t_seen!=2||!boot_s_valid())goto clean;',
    'if(live_check(&mismatch,0)!=ENG_OK||mismatch||t_seen!=2||!boot_s_valid()){diag_reason(22,BF_ROWS);goto clean;}')
s=s.replace('if(live_check(&mismatch,0)!=ENG_OK||mismatch||t_seen!=2||!boot_s_valid()||!fresh())goto clean;',
    'if(live_check(&mismatch,0)!=ENG_OK||mismatch||t_seen!=2||!boot_s_valid()||!fresh()){diag_reason(22,BF_ROWS);goto clean;}')
s=s.replace('if(svc(RV_SETTINGS,6,0,0,&io.request.plan,sizeof(io.request.plan),io.request.plan.count,&io.reply)!=RV_OK)goto clean;',
    'if(svc(RV_SETTINGS,6,0,0,&io.request.plan,sizeof(io.request.plan),io.request.plan.count,&io.reply)!=RV_OK){diag_reason(23,BF_LOCK);goto clean;}')
s=s.replace('status=deep(1);','diag_engine(2);status=deep(1);',1)
s=s.replace('status=ENG_UNCERTAIN;\n    if(!eng_boot_check())', 'status=ENG_UNCERTAIN;diag_reason(31,BF_COLOUR);diag_engine(3);\n    if(!eng_boot_check())')
s=s.replace('g->boot_committed=1;','g->boot_committed=1;g->auto_result=1;diag_engine(4);')
s=s.replace('g->busy=g->boot_active=0;return status;',
    'if(status!=ENG_OK)diag_reason(status==ENG_STALE?30:31,status==ENG_STALE?BF_EPOCH:BF_COLOUR);\n    g->busy=g->boot_active=0;return status;')
p.write_text(s)
p=P/'boot_adapter.inc.c';s=p.read_text()
start=s.index('static int boot_mode_known(');end=s.index('volatile uint8_t ig_boot_raw_mode;',start)
s=s[:start]+'''static uint32_t boot_fail_bits(void)
{
    uint32_t bits=0,settings=RV_WORD(0x200c0dac),length=RV_WORD(0x200c0db0);
    unsigned valid=settings>=0x20000000u&&settings<=0x207ff000u&&length==0x1000;
    if(RV_WORD(0x205d9bf8)!=0)bits|=BF_ACTIVITY;
    /* The existing proven native branch. No physical M/P/A/S mapping is invented. */
    if(RV_BYTE(0x205d9a7f)!=0||!valid||RV_WORD(settings+0x2fc)!=0x8001)bits|=BF_MODE;
    if(RV_BYTE(0x205d9aa3))bits|=BF_MY;
    if(RV_BYTE(0x205da00b))bits|=BF_PENDING;
    if(!valid)bits|=BF_SETTINGS;
    if(RV_WORD(0x205d9c00)!=5)bits|=BF_STATE;
    return bits;
}
static int boot_native_ready(void){return !boot_fail_bits();}
'''+s[end:]
start=s.index('static int32_t boot_run(')
s=s[:start]+'''static int32_t boot_run(const RvApi *a,uint32_t c,const RvRequest *q,RvReply *r)
{
    EngStatus status=ENG_OK;unsigned detail=2,reason=0;uint32_t bits;
    if(!ingress(a,c,q,r)){r->status=RV_STALE;return RV_FAULT;}
    diag_capture(51);ig_boot_raw_mode=RV_BYTE(0x205d9a7f);bits=boot_fail_bits();
    n.entry=51;n.watch_view=n.view_lost=n.comm_failed=0;eng_view_lost(0);
    rv_settings_entry(RV_PTR(n.context->root_address),51);
    boot_mode_epoch=((RvRoot *)RV_PTR(n.context->root_address))->epoch[RV_MODE_E];
    boot_settings=RV_WORD(0x200c0dac);boot_settings_bytes=RV_WORD(0x200c0db0);
    eng_read_saved();
    if(bits&BF_ACTIVITY)reason=10;
    else if(bits&BF_MODE)reason=11;
    else if(bits&BF_MY)reason=12;
    else if(bits&BF_PENDING)reason=13;
    else if(bits&BF_SETTINGS)reason=14;
    else if(bits&BF_STATE)reason=15;
    if(q->args[9]!=0x200547ec){bits|=BF_SETTINGS;if(!reason)reason=14;}
    if(eng_memory_result()!=1){bits|=BF_RECORD;if(!reason)reason=21;}
    if(boot_settings>=0x20000000u&&boot_settings<=0x207ff000u&&boot_settings_bytes==0x1000&&
       (RV_BYTE(boot_settings+8)||RV_BYTE(boot_settings+0x36e)!=1||
        RV_BYTE(boot_settings+0x6dd)!=9||RV_BYTE(boot_settings+0x6de)!=9)){
        bits|=BF_NATIVE;if(!reason)reason=20;
    }
#if !G157_BOOT
    bits|=BF_POLICY;reason=2;
#endif
    if(bits)diag_reason(reason,bits);
    else status=eng_boot_check()?eng_boot_run(RV_PTR(q->args[9]),&detail):ENG_STALE;
    n.active=0;r->detail=detail;r->status=status==ENG_OK?RV_OK:status==ENG_STALE?RV_STALE:RV_IO;
    return status==ENG_OK?RV_CONSUMED:RV_FAULT;
}
''';p.write_text(s)
print('separated readback and BOOT transaction')
