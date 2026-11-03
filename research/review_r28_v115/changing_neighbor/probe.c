/* Real resident, services and product C; only native boundaries are doubles. */
#define rv_rpc8_native fixture_rpc8
#define rv_native_create fixture_create
#define rv_native_write fixture_write
#define rv_native_delete fixture_delete
#define rv_native_rename fixture_rename
#define rv_native_sd_id fixture_sd_id
#include "/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/research/review_r28_v115/host/fixture.inc.c"
#undef rv_rpc8_native
#undef rv_native_create
#undef rv_native_write
#undef rv_native_delete
#undef rv_native_rename
#undef rv_native_sd_id
#include "containers/product/blackbox.h"
#include "entry_projection.inc.c"
static unsigned explicit_apply,flush_allowed,rpc_calls,t_reads,log_writes,internal_mutations,sd_failure;
static unsigned inject_at,inject_action,inject_hit,after_fault_w;
static unsigned service_fault_id,service_fault_op,service_fault_hit,service_fault_w;
extern int32_t fixture_service(RvRoot *,uint32_t,uint32_t,const RvRequest *,RvReply *);
int32_t rv_service(RvRoot *r,uint32_t id,uint32_t op,const RvRequest *q,RvReply *reply)
{
    if(id==service_fault_id&&op==service_fault_op&&!service_fault_hit){
        memset(reply,0,sizeof(*reply));reply->version=1;reply->bytes=32;reply->status=RV_IO;
        service_fault_hit=1;service_fault_w=rpc_w;return RV_IO;
    }
    return fixture_service(r,id,op,q,reply);
}
static struct {unsigned cmd,value,address;} trace[1024];
static void mutation(const char *p)
{
    if(!strncmp(p,"/ATA1/GXRBX",11)){
        CHECK(flush_allowed&&root.inflight&&session()->rpc_token==0);++log_writes;
    }else if(!strncmp(p,"/IROM/T",7)||!strncmp(p,"/IROM/L",7)){
        CHECK(!(root.flags&RF_QUARANTINE));++internal_mutations;
    }
}
int32_t rv_native_create(const char *p,uint32_t f){mutation(p);return fixture_create(p,f);}
int32_t rv_native_write(int32_t fd,const void *p,uint32_t n){mutation(files[fds[fd-17].file].path);return fixture_write(fd,p,n);}
int32_t rv_native_delete(const char *p){mutation(p);return fixture_delete(p);}
int32_t rv_native_rename(const char *a,const char *b){mutation(a);mutation(b);return fixture_rename(a,b);}
int32_t rv_native_sd_id(void *p){if(sd_failure==2){memset(p,0,16);return 0;}return sd_failure?-1:fixture_sd_id(p);}
int32_t rv_rpc8_native(uint32_t cmd,uint32_t value)
{
    int32_t result;unsigned address=(page<<16)|(value&65534);
    CHECK(explicit_apply);
    if(rpc_calls<1024){
    trace[rpc_calls].cmd=cmd;trace[rpc_calls].value=value;
    trace[rpc_calls].address=cmd==21?address:cursor;
    }
    ++rpc_calls;if(cmd==21&&page==0x12c0)++t_reads;
    if(inject_hit&&cmd==22)++after_fault_w;
    if(rpc_calls==inject_at&&inject_action==0){inject_hit=1;return -1;}
    result=fixture_rpc8(cmd,value);
    if(rpc_calls==inject_at){
        inject_hit=1;
        if(inject_action==1)return result^1;
        ++root.epoch[inject_action==2?RV_LINK_E:inject_action==3?RV_UNIT_E:inject_action==4?RV_BOOT_E:RV_S_E];
    }
    return result;
}
static void clean(void)
{
    memset(files,0,sizeof(files));explicit_apply=flush_allowed=0;
    inject_at=inject_hit=after_fault_w=rpc_calls=t_reads=0;sd_failure=0;
    native_fail_op=native_fail_left=0;native_fail_path=0;native_fail_code=-1;
    service_fault_id=service_fault_op=service_fault_hit=service_fault_w=0;
    fault_kind=fault_at=fault_used=0;scenario="v34c";reboot();
    writes=renames=rpc_w=previews=log_writes=internal_mutations=0;
}
static void ready(int card_source)
{
    put_file(card_source?"/ATA1/GXRCE.DAT":"/IROM/GXRCE0.DAT",new_raw,new_bytes);
    CHECK(rv_load(&root,&rv_trust)==RV_OK);
    CHECK(!rpc_calls&&!rpc_w&&!writes&&!previews&&!log_writes);
}
static int has_recipe(void)
{EngRecipeRef r;EngTweak t;int result;root.inflight=1;result=eng_current(&r,&t)==ENG_OK;root.inflight=0;return result;}
static void apply_ok(unsigned slot)
{select_slot(slot);explicit_apply=flush_allowed=1;close_key(1);explicit_apply=flush_allowed=0;}
static void open_fn2(void)
{explicit_apply=flush_allowed=1;panel_open();explicit_apply=flush_allowed=0;}
static void close_menu(void)
{flush_allowed=1;close_key(0);flush_allowed=0;}
static void tweak_path(char path[32],unsigned slot,unsigned replica)
{snprintf(path,32,"/IROM/T%s%02u%c.BIN",unit==0?"50":unit==1?"28":"M0",slot-1,'A'+replica);}
static void last_path(char path[32],unsigned replica)
{snprintf(path,32,"/IROM/L%s%c.BIN",unit==0?"50":unit==1?"28":"M0",'A'+replica);}
static void seed_last34(unsigned slot)
{
    uint8_t raw[192]={0};Gxr2View v;GxtsBinding b;char path[32];
    CHECK(gxr2_validate(new_raw,new_bytes,&trust,&units[unit],0,&v)==GXR2_OK);
    CHECK(gxts_bind(&v,unit,slot,&b)==GXTS_OK);
    memcpy(raw,"GXLS",4);raw[5]=1;raw[7]=192;rv_put32(raw+8,1);raw[16]=slot;raw[17]=unit;
    memcpy(raw+24,b.identity,160);rv_put32(raw+12,gxrce_crc32(raw,sizeof(raw)));last_path(path,0);put_file(path,raw,sizeof(raw));
}
/* Unchanged gen113 code is a negative control under the same writer replay. */
#define rv_native_seed old_rv_native_seed
#include "/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/firmware/engine_v36_r28/baseline/engine_services/native_seed.c"
#undef rv_native_seed
static void seed115(const char *output)
{
    RvPrivateContext *c;uint8_t before[32],private_old[236],sentinel[236];unsigned pointer,capacity,kind;
    clean();ready(1);c=&session()->context;CHECK(c->ui_state_capacity==256);
    memcpy(before,RV_PTR(0x2022f71c),32);
    CHECK(RV_BYTE(0x2022f71c)==0&&RV_WORD(0x2022f720)==0x2022f56c);
    CHECK(old_rv_native_seed(c)==RV_UNAVAILABLE);
    CHECK(rv_native_seed(c)==RV_OK&&c->ui_state_bytes==236);
    CHECK(RV_BYTE(c->ui_state_address)==5);
    CHECK(!memcmp(RV_PTR(c->ui_state_address+1),before+1,31));
    CHECK(!memcmp(RV_PTR(c->ui_state_address+32),RV_PTR(0x2022f56c),72));
    CHECK(!memcmp(before,RV_PTR(0x2022f71c),32));
    for(pointer=0;pointer<3;pointer++)for(capacity=0;capacity<2;capacity++){
        RV_WORD(0x2022f720)=pointer==0?0:pointer==1?0x20704800-71:0x2022f000;
        c->ui_state_capacity=capacity?256:235;
        memset(RV_PTR(c->ui_state_address),0xa5,236);memcpy(sentinel,RV_PTR(c->ui_state_address),236);
        CHECK(rv_native_seed(c)==RV_UNAVAILABLE);
        CHECK(!memcmp(sentinel,RV_PTR(c->ui_state_address),236));
    }
    CHECK(rv_native_seed(0)==RV_UNAVAILABLE);
    /* Preserve the old hand-seeded type5 case as an explicit regression only. */
    c->ui_state_capacity=256;RV_BYTE(0x2022f71c)=5;RV_WORD(0x2022f720)=0x2022f000;
    CHECK(old_rv_native_seed(c)==RV_OK);memcpy(private_old,RV_PTR(c->ui_state_address),236);
    CHECK(rv_native_seed(c)==RV_OK&&!memcmp(private_old,RV_PTR(c->ui_state_address),236));
    for(kind=0;kind<4;kind++){
        clean();
        if(kind==1)native_writer_exposure();
        if(kind==2)native_writer_white_balance();
        if(kind==3)native_writer_image();
        CHECK(RV_BYTE(0x2022f71c)==(kind==0?0:kind==1?4:kind==2?9:5));
        ready(1);c=&session()->context;
        CHECK(old_rv_native_seed(c)==(kind==3?RV_OK:RV_UNAVAILABLE));
        menu();
        if(fixture_has_recipes()){
            CHECK(session()->rows==8&&rv_ui_snapshot(&root)->state[0]==5);
            CHECK(RV_BYTE(0x2022f71c)==(kind==0?0:kind==1?4:kind==2?9:5));
            open_fn2();close_menu();
        }
    }
    clean();ready(1);c=&session()->context;menu();
    if(!fixture_has_recipes()){CHECK(RV_BYTE(0x2022f5ac)==7);return;}
    CHECK(session()->rows==8&&rv_ui_snapshot(&root)->state[0]==5);
    CHECK(RV_BYTE(0x2022f71c)==0); /* No new native kind store. */
    CHECK(!memcmp(RV_PTR(c->state_address+2048+2432),"GXSD3501",8));
    CHECK(be32(RV_PTR(c->state_address+2048+2440))==256);
    /* Exercise the actual resident H01/H02 path before the native type5 store. */
    close_menu();native_writer_adj();CHECK(first_frame_entry(1)>=1);
    CHECK(session()->rows==8&&RV_BYTE(0x2022f71c)==5);
    open_fn2();close_menu();
    {
        File *saved=file("/ATA1/GXRBX0.BIN");FILE *f;
        CHECK(saved&&saved->length==4096);f=fopen(output,"wb");
        CHECK(f&&fwrite(saved->bytes,1,4096,f)==4096&&!fclose(f));
    }
}
static void fallback115(void)
{
    unsigned mode;uint32_t frame[32];uint8_t state[32];RvPrivateContext *c;
    for(mode=0;mode<2;mode++){
        clean();ready(0);c=&session()->context;
        if(mode==0)c->ui_state_capacity=235;
        else RV_WORD(0x2022f720)=0; /* Positive evidence of an unproven layout. */
        memcpy(state,RV_PTR(0x2022f71c),32);memset(frame,0,sizeof(frame));
        flush_allowed=1;rv_hook_observe(&root,1,frame);flush_allowed=0;
        CHECK(!frame[1]&&(root.state==RV_READY||root.state==RV_DISABLED_UNTIL_REBOOT));
        CHECK(RV_WORD(0x2022f5a8)==0x2022d610&&RV_BYTE(0x2022f5ac)==7);
        CHECK(!memcmp(state,RV_PTR(0x2022f71c),32));
        CHECK(!rpc_calls&&!rpc_w&&!previews);
        native_writer_image();CHECK(RV_BYTE(0x2022f71c)==5);
        printf("NATIVE_FALLBACK positive_bad_input=%u resident_state=%u descriptor_rows=7 no_rpc=1\n",mode,root.state);
    }
}
static void update115(const uint8_t *old,unsigned bytes,unsigned keep_ok)
{
    unsigned before;uint32_t frame[32];File *saved;
    clean();put_file("/IROM/GXRCE0.DAT",old,bytes);put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);
    CHECK(be32(old+28)==114&&be32(new_raw+28)==115);
    put_file("/ATA1/GXRCE.OK",old,bytes);
    CHECK(file("/ATA1/GXRCE.OK")&&!memcmp(file("/ATA1/GXRCE.OK")->bytes,old,bytes));
    if(!keep_ok)file("/ATA1/GXRCE.OK")->exists=0; /* Reviewable card preparation. */
    rename_refuse_existing=1;
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->selected_source==RV_SOURCE_CARD);
    memset(frame,0,sizeof(frame));flush_allowed=1;rv_hook_observe(&root,1,frame);flush_allowed=0;
    if(keep_ok){
        CHECK(ig_host_install_status()==RV_UNCERTAIN&&root.state==RV_DISABLED_UNTIL_REBOOT);
        CHECK(file("/ATA1/GXRCE.DAT")&&file("/ATA1/GXRCE.OK")&&!memcmp(file("/ATA1/GXRCE.OK")->bytes,old,bytes));
        saved=file("/IROM/GXRCE1.DAT");CHECK(saved&&saved->length==new_bytes&&!memcmp(saved->bytes,new_raw,new_bytes));
        return;
    }
    CHECK(ig_host_install_status()==RV_OK&&!(root.flags&(RF_UNCERTAIN|RF_STOP|RF_QUARANTINE)));
    CHECK(file("/IROM/GXRCE0.DAT")&&!memcmp(file("/IROM/GXRCE0.DAT")->bytes,old,bytes));
    saved=file("/IROM/GXRCE1.DAT");CHECK(saved&&saved->length==new_bytes&&!memcmp(saved->bytes,new_raw,new_bytes));
    saved=file("/ATA1/GXRCE.OK");CHECK(saved&&saved->length==new_bytes&&!memcmp(saved->bytes,new_raw,new_bytes));
    CHECK(!file("/ATA1/GXRCE.DAT"));
    if(fixture_has_recipes()){CHECK(session()->rows==8);close_menu();}
    /* A formatted card has no product files. IROM still selects generation115. */
    saved=file("/ATA1/GXRCE.OK");saved->exists=0;reboot();before=writes;
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->generation==115);
    CHECK(session()->selected_source==RV_SOURCE_B&&writes==before);
    menu();if(fixture_has_recipes())CHECK(session()->rows==8);
}
static void basic(void)
{
    unsigned before,slot;uint8_t initial[4096];
    clean();memcpy(initial,RV_PTR(0x20500000),sizeof(initial));ready(1);menu();
    CHECK(!rpc_calls&&!previews&&!has_recipe());
    if(!fixture_has_recipes()){CHECK(RV_BYTE(0x2022f5ac)==7&&!log_writes);return;}
    before=writes;for(slot=1;slot<=8;slot++)select_slot(slot);
    CHECK(!rpc_calls&&!rpc_w&&!previews&&writes==before);
    CHECK(!memcmp(initial,RV_PTR(0x20500000),sizeof(initial)));
    apply_ok(1);CHECK(has_recipe());matches_recipe(new_raw,1,new_golden);
    CHECK(t_reads>=1&&log_writes);
    menu();select_slot(6);open_fn2();matches_recipe(new_raw,6,new_golden);
    before=rpc_calls;select_slot(8);CHECK(rpc_calls==before);close_menu();
    matches_recipe(new_raw,6,new_golden);
    menu();select_slot(4);apply_ok(4);matches_stock();
}
static void first_frame34(void)
{
    unsigned remembered,mode,before;
    for(remembered=0;remembered<=8;remembered++)for(mode=0;mode<256;mode++){
        clean();put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);
        if(remembered&&fixture_has_recipes())seed_last34(remembered);
        CHECK(rv_load(&root,&rv_trust)==RV_OK);before=rpc_calls;
        CHECK(first_frame_entry(mode)==(!fixture_has_recipes()?native_mode_rows[native_s_modes[mode]]:remembered?remembered:1));
        CHECK(rpc_calls==before&&!previews&&!writes&&!has_recipe());
        if(fixture_has_recipes()){
            if(mode%3==0){explicit_apply=flush_allowed=1;close_key(1);explicit_apply=flush_allowed=0;}
            else if(mode%3==1){open_fn2();close_menu();}
            else close_menu();
            if(mode%3!=2){CHECK(has_recipe());matches_recipe(new_raw,remembered?remembered:1,new_golden);}
            else {
                CHECK(!has_recipe());before=rpc_calls;
                CHECK(first_frame_entry(mode)==(remembered?remembered:1));
                CHECK(rpc_calls==before&&!has_recipe());close_menu();
            }
        }
    }
}
static void control34(unsigned mode)
{
    uint8_t ctl[17]={0};unsigned before;
    clean();put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);
    memcpy(ctl,"GXRC3401",8);rv_put32(ctl+8,mode==1?1:0);rv_put32(ctl+12,gxrce_crc32(ctl,12));
    if(mode!=0)put_file("/ATA1/GXRCE.CTL",ctl,mode==7?17:16);
    if(mode==3)file("/ATA1/GXRCE.CTL")->bytes[12]^=1;
    if(mode==4||mode==5||mode==6){native_fail_op=mode==4?2:mode==5?4:6;native_fail_path="/ATA1/GXRCE.CTL";native_fail_left=1;native_fail_code=-1;}
    if(mode==8)sd_failure=1;
    if(mode==9)sd_failure=2;
    before=opens;
    if(mode==2){
        CHECK(rv_load(&root,&rv_trust)!=RV_OK&&root.state==RV_DISABLED_UNTIL_REBOOT);
        CHECK(!rpc_calls&&!writes&&!previews&&!log_writes);
        file("/ATA1/GXRCE.CTL")->exists=0;
        {uint32_t f[32]={0};rv_hook_observe(&root,1,f);CHECK(!f[1]&&root.state==RV_DISABLED_UNTIL_REBOOT);}
    }else CHECK(rv_load(&root,&rv_trust)==RV_OK&&!rpc_calls&&!writes&&!previews);
    CHECK(opens>=before);
    if(mode==8||mode==9){menu();CHECK(root.state==RV_READY&&!rpc_calls&&!writes);if(fixture_has_recipes()){apply_ok(6);matches_recipe(new_raw,6,new_golden);CHECK(internal_mutations&&!log_writes);}}
}
static void iso34(unsigned neighbour)
{
    unsigned slot,next;Gxr2View v;uint32_t map,a14,b14;uint8_t *p;
    clean();ready(1);menu();if(!fixture_has_recipes())return;
    CHECK(gxr2_validate(new_raw,new_bytes,&trust,&units[unit],0,&v)==GXR2_OK);
    map=be32(new_raw+v.sections[2].offset+64*unit+12);a14=be32(new_raw+map+32+7*12);b14=be32(new_raw+map+32+8*12);
    p=RV_PTR(b14-1);p[0]=(uint8_t)neighbour;p[34]=(uint8_t)(255-neighbour);
    for(slot=1;slot<=8;slot++)for(next=1;next<=8;next++){
        menu();apply_ok(slot);matches_recipe(new_raw,slot,new_golden);
        CHECK(RV_BYTE(b14-1)==neighbour&&RV_BYTE(b14+33)==255-neighbour);
        CHECK(t_control==(unit!=2&&slot==6?0u:2u));
        if(slot!=4){CHECK(!memcmp(RV_PTR(a14),RV_PTR(be32(new_raw+map+32)),62));CHECK(!memcmp(RV_PTR(b14),RV_PTR(be32(new_raw+map+44)),33));}
        menu();apply_ok(next);matches_recipe(new_raw,next,new_golden);
    }
}
static void rpc_faults34(void)
{
    unsigned indices[64],count=0,i,j,mode,n,a14,b14;Gxr2View v;
    clean();ready(1);menu();if(!fixture_has_recipes())return;
    CHECK(gxr2_validate(new_raw,new_bytes,&trust,&units[unit],0,&v)==GXR2_OK);
    n=be32(new_raw+v.sections[2].offset+64*unit+12);a14=be32(new_raw+n+32+7*12);b14=be32(new_raw+n+32+8*12);
    apply_ok(1);
    for(i=0;i<rpc_calls;i++)if((trace[i].cmd==21&&(trace[i].address==a14||trace[i].address==b14-1))||
       (trace[i].cmd==22&&trace[i].address>=a14&&trace[i].address<a14+62)||
       (trace[i].cmd==22&&trace[i].address>=b14-1&&trace[i].address<b14+33)){
        if(trace[i].cmd==21)indices[count++]=i; /* preceding X, one based */
        indices[count++]=i+1;
    }
    CHECK(count==52);
    for(i=0;i<count;i++)for(mode=0;mode<6;mode++){
        clean();ready(1);menu();inject_at=indices[i];inject_action=mode;
        explicit_apply=flush_allowed=1;select_slot(1);close_key(1);explicit_apply=flush_allowed=0;
        CHECK(inject_hit&&!after_fault_w&&eng_uncertain());
        CHECK(eng_list()->applied==0&&root.state==RV_DISABLED_UNTIL_REBOOT);
        for(j=0;j<2;j++)CHECK(!fds[j].live);
    }
    printf("NEW_RPC_FAULTS calls=%u modes=6 cases=%u\n",count,count*6);
}
static void t34(unsigned mode)
{
    unsigned before;int32_t result;
    clean();ready(1);menu();if(!fixture_has_recipes())return;
    if(mode==0)t_control=0;
    else {inject_at=mode==1?1:2;inject_action=0;}
    select_slot(1);explicit_apply=flush_allowed=1;
    result=invoke(session()->entries.panel_open,0,0);explicit_apply=flush_allowed=0;
    CHECK(result!=RV_CONSUMED&&!rpc_w&&!previews&&!eng_list()->applied);
    before=rpc_calls;root.inflight=1;
    CHECK(eng_select(1)!=ENG_OK);root.inflight=0;CHECK(rpc_calls==before&&!rpc_w);
}
static void quarantine34(const uint8_t *old,unsigned bytes,unsigned attack)
{
    uint8_t last[192],tweak[GXTS_BYTES];char path[32];unsigned before;
    clean();put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);put_file("/ATA1/GXRCE.DAT",old,bytes);
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&(root.flags&RF_QUARANTINE));menu();if(!fixture_has_recipes())return;
    before=internal_mutations;
    native_fail_op=2;native_fail_path="/ATA1/GXRCE.DAT";native_fail_left=1;native_fail_code=attack?-2:-1;
    select_slot(8);open_fn2();select_slot(8);explicit_apply=flush_allowed=1;close_key(1);explicit_apply=flush_allowed=0;
    CHECK(root.state==RV_READY&&internal_mutations==before);
    file("/ATA1/GXRCE.DAT")->exists=0;menu();apply_ok(1);menu();open_fn2();
    select_slot(7);explicit_apply=flush_allowed=1;close_key(1);explicit_apply=flush_allowed=0;
    CHECK(root.flags&RF_QUARANTINE);CHECK(internal_mutations==before);
    last_path(path,0);CHECK(!file(path));tweak_path(path,1,0);CHECK(!file(path));
    (void)last;(void)tweak;
}
static void irom34(const uint8_t *old,unsigned bytes,unsigned state)
{
    clean();if(state==1)put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);
    if(state==2)put_file("/IROM/GXRCE0.DAT",old,bytes);
    if(state==4){put_file("/IROM/GXRCE0.DAT",old,bytes);put_file("/IROM/GXRCE1.DAT",old,bytes);}
    if(state==3){put_file("/IROM/GXRCE0.DAT",new_raw,1024);put_file("/IROM/GXRCE1.DAT",new_raw,1024);}
    put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&!rpc_calls);menu();
    CHECK(ig_host_install_status()==RV_OK&&(valid_irom(0)||valid_irom(1)));
    if(state==4)CHECK(file("/IROM/GXRCE1.DAT")&&file("/IROM/GXRCE1.DAT")->length==bytes&&!memcmp(file("/IROM/GXRCE1.DAT")->bytes,old,bytes));
    if(fixture_has_recipes()){apply_ok(6);matches_recipe(new_raw,6,new_golden);}
    reboot();rpc_calls=0;CHECK(rv_load(&root,&rv_trust)==RV_OK&&!rpc_calls);menu();
    CHECK(!has_recipe());
}
static void fallback34(const uint8_t *old,unsigned bytes,unsigned state)
{
    uint32_t f[32]={0};unsigned before;
    clean();
    if(state==1)put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);
    if(state==2)put_file("/IROM/GXRCE0.DAT",old,bytes);
    if(state==3)put_file("/IROM/GXRCE0.DAT",new_raw,1024);
    if(state==1){CHECK(rv_load(&root,&rv_trust)==RV_OK);menu();}
    else {
        CHECK(rv_load(&root,&rv_trust)!=RV_OK&&root.state==RV_DISABLED_UNTIL_REBOOT);
        before=opens;rv_hook_observe(&root,1,f);CHECK(!f[1]&&opens==before);
        CHECK(RV_BYTE(0x2022f5ac)==7);
    }
    CHECK(!rpc_calls&&!rpc_w&&!writes&&!previews);
}
static void blackbox34(const char *out)
{
    unsigned count;FILE *f;File *saved;
    clean();ready(1);menu();if(!fixture_has_recipes())return;
    CHECK(!log_writes);count=log_writes;select_slot(5);CHECK(count==log_writes);
    open_fn2();CHECK(log_writes>count);saved=file("/ATA1/GXRBX0.BIN");CHECK(saved&&saved->length==4096);
    count=log_writes;select_slot(8);CHECK(log_writes==count);
    close_menu();CHECK(log_writes>count&&file("/ATA1/GXRBX1.BIN"));
    f=fopen(out,"wb");CHECK(f&&fwrite(saved->bytes,1,4096,f)==4096&&!fclose(f));
}
static void legacy34(const char *dir,unsigned copies)
{
    char input[1024],path[32];uint8_t encoded[GXTS_BYTES],before[GXTS_BYTES];
    unsigned i,slot,replica;Gxr2View v;GxtsBinding binding;GxtsState state;
    if(!fixture_has_recipes())return;
    for(slot=1;slot<=8;slot++)for(rename_refuse_existing=0;rename_refuse_existing<2;rename_refuse_existing++){
        clean();snprintf(input,sizeof(input),"%s/%u-%u.BIN",dir,unit,slot);
        CHECK(load_file(input,encoded,sizeof(encoded))==GXTS_BYTES);memcpy(before,encoded,sizeof(before));
        for(replica=0;replica<copies;replica++){tweak_path(path,slot,replica);put_file(path,encoded,sizeof(encoded));}
        ready(1);menu();select_slot(slot);open_fn2();current(0);select_slot(9);
        explicit_apply=flush_allowed=1;close_key(1);explicit_apply=flush_allowed=0;
        CHECK(root.state==RV_READY&&ig_host_panel()->last_store==RV_OK);current(3);
        if(copies==2){tweak_path(path,slot,1);CHECK(file(path)&&!memcmp(file(path)->bytes,before,sizeof(before)));}
        CHECK(gxr2_validate(new_raw,new_bytes,&trust,&units[unit],0,&v)==GXR2_OK);
        CHECK(gxts_bind(&v,unit,slot,&binding)==GXTS_OK);
        tweak_path(path,slot,0);CHECK(file(path)&&gxts_decode(file(path)->bytes,file(path)->length,&binding,&state)==GXTS_OK&&state.generation==1);
        for(i=2;i<=8;i++){
            menu();select_slot(slot);open_fn2();select_slot(i%2?8:7);
            explicit_apply=flush_allowed=1;close_key(1);explicit_apply=flush_allowed=0;
            CHECK(root.state==RV_READY&&ig_host_panel()->last_store==RV_OK);
        }
    }
}
static void store_fault34(unsigned kind)
{
    static const unsigned ops[4]={3,5,6,7};char path[32];unsigned mode,slot=5,before;
    if(!fixture_has_recipes())return;
    for(mode=0;mode<4;mode++)for(rename_refuse_existing=0;rename_refuse_existing<2;rename_refuse_existing++){
        clean();ready(1);menu();apply_ok(1);menu();select_slot(slot);
        if(kind)open_fn2();
        if(kind){snprintf(path,sizeof(path),"/IROM/T%s%02u.TMP",unit==0?"50":unit==1?"28":"M0",slot-1);select_slot(8);}
        else snprintf(path,sizeof(path),"/IROM/L%s.TMP",unit==0?"50":unit==1?"28":"M0");
        native_fail_op=ops[mode];native_fail_left=1;native_fail_path=path;native_fail_code=-1;
        explicit_apply=flush_allowed=1;close_key(1);explicit_apply=flush_allowed=0;
        CHECK(fault_used);
        if(kind){matches_recipe(new_raw,slot,new_golden);}
        else {
            CHECK(root.state==RV_READY&&!(root.flags&RF_UNCERTAIN));
            before=rpc_w;menu();open_fn2();CHECK(rpc_w==before);close_menu();
            menu();apply_ok(6);CHECK(root.state==RV_READY);matches_recipe(new_raw,6,new_golden);
        }
        native_fail_left=0;native_fail_op=0;native_fail_path=0;
        reboot();rpc_calls=0;CHECK(rv_load(&root,&rv_trust)==RV_OK);menu();CHECK(!has_recipe());
    }
}
static void neighbour34(void)
{
    unsigned value,i;uint32_t map,b14;static const unsigned slots[4]={4,6,3,4};
    if(!fixture_has_recipes())return;
    map=be32(new_raw+be32(new_raw+156)+64*unit+12);b14=be32(new_raw+map+32+8*12);
    for(value=0;value<256;value++){
        clean();ready(1);menu();RV_BYTE(b14-1)=value;RV_BYTE(b14+33)=255-value;
        for(i=0;i<4;i++){menu();apply_ok(slots[i]);matches_recipe(new_raw,slots[i],new_golden);
            CHECK(RV_BYTE(b14-1)==value&&RV_BYTE(b14+33)==255-value);}
    }
}
static void quarantine_service34(void)
{
    RvRequest q={0};RvReply reply;uint32_t fd,card;
    clean();ready(1);menu();root.inflight=1;
    q.version=1;q.bytes=64;q.args[0]=root.epoch[RV_IO_E];q.args[2]=2;q.args[3]=unit+1;q.args[5]=4;q.args[8]=240;
    CHECK(rv_service(&root,RV_STORAGE,3,&q,&reply)==RV_OK);fd=reply.token;
    memset(&q,0,sizeof(q));q.version=1;q.bytes=64;q.args[0]=root.epoch[RV_IO_E];q.args[2]=1;q.args[5]=1;
    put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);
    CHECK(rv_service(&root,RV_STORAGE,2,&q,&reply)==RV_OK&&!(root.flags&RF_QUARANTINE));card=reply.token;
    memset(&q,0,sizeof(q));q.version=1;q.bytes=64;q.args[0]=root.epoch[RV_IO_E];q.args[1]=card;
    q.args[6]=session()->context.state_address;q.args[7]=16;
    native_fail_op=4;native_fail_path="/ATA1/GXRCE.DAT";native_fail_left=1;native_fail_code=-1;
    CHECK(rv_service(&root,RV_STORAGE,4,&q,&reply)==RV_IO&&(root.flags&RF_QUARANTINE));
    q.args[6]=q.args[7]=0;CHECK(rv_service(&root,RV_STORAGE,6,&q,&reply)==RV_OK);
    memset(&q,0,sizeof(q));q.version=1;q.bytes=64;q.args[0]=root.epoch[RV_IO_E];
    q.args[2]=2;q.args[3]=unit+1;q.args[5]=4;q.args[8]=240;
    CHECK(rv_service(&root,RV_STORAGE,3,&q,&reply)==RV_CONFLICT);
    q.args[8]=0;q.args[9]=2;CHECK(rv_service(&root,RV_STORAGE,7,&q,&reply)==RV_CONFLICT);
    q.args[9]=0;CHECK(rv_service(&root,RV_STORAGE,8,&q,&reply)==RV_CONFLICT);
    memset(&q,0,sizeof(q));q.version=1;q.bytes=64;q.args[0]=root.epoch[RV_IO_E];q.args[1]=fd;
    q.args[6]=session()->context.state_address;q.args[7]=16;
    CHECK(rv_service(&root,RV_STORAGE,5,&q,&reply)==RV_CONFLICT);
    q.args[6]=q.args[7]=0;CHECK(rv_service(&root,RV_STORAGE,6,&q,&reply)==RV_OK);root.inflight=0;
    CHECK(root.state==RV_READY&&(root.flags&RF_QUARANTINE));
}
static void log_fault34(void)
{
    unsigned op;uint8_t prior[4096];File *old;const char *path="/ATA1/GXRBX1.BIN";
    if(!fixture_has_recipes())return;
    for(op=3;op<=6;op++){
        clean();ready(1);menu();open_fn2();old=file("/ATA1/GXRBX0.BIN");CHECK(old&&old->length==4096);memcpy(prior,old->bytes,4096);
        native_fail_op=op;native_fail_path=path;native_fail_left=1;native_fail_code=-1;fault_used=0;
        close_menu();CHECK(fault_used&&root.state==RV_READY&&!(root.flags&RF_UNCERTAIN));
        CHECK(!memcmp(old->bytes,prior,4096));
        native_fail_left=0;native_fail_op=0;native_fail_path=0;
        menu();open_fn2();close_menu();CHECK(root.state==RV_READY);
    }
}
static void publish_failure34(unsigned mode)
{
    unsigned before;
    clean();RV_BYTE(0x2050036e)=4;ready(1);menu();if(!fixture_has_recipes())return;
    service_fault_id=mode<2?RV_SETTINGS:RV_PREVIEW;service_fault_op=mode==0?2:mode==1?3:1;
    select_slot(1);explicit_apply=flush_allowed=1;close_key(1);explicit_apply=flush_allowed=0;
    CHECK(service_fault_hit&&rpc_w==service_fault_w&&eng_uncertain()&&!eng_list()->applied);
    CHECK(root.state==RV_DISABLED_UNTIL_REBOOT);before=rpc_calls;
    root.inflight=1;CHECK(eng_select(1)==ENG_STALE);root.inflight=0;CHECK(rpc_calls==before&&eng_uncertain());
}
static void generation_fixture(uint8_t *raw,unsigned generation)
{
    Gxr2View v;memcpy(raw,new_raw,new_bytes);rv_put32(raw+28,generation);rv_put32(raw+20,0);
    rv_put32(raw+20,gxrce_crc32(raw,256));
    CHECK(gxr2_validate(raw,new_bytes,&trust,&units[unit],0,&v)==GXR2_OK);
}
static void conflict34(int mode)
{
    uint8_t raw[65537];unsigned before;
    clean();generation_fixture(raw,be32(new_raw+28)+(mode==1?1:mode==2?0:-1));
    if(mode==2){rv_put32(raw+116,be32(raw+116)+4);rv_put32(raw+20,0);rv_put32(raw+20,gxrce_crc32(raw,256));}
    if(mode==1){
        put_file("/IROM/GXRCE0.DAT",raw,new_bytes);put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);
        hidden_path[0]="/IROM/GXRCE0.DAT";hidden_left[0]=3;
    }else {put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);put_file("/ATA1/GXRCE.DAT",raw,new_bytes);}
    CHECK(rv_load(&root,&rv_trust)==RV_OK);menu();
    if(mode==1){
        CHECK(hidden_hits&&file("/IROM/GXRCE0.DAT")&&be32(file("/IROM/GXRCE0.DAT")->bytes+28)==be32(new_raw+28));
        puts("ACCEPTED_F02 synthetic next generation hidden by native open=-1 was replaced by current");
        return;
    }
    CHECK(ig_host_install_status()==RV_CONFLICT&&(root.flags&RF_QUARANTINE));before=internal_mutations;
    if(fixture_has_recipes()){apply_ok(8);file("/ATA1/GXRCE.DAT")->exists=0;menu();open_fn2();select_slot(8);
        explicit_apply=flush_allowed=1;close_key(1);explicit_apply=flush_allowed=0;
        CHECK(root.state==RV_READY&&internal_mutations==before&&(root.flags&RF_QUARANTINE));}
}
static void daily34(unsigned mode)
{
    char path[32];unsigned before,pass;File *saved;
    if(!fixture_has_recipes())return;
    clean();put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);
    if(mode==0){
        put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);
        CHECK(rv_load(&root,&rv_trust)==RV_OK);menu();close_menu();
        CHECK(file("/ATA1/GXRCE.OK")&&!file("/ATA1/GXRCE.DAT"));reboot();
    }
    if(mode==4){put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);native_fail_op=2;native_fail_path="/ATA1/GXRCE.DAT";native_fail_left=100000;}
    if(mode==5)put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);
    for(pass=0;pass<2;pass++){
        if(pass)reboot();
        if(mode==2){root.flags&=~RF_SD;sd_failure=2;}
        if(mode==3)sd_failure=1;
        rpc_calls=t_reads=0;before=internal_mutations;
        CHECK(rv_load(&root,&rv_trust)==RV_OK&&!(root.flags&RF_QUARANTINE));
        if(mode==5&&file("/ATA1/GXRCE.DAT"))file("/ATA1/GXRCE.DAT")->exists=0;
        menu();CHECK(!rpc_calls&&!has_recipe()&&root.state==RV_READY&&!(root.flags&RF_QUARANTINE));
        CHECK(session()->cursor==(pass?7u:0u));
        if(pass){open_fn2();current(3);close_menu();CHECK(root.state==RV_READY);continue;}
        select_slot(8);open_fn2();current(0);select_slot(9);
        explicit_apply=flush_allowed=1;close_key(1);explicit_apply=flush_allowed=0;
        CHECK(root.state==RV_READY&&ig_host_panel()->last_store==RV_OK&&internal_mutations>before);
        current(3);tweak_path(path,8,0);saved=file(path);CHECK(saved&&saved->length==GXTS_BYTES);
        last_path(path,0);saved=file(path);CHECK(saved&&saved->length==192&&saved->bytes[16]==8);
        menu();apply_ok(6);last_path(path,1);saved=file(path);CHECK(saved&&saved->bytes[16]==6);
        menu();apply_ok(8);CHECK(root.state==RV_READY);
    }
    if(mode==2||mode==3)CHECK(!log_writes);
    printf("DAILY mode=%u Fn2_saved=3 OK_updates_GXLS=1 cold_cursor=8 cold_tweak=3\n",mode);
}
static void rejected34(unsigned mode,const uint8_t *old,unsigned bytes)
{
    uint8_t raw[65537];unsigned before,pass;
    clean();put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);
    memcpy(raw,new_raw,new_bytes);
    if(mode==0)put_file("/ATA1/GXRCE.DAT",old,bytes);
    else{
        if(mode==1)raw[80]^=1;
        if(mode==5)raw[256]^=1;
        put_file("/ATA1/GXRCE.DAT",raw,new_bytes);
    }
    if(mode==2||mode==4){native_fail_op=4;native_fail_skip=mode==4?4:0;native_fail_left=1;native_fail_path="/ATA1/GXRCE.DAT";}
    if(mode==3||mode==6){native_fail_op=6;native_fail_skip=mode==3?1:2;native_fail_left=1;native_fail_path="/ATA1/GXRCE.DAT";}
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&(root.flags&RF_QUARANTINE));
    CHECK(session()->selected_source==RV_SOURCE_A);
    if(mode>=2&&mode!=5)CHECK(fault_used);
    before=internal_mutations;native_fail_skip=0;
    for(pass=0;pass<3;pass++){
        native_fail_op=2;native_fail_path="/ATA1/GXRCE.DAT";native_fail_left=pass==1?100000:1;native_fail_code=-1;
        if(pass==2)file("/ATA1/GXRCE.DAT")->exists=0;
        menu();if(fixture_has_recipes()){apply_ok(8);menu();open_fn2();select_slot(9);
            explicit_apply=flush_allowed=1;close_key(1);explicit_apply=flush_allowed=0;
            CHECK(root.state==RV_READY&&internal_mutations==before);}
        CHECK(root.flags&RF_QUARANTINE);
    }
    native_fail_left=native_fail_op=0;native_fail_path=0;
    printf("REJECT mode=%u sticky_after_transient_minus1=1 zero_internal_writes=1\n",mode);
}
static void r33_counterexamples34(const uint8_t *old,unsigned bytes)
{
    unsigned rename,explicit_save,mode,before;
    if(!fixture_has_recipes())return;
    for(rename=0;rename<2;rename++)for(explicit_save=0;explicit_save<2;explicit_save++)for(mode=0;mode<3;mode++){
        clean();rename_refuse_existing=rename;
        put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);put_file("/ATA1/GXRCE.DAT",old,bytes);
        CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->selected_source==RV_SOURCE_A&&(root.flags&RF_QUARANTINE));
        menu();select_slot(8);if(explicit_save){open_fn2();select_slot(9);}
        before=internal_mutations;native_fail_op=mode==2?6:2;native_fail_code=mode==1?-2:-1;
        native_fail_left=1;native_fail_path="/ATA1/GXRCE.DAT";
        explicit_apply=flush_allowed=1;close_key(explicit_save);explicit_apply=flush_allowed=0;
        CHECK(root.state==RV_READY&&internal_mutations==before&&(root.flags&RF_QUARANTINE));
        native_fail_left=0;file("/ATA1/GXRCE.DAT")->exists=0;
        menu();open_fn2();select_slot(8);explicit_apply=flush_allowed=1;close_key(1);explicit_apply=flush_allowed=0;
        CHECK(root.state==RV_READY&&internal_mutations==before&&(root.flags&RF_QUARANTINE));
    }
    printf("R33_REFUSED counterexamples=4 controls=8 unit=%u\n",unit);
}
 #include "host_r28.inc.c"
/* Independent checks of the mutation boundary, snapshot lifetime and card state. */
static void review_cases(const uint8_t *old,unsigned old_bytes)
{
    unsigned kind,depth,capacity,before,i;uint32_t f[32],g[32],snapshot;
    uint8_t state[32],desc[72],views[64];
    for(kind=0;kind<4;kind++)for(depth=1;depth<=2;depth++){
        clean();ready(0);
        if(kind==1)native_writer_exposure();
        if(kind==2)native_writer_white_balance();
        if(kind==3)native_writer_image();
        RV_BYTE(RV_NATIVE_VIEWS)=depth==1?32:33;
        RV_BYTE(RV_NATIVE_VIEWS+8)=33;RV_WORD(RV_NATIVE_VIEWS+12)=0x2022f71c;
        RV_BYTE(0x205a27d4)=depth;
        memcpy(state,RV_PTR(0x2022f71c),32);memcpy(desc,RV_PTR(0x2022f56c),72);
        memcpy(views,RV_PTR(RV_NATIVE_VIEWS),64);
        before=rpc_calls;memset(f,0,sizeof(f));rv_hook_observe(&root,1,f);
        CHECK(rpc_calls==before&&!rpc_w&&!previews);
        CHECK(!memcmp(views,RV_PTR(RV_NATIVE_VIEWS),64));
        for(i=0;i<32;i++)if(i!=9&&i!=10)CHECK(state[i]==RV_BYTE(0x2022f71c+i));
        for(i=0;i<72;i++)if(i<60||i>64)CHECK(desc[i]==RV_BYTE(0x2022f56c+i));
        CHECK(f[1]&&RV_BYTE(0x2022f5ac)==8&&session()->rows==8);
        snapshot=root.ui_block;CHECK(snapshot&&rv_ui_snapshot(&root)->state[0]==5);
        memset(g,0,sizeof(g));rv_hook_observe(&root,2,g);CHECK(g[7]==f[15]);
        /* The complete native writer/consumer trace is replayed separately. */
        native_writer_image();RV_BYTE(0x2022f725)=RV_BYTE(0x2022f726)=g[7];
        RV_BYTE(RV_NATIVE_VIEWS)=33;
        RV_WORD(RV_NATIVE_VIEWS+4)=0x2022f71c;RV_BYTE(0x205a27d4)=1;
        RV_BYTE(0x2022f727)=0x61;RV_BYTE(0x2022f728)=0x62;
        for(i=0;i<5;i++)RV_BYTE(0x2022f729+i)=(uint8_t)(0x70+i);
        open_fn2();CHECK(RV_WORD(RV_NATIVE_VIEWS+4)==snapshot);
        CHECK(rv_ui_snapshot(&root)->state[11]==0x61&&rv_ui_snapshot(&root)->state[12]==0x62);
        for(i=0;i<5;i++)CHECK(rv_ui_snapshot(&root)->state[13+i]==0x70+i);
        close_menu();CHECK(RV_WORD(RV_NATIVE_VIEWS+4)==0x2022f71c);
        CHECK(RV_WORD(0x2022f5a8)==0x2022d610&&RV_BYTE(0x2022f5ac)==7);
        CHECK(owned(snapshot,1968));rv_retire(&root,RV_CHECK_SESSION);CHECK(owned(snapshot,1968));
    }
    for(capacity=236;capacity<=256;capacity++){
        clean();ready(0);session()->context.ui_state_capacity=capacity;
        memset(RV_PTR(session()->context.ui_state_address),0xa5,256);
        CHECK(rv_native_seed(&session()->context)==RV_OK);
        for(i=236;i<256;i++)CHECK(RV_BYTE(session()->context.ui_state_address+i)==0xa5);
    }
    /* Preserve the first H01 diagnostic by closing without a cursor event. */
    {
        clean();ready(0);menu();native_writer_image();close_menu();
        CHECK(!rpc_calls&&!has_recipe()&&file("/ATA1/GXRBX0.BIN"));
        CHECK(file("/ATA1/GXRBX0.BIN")->bytes[2460]==0);
        clean();ready(0);menu();native_writer_image();select_slot(2);close_menu();
        CHECK(!rpc_calls&&!has_recipe()&&file("/ATA1/GXRBX0.BIN")->bytes[2460]==5);
        puts("REVIEW first_MENU_exit seed_kind=0 no_RPC=1; after_cursor seed_kind=5 first_seed_retained_tested_separately=1");
    }
    /* Mirror today's stale OK, then show the corrected procedure converges. */
    clean();CHECK(be32(old+28)==113);put_file("/IROM/GXRCE0.DAT",old,old_bytes);
    put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);
    put_file("/ATA1/GXRCE.OK",old,old_bytes);rename_refuse_existing=1;
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->selected_source==RV_SOURCE_CARD);
    memset(f,0,sizeof(f));flush_allowed=1;rv_hook_observe(&root,1,f);flush_allowed=0;
    CHECK(ig_host_install_status()==RV_UNCERTAIN&&root.state==RV_DISABLED_UNTIL_REBOOT);
    CHECK(file("/IROM/GXRCE0.DAT")&&!memcmp(file("/IROM/GXRCE0.DAT")->bytes,old,old_bytes));
    CHECK(file("/IROM/GXRCE1.DAT")&&!memcmp(file("/IROM/GXRCE1.DAT")->bytes,new_raw,new_bytes));
    CHECK(file("/ATA1/GXRCE.OK")&&!memcmp(file("/ATA1/GXRCE.OK")->bytes,old,old_bytes));
    printf("REVIEW stale_OK install=%d state=%u DAT_exists=%u OK_exists=%u\n",
        ig_host_install_status(),root.state,file("/ATA1/GXRCE.DAT")!=0,file("/ATA1/GXRCE.OK")!=0);
    clean();put_file("/IROM/GXRCE0.DAT",old,old_bytes);
    put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);rename_refuse_existing=1;
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->selected_source==RV_SOURCE_CARD);
    memset(f,0,sizeof(f));rv_hook_observe(&root,1,f);
    CHECK(ig_host_install_status()==RV_OK&&session()->generation==115&&session()->rows==8);
    CHECK(file("/IROM/GXRCE0.DAT")&&!memcmp(file("/IROM/GXRCE0.DAT")->bytes,old,old_bytes));
    CHECK(file("/IROM/GXRCE1.DAT")&&!memcmp(file("/IROM/GXRCE1.DAT")->bytes,new_raw,new_bytes));
    CHECK(file("/ATA1/GXRCE.OK")&&!memcmp(file("/ATA1/GXRCE.OK")->bytes,new_raw,new_bytes));
    CHECK(!file("/ATA1/GXRCE.DAT"));file("/ATA1/GXRCE.OK")->exists=0;
    reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->generation==115&&session()->selected_source==RV_SOURCE_B);
    menu();CHECK(session()->rows==8);
    puts("REVIEW exact_113_to_115 old_preserved=1 OK_exact=1 cardless_IROM115=1");
    printf("REVIEW bounded_private_seed capacities=21 mutation_cases=8 snapshot_retained=1\n");
}


static void changing_neighbor_probe(void)
{
    uint32_t map=be32(new_raw+be32(new_raw+156)+64*unit+12);
    uint32_t neighbor=be32(new_raw+map+24)+1;
    unsigned first,after;
    clean();ready(0);menu();RV_BYTE(neighbor)=0x5a;
    apply_ok(1);CHECK(RV_BYTE(neighbor)==0x5a);
    first=RV_BYTE(neighbor);RV_BYTE(neighbor)=0xa5;
    menu();apply_ok(2);after=RV_BYTE(neighbor);
    CHECK(root.state==RV_READY&&after==first);
    printf("PROBE {\"unit\":%u,\"neighbor_address\":%u,\"first_live\":90,\"later_live\":165,\"after_apply\":%u,\"hardware_writer_proven\":false}\n",
        unit,neighbor,after);
}

int main(int argc,char **argv)
{
    uint8_t rawtrust[232],old[65537];unsigned i,state,old_bytes;
    CHECK(argc>=8);scenario="v34c";unit=(unsigned)strtoul(argv[2],0,10);CHECK(unit<3);
    new_bytes=load_file(argv[3],new_raw,sizeof(new_raw));base_bytes=new_bytes;memcpy(base_raw,new_raw,new_bytes);
    CHECK(load_file(argv[4],rawtrust,sizeof(rawtrust))==232);CHECK(load_file(argv[5],new_golden,sizeof(new_golden))==sizeof(new_golden));memcpy(golden,new_golden,sizeof(golden));
    old_bytes=load_file(argv[6],old,sizeof(old));
    memcpy(trust.body_sha256,rawtrust+8,32);memcpy(trust.resident_build_id,rawtrust+40,32);memcpy(trust.resident_abi_id,rawtrust+72,16);
    for(i=0;i<3;i++){trust.modules[i].unit=units[i];trust.modules[i].stock_crc32=be32(rawtrust+100+48*i);memcpy(trust.modules[i].stock_sha256,rawtrust+104+48*i,32);}
    if(!strcmp(argv[1],"changing-neighbor"))changing_neighbor_probe();
    else if(!strcmp(argv[1],"review"))review_cases(old,old_bytes);
    else if(!strcmp(argv[1],"seed115"))seed115(argv[7]);
    else if(!strcmp(argv[1],"fallback115"))fallback115();
    else if(!strcmp(argv[1],"update115"))update115(old,old_bytes,(unsigned)atoi(argv[7]));
    else if(!strcmp(argv[1],"sticky115"))sticky115(argv[7]);
    else if(!strcmp(argv[1],"adjacency115"))adjacency115();
    else if(!strcmp(argv[1],"bindings115"))bindings115(old,old_bytes);
    else if(!strcmp(argv[1],"basic"))basic();
    else if(!strcmp(argv[1],"first"))first_frame34();
    else if(!strcmp(argv[1],"ctl"))control34((unsigned)strtoul(argv[7],0,10));
    else if(!strcmp(argv[1],"iso"))iso34((unsigned)strtoul(argv[7],0,10));
    else if(!strcmp(argv[1],"rpc-faults"))rpc_faults34();
    else if(!strcmp(argv[1],"t"))t34((unsigned)strtoul(argv[7],0,10));
    else if(!strcmp(argv[1],"quarantine"))quarantine34(old,old_bytes,(unsigned)strtoul(argv[7],0,10));
    else if(!strcmp(argv[1],"irom")){for(state=0;state<5;state++)irom34(old,old_bytes,state);for(state=0;state<4;state++)fallback34(old,old_bytes,state);}
    else if(!strcmp(argv[1],"blackbox"))blackbox34(argv[7]);
    else if(!strcmp(argv[1],"legacy"))legacy34(argv[7],argc>8?(unsigned)atoi(argv[8]):2);
    else if(!strcmp(argv[1],"store-fault"))store_fault34((unsigned)atoi(argv[7]));
    else if(!strcmp(argv[1],"neighbour"))neighbour34();
    else if(!strcmp(argv[1],"service-quarantine"))quarantine_service34();
    else if(!strcmp(argv[1],"log-fault"))log_fault34();
    else if(!strcmp(argv[1],"publish-failure"))publish_failure34((unsigned)atoi(argv[7]));
    else if(!strcmp(argv[1],"conflict"))conflict34(0);
    else if(!strcmp(argv[1],"accepted-f02"))conflict34(1);
    else if(!strcmp(argv[1],"same-conflict"))conflict34(2);
    else if(!strcmp(argv[1],"daily"))daily34((unsigned)atoi(argv[7]));
    else if(!strcmp(argv[1],"rejected"))rejected34((unsigned)atoi(argv[7]),old,old_bytes);
    else if(!strcmp(argv[1],"r33"))r33_counterexamples34(old,old_bytes);
    else CHECK(0);
    CHECK(opens==closes);for(i=0;i<2;i++)CHECK(!fds[i].live);
    printf("OK case=%s unit=%u assertions=%u rpc=%u internal=%u logs=%u\n",argv[1],unit,assertions,rpc_calls,internal_mutations,log_writes);
    return 0;
}
