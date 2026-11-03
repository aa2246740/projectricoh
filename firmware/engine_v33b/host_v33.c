/* Native calls are doubled; every engine/service/resident path is real C. */
#define main inherited_fixture_main
#define rv_native_open original_open
#define rv_native_create original_create
#define rv_native_read original_read
#define rv_native_write original_write
#define rv_native_close original_close
#define rv_native_delete original_delete
#define rv_native_rename original_rename
#include "containers/product/host_checks.c"
#undef main
#undef rv_native_open
#undef rv_native_create
#undef rv_native_read
#undef rv_native_write
#undef rv_native_close
#undef rv_native_delete
#undef rv_native_rename

static unsigned tracing,last_object,injected_op,injected_at,counts[10],injected;
static int injected_code=-1;
static File durable_before[64];
static int traced(unsigned op,const char *path)
{
    if(!tracing || strncmp(path,last_object?"/IROM/L":"/IROM/T",7))return 0;
    ++counts[op];
    if(op==injected_op && counts[op]==injected_at) {
        injected=1;printf("INJECT op=%u ordinal=%u path=%s raw=%d\n",op,counts[op],path,injected_code);return 1;
    }
    return 0;
}
int32_t rv_native_open(const char *p,uint32_t f)
{return traced(2,p)?injected_code:original_open(p,f);}
int32_t rv_native_create(const char *p,uint32_t f)
{return traced(3,p)?injected_code:original_create(p,f);}
int32_t rv_native_read(int32_t fd,void *p,uint32_t n)
{return traced(4,files[fds[fd-17].file].path)?injected_code:original_read(fd,p,n);}
int32_t rv_native_write(int32_t fd,const void *p,uint32_t n)
{return traced(5,files[fds[fd-17].file].path)?injected_code:original_write(fd,p,n);}
int32_t rv_native_close(int32_t fd)
{
    int fail=traced(6,files[fds[fd-17].file].path);int32_t rc=original_close(fd);
    return fail?injected_code:rc;
}
int32_t rv_native_delete(const char *p)
{return traced(8,p)?injected_code:original_delete(p);}
int32_t rv_native_rename(const char *a,const char *b)
{
    int fail=traced(7,a);
    if(!fail && tracing && !strncmp(a,last_object?"/IROM/L":"/IROM/T",7))CHECK(!file(b));
    return fail?injected_code:original_rename(a,b);
}
static void path_for(char p[32],int last,unsigned slot,unsigned copy)
{
    const char *tag=unit==0?"50":unit==1?"28":"M0";
    if(last)CHECK(snprintf(p,32,copy==2?"/IROM/L%s.TMP":"/IROM/L%s%c.BIN",tag,'A'+copy)>0);
    else CHECK(snprintf(p,32,copy==2?"/IROM/T%s%02u.TMP":"/IROM/T%s%02u%c.BIN",tag,slot-1,'A'+copy)>0);
}
static void current_slot(unsigned slot,int value)
{
    EngRecipeRef ref;EngTweak t;root.inflight=1;CHECK(eng_current(&ref,&t)==ENG_OK);root.inflight=0;
    CHECK(ref.unit==unit&&ref.slot==slot&&t.v[0]==value);
}
static int has_current(void)
{
    EngRecipeRef r;EngTweak t;EngStatus status;
    root.inflight=1;status=eng_current(&r,&t);root.inflight=0;return status==ENG_OK;
}
static void actual_rows(uint8_t out[410])
{
    unsigned i,pos=0;uint32_t map=be32(new_raw+be32(new_raw+156)+64*unit+12);
    for(i=0;i<7;++i) {
        const uint8_t *d=new_raw+map+32+12*i;unsigned bytes=be16(d+4);
        memcpy(out+pos,RV_PTR(be32(d)),bytes);pos+=bytes;
    }
    CHECK(pos==408);out[408]=t_control>>8;out[409]=t_control;
}
static void load108(void)
{
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->generation==108);
    CHECK(!has_current());menu();CHECK(root.state==RV_READY);
}
static void installed(void)
{put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);load108();}
static void cold108(void)
{reboot();load108();}
static void save_cont(unsigned slot,int value)
{menu();select_slot(slot);panel_open();select_slot((unsigned)(value+6));close_key(1);CHECK(root.state==RV_READY&&ig_host_panel()->last_store==RV_OK);current_slot(slot,value);}
static void no_files_changed(void)
{CHECK(!memcmp(files,durable_before,sizeof(files)));}
static void seed_tweak(const uint8_t *raw,unsigned bytes,unsigned slot,unsigned copies,int value)
{
    Gxr2View v;GxtsBinding b;GxtsState state;uint8_t encoded[GXTS_BYTES];char path[32];unsigned i;
    CHECK(gxr2_validate(raw,bytes,&trust,&units[unit],0,&v)==GXR2_OK);
    CHECK(gxts_bind(&v,unit,slot,&b)==GXTS_OK);
    gxts_defaults(&b,&state);state.values[0]=value;
    for(i=0;i<copies;++i) {
        state.generation=i+1;CHECK(gxts_encode(&b,&state,encoded)==GXTS_OK);
        path_for(path,0,slot,i);put_file(path,encoded,sizeof(encoded));
    }
}
static void visibility(void)
{
    unsigned i;uint32_t frame[32]={0};installed();
    if(unit==1) {
        CHECK(!eng_list()->opened&&!root.ui_block&&RV_BYTE(0x2022f5ac)==7);matches_stock();
        memcpy(durable_before,files,sizeof(files));rv_hook_observe(&root,6,frame);CHECK(!frame[1]);
        frame[1]=0;rv_hook_observe(&root,8,frame);CHECK(!frame[1]&&!rpc_w);menu();no_files_changed();return;
    }
    CHECK(eng_list()->rows==8&&session()->rows==8&&session()->cursor==0&&RV_BYTE(0x2022f5ac)==8);
    CHECK(!has_current());
    for(i=0;i<8;++i)CHECK(eng_list()->row[i].occupied&&eng_list()->row[i].ascii[0]=='0'&&eng_list()->row[i].ascii[1]==(char)('1'+i));
    select_slot(1);matches_recipe(new_raw,1,new_golden);
    select_slot(8);matches_recipe(new_raw,8,new_golden);CHECK(session()->cursor==7);
    panel_open();CHECK(ig_host_panel()->recipe.slot==8&&session()->rows==11);close_key(0);
    cold108();CHECK(session()->rows==8&&session()->cursor==7);current_slot(8,0);
}
static void invalid_row(unsigned row)
{
    uint32_t frame[32]={0},before;installed();select_slot(5);before=rpc_w;
    RV_BYTE(0x2022f726)=row;rv_hook_observe(&root,8,frame);
    CHECK(root.state==RV_DISABLED_UNTIL_REBOOT&&frame[1]==(uint32_t)(uintptr_t)rv_skip_08&&rpc_w==before);
    CHECK(RV_BYTE(0x2022f5ac)==7);cold108();current_slot(5,0);CHECK(session()->cursor==4);
}
static void remember(unsigned slot)
{
    uint8_t before[410],after[410],settings[0x1000];unsigned mutations;
    installed();save_cont(slot,2);actual_rows(before);memcpy(settings,RV_PTR(0x20500000),sizeof(settings));
    last_object=1;tracing=1;memset(counts,0,sizeof(counts));menu();select_slot(slot);panel_open();close_key(0);
    mutations=counts[3]+counts[5]+counts[7]+counts[8];CHECK(!mutations);tracing=0;
    memcpy(durable_before,files,sizeof(files));cold108();no_files_changed();
    CHECK(eng_list()->cursor==slot&&session()->cursor==slot-1&&RV_BYTE(0x2022f726)==slot);
    current_slot(slot,2);actual_rows(after);CHECK(!memcmp(before,after,sizeof(before)));
    CHECK(!memcmp(settings,RV_PTR(0x20500000),sizeof(settings)));
    if(slot==3)CHECK(RV_BYTE(0x2050036e)==3);
}
static void remembered_invalid(const char *kind)
{
    char a[32];uint8_t raw[192];File *f;Gxr2View v;GxtsBinding b;unsigned slot,before;
    installed();select_slot(5);path_for(a,1,0,0);f=file(a);CHECK(f&&f->length==192);memcpy(raw,f->bytes,192);
    if(!strcmp(kind,"missing"))f->exists=0;
    else if(!strcmp(kind,"unreadable")) {hidden_path[0]=a;hidden_left[0]=3;}
    else {
        if(!strcmp(kind,"corrupt"))raw[12]^=1;
        else if(!strcmp(kind,"stale")) {raw[24+96]^=1;rv_put32(raw+12,0);rv_put32(raw+12,gxrce_crc32(raw,192));}
        else {
            slot=!strcmp(kind,"hidden09")?9:10;CHECK(gxr2_validate(base_raw,base_bytes,&trust,&units[unit],0,&v)==GXR2_OK);
            CHECK(gxts_bind(&v,unit,slot,&b)==GXTS_OK);raw[16]=slot;memcpy(raw+24,b.identity,160);
            rv_put32(raw+12,0);rv_put32(raw+12,gxrce_crc32(raw,192));
        }
        put_file(a,raw,192);
    }
    before=rpc_w;memcpy(durable_before,files,sizeof(files));cold108();no_files_changed();
    CHECK(!has_current()&&session()->cursor==0&&eng_list()->cursor==1&&root.state==RV_READY&&rpc_w==before);
    select_slot(5);CHECK(root.state==RV_READY);current_slot(5,0);
}
static void stale_binding(unsigned slot,unsigned copies)
{
    uint8_t before[410],after[410];installed();seed_tweak(base_raw,base_bytes,slot,copies,2);
    cold108();select_slot(slot);current_slot(slot,0);
    save_cont(slot,3);actual_rows(before);cold108();current_slot(slot,3);actual_rows(after);
    CHECK(!memcmp(before,after,sizeof(before)));puts("R4_01_PASS stale_A_or_AB_save_and_cold_reload=3");
}
static uint32_t direct_address(void *unused,const void *p,uint32_t bytes)
{(void)unused;(void)bytes;return eng_wire_address(p);}
static PnGxts *direct_store(unsigned slot,PnPort *port)
{
    RvPrivateContext *c=&session()->context;uint32_t base=(c->state_address+3079u)&~7u;
    PsStore *store=RV_PTR(base);PnGxts *tweak=RV_PTR(base+1280);uint8_t indices[6];EngRecipeRef ref;unsigned i;
    const Gxr2View *v=eng_validated_view();const uint8_t *d=v->bytes+v->sections[2].offset+64*unit;
    memset(port,0,sizeof(*port));port->api=rv_services_init(c);port->context=root.lease;
    port->io_lease=port->ui_lease=c->state_lease;port->address=direct_address;
    for(i=0;i<6;++i){port->epochs[i]=root.epoch[i];indices[i]=(uint8_t)eng_parameter_index(i+1);}
    ps_init(store,port,RV_PTR(base+1024),256,0,0);
    ref.unit=(uint8_t)unit;ref.slot=(uint8_t)slot;eng_identity(v->bytes+be32(d+16)+32+64*(slot-1),ref.identity);
    CHECK(pn_gxts_bind(tweak,store,v,&ref,indices)==RV_OK);return tweak;
}
static void direct_stale(unsigned copies)
{
    PnPort port;PnGxts *tweak;GxtsBinding stale;GxtsState state;EngTweak values;
    uint8_t encoded[GXTS_BYTES];char path[32];unsigned i;
    installed();root.inflight=1;tweak=direct_store(1,&port);stale=tweak->binding;stale.identity[96]^=128;
    gxts_defaults(&stale,&state);state.values[0]=2;
    for(i=0;i<copies;++i){state.generation=i+1;CHECK(gxts_encode(&stale,&state,encoded)==GXTS_OK);path_for(path,0,1,i);put_file(path,encoded,sizeof(encoded));}
    CHECK(pn_gxts_load(tweak,&values)==RV_OK&&values.v[0]==0);values.v[0]=3;
    tracing=1;CHECK(pn_gxts_save(tweak,&tweak->recipe,&values)==RV_OK);tracing=0;root.inflight=0;
    cold108();root.inflight=1;tweak=direct_store(1,&port);
    CHECK(pn_gxts_load(tweak,&values)==RV_OK&&values.v[0]==3);root.inflight=0;
    puts("DIRECT_R4_01_PASS current_binding_defaults_then_save=3 cold_reload=3");
}
static void upgrade(int saved)
{
    char path[32];uint8_t prior[GXTS_BYTES];
    put_file("/IROM/GXRCE0.DAT",base_raw,base_bytes);
    if(saved) {
        seed_tweak(base_raw,base_bytes,5,1,2);path_for(path,0,5,0);memcpy(prior,file(path)->bytes,GXTS_BYTES);
    }
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->generation==be32(base_raw+28));menu();
    CHECK(!has_current());
    put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);reboot();load108();
    CHECK(ig_host_install_status()==RV_OK&&valid_irom(0)&&valid_irom(1));
    CHECK(!file("/ATA1/GXRCE.DAT")&&file("/ATA1/GXRCE.OK")&&!has_current());
    if(saved)CHECK(file(path)&&!memcmp(file(path)->bytes,prior,GXTS_BYTES));
    if(unit==1) {CHECK(RV_BYTE(0x2022f5ac)==7);matches_stock();cold108();return;}
    CHECK(session()->cursor==0);select_slot(5);current_slot(5,saved?2:0);
    cold108();current_slot(5,saved?2:0);CHECK(session()->cursor==4);
}
static void per_unit(void)
{
    CHECK(unit==0);installed();save_cont(5,2);
    unit=2;reboot();load108();CHECK(!has_current()&&session()->cursor==0);save_cont(6,1);
    unit=0;cold108();current_slot(5,2);CHECK(session()->cursor==4);
    unit=2;cold108();current_slot(6,1);CHECK(session()->cursor==5);
    unit=1;memcpy(durable_before,files,sizeof(files));cold108();no_files_changed();
    CHECK(RV_BYTE(0x2022f5ac)==7&&!has_current());
    unit=0;cold108();current_slot(5,2);
}
static void apply_failure(int automatic)
{
    uint32_t before,frame[32]={0};installed();
    if(automatic) {
        select_slot(5);reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);
    }
    before=rpc_w;fault_kind=8;fault_at=kind_count[0]+1;fault_action=21;
    memcpy(durable_before,files,sizeof(files));
    if(automatic)rv_hook_observe(&root,1,frame);
    else {RV_BYTE(0x2022f726)=5;rv_hook_observe(&root,8,frame);}
    CHECK(root.state==RV_DISABLED_UNTIL_REBOOT&&rpc_w==before+1&&eng_uncertain());
    CHECK(RV_BYTE(0x2022f5ac)==7);no_files_changed();
}
static void fault_save(int last,unsigned initial,int empty,unsigned op,unsigned ordinal,int code)
{
    uint8_t committed[410],after[410],settings[0x1000];char tmp[32];unsigned i;
    installed();
    if(last) {
        if(!empty) {select_slot(1);if(initial==2)select_slot(2);}
    } else if(!empty) {save_cont(5,1);if(initial==2)save_cont(5,2);}
    if(!last) {menu();select_slot(5);panel_open();actual_rows(committed);memcpy(settings,RV_PTR(0x20500000),sizeof(settings));select_slot(9);}
    path_for(tmp,last,5,2);if(!empty)put_file(tmp,(const uint8_t *)"stale",5);
    last_object=last;tracing=1;injected_op=op;injected_at=ordinal;injected_code=code;
    memset(counts,0,sizeof(counts));
    if(last)select_slot(5);else close_key(1);
    tracing=0;
    if(op)CHECK(injected);
    if(!op) {
        printf("TRACE object=%s initial=%u empty=%d",last?"last":"tweak",initial,empty);
        for(i=2;i<=8;++i)printf(" op%u=%u",i,counts[i]);puts("");
    }
    if(last) {current_slot(5,0);matches_recipe(new_raw,5,new_golden);}
    else if(ig_host_panel()->last_store==RV_OK)current_slot(5,3);
    else {
        actual_rows(after);CHECK(!memcmp(committed,after,sizeof(committed)));
        CHECK(!memcmp(settings,RV_PTR(0x20500000),sizeof(settings)));
    }
    /* A failed final readback can leave the whole old or new record. It must
     * never leave a partial formal record or make subsequent saves stick. */
    cold108();
    if(last) {
        if(has_current()) {
            EngRecipeRef ref;EngTweak t;root.inflight=1;CHECK(eng_current(&ref,&t)==ENG_OK);root.inflight=0;
            CHECK(ref.slot==1||ref.slot==2||ref.slot==5);matches_recipe(new_raw,ref.slot,new_golden);
        } else CHECK(session()->cursor==0);
        select_slot(5);select_slot(6);CHECK(ig_host_last_store()==RV_OK);cold108();current_slot(6,0);
    } else {save_cont(5,4);cold108();current_slot(5,4);}
    printf("FAULT_PASS object=%s op=%u ordinal=%u raw=%d rollback=1 reboot_retry=1\n",last?"last":"tweak",op,ordinal,code);
}
int main(int argc,char **argv)
{
    uint8_t wire[232];unsigned i,op=0,ordinal=0,initial=2;int code=-1;
    CHECK(argc>=8);scenario=argv[1];unit=(unsigned)strtoul(argv[2],0,10);CHECK(unit<3);
    base_bytes=load_file(argv[3],base_raw,sizeof(base_raw));new_bytes=load_file(argv[4],new_raw,sizeof(new_raw));
    CHECK(load_file(argv[5],wire,sizeof(wire))==232&&load_file(argv[6],golden,sizeof(golden))==sizeof(golden));
    CHECK(load_file(argv[7],new_golden,sizeof(new_golden))==sizeof(new_golden));
    memcpy(trust.body_sha256,wire+8,32);memcpy(trust.resident_build_id,wire+40,32);memcpy(trust.resident_abi_id,wire+72,16);
    for(i=0;i<3;++i){trust.modules[i].unit=units[i];trust.modules[i].stock_crc32=be32(wire+100+48*i);memcpy(trust.modules[i].stock_sha256,wire+104+48*i,32);}
    rename_refuse_existing=argc>8?(unsigned)strtoul(argv[8],0,10):1;reboot();
    if(!strcmp(scenario,"visible"))visibility();
    else if(!strncmp(scenario,"invalid-row-",12))invalid_row((unsigned)strtoul(scenario+12,0,10));
    else if(!strcmp(scenario,"remember05"))remember(5);
    else if(!strcmp(scenario,"remember03"))remember(3);
    else if(!strncmp(scenario,"remember-",9))remembered_invalid(scenario+9);
    else if(!strncmp(scenario,"stale-",6))stale_binding(strstr(scenario,"slot2")?2:1,strstr(scenario,"both")?2:1);
    else if(!strncmp(scenario,"direct-stale-",13))direct_stale(strstr(scenario,"both")?2:1);
    else if(!strncmp(scenario,"upgrade-",8))upgrade(strstr(scenario,"saved")!=NULL);
    else if(!strcmp(scenario,"per-unit"))per_unit();
    else if(!strcmp(scenario,"auto-apply-failure"))apply_failure(1);
    else if(!strcmp(scenario,"manual-apply-failure"))apply_failure(0);
    else if(!strncmp(scenario,"fault-",6)||!strncmp(scenario,"trace-",6)) {
        if(argc>9)initial=(unsigned)strtoul(argv[9],0,10);
        if(argc>10)op=(unsigned)strtoul(argv[10],0,10);
        if(argc>11)ordinal=(unsigned)strtoul(argv[11],0,10);
        if(argc>12)code=(int)strtol(argv[12],0,10);
        fault_save(strstr(scenario,"last")!=NULL,initial,initial==0,op,ordinal,code);
    } else CHECK(0);
    CHECK(opens==closes);for(i=0;i<2;++i)CHECK(!fds[i].live);
    printf("OK scenario=%s unit=%u assertions=%u rename=%s real_missing=-1\n",scenario,unit,assertions,rename_refuse_existing?"reject":"replace");return 0;
}
