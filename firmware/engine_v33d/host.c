/* Adapted from the passing round-4 fixture; product and resident C stay frozen. */
#define main full_r3_fixture_main
#define rv_native_open fixture_open
#define rv_native_create fixture_create
#define rv_native_write fixture_write
#define rv_native_delete fixture_delete
#define rv_native_rename fixture_rename
#include "containers/product/host_checks.c"
#undef main
#undef rv_native_open
#undef rv_native_create
#undef rv_native_write
#undef rv_native_delete
#undef rv_native_rename

typedef struct { unsigned create,write,remove,rename; } Mutations;
static Mutations mutations,readonly_start;
static File before_files[64];
static unsigned policy,save_slot,missing_minus1,old_generation;
static const char *phase="setup",*evidence_dir;
static uint8_t saved[3][GXTS_BYTES];
static const unsigned saved_slots[3]={1,2,5};
static const int8_t saved_values[ENG_PARAMS]={3,2,-2,1,0,0,0,0};

static void slot_tweak_path(char out[32],unsigned slot,unsigned copy)
{
    const char *name=unit==0?"50":unit==1?"28":"M0";
    CHECK(snprintf(out,32,"/IROM/T%s%02u%c.BIN",name,slot-1,'A'+copy)>0);
}
static void mutation_path(const char *path)
{
    char a[32],b[32],tmp[32];
    CHECK(policy!=1);
    if(policy==2) {
        slot_tweak_path(a,save_slot,0);slot_tweak_path(b,save_slot,1);
        CHECK(snprintf(tmp,sizeof(tmp),"%.11s.TMP",a)>0);
        CHECK(!strcmp(path,a)||!strcmp(path,b)||!strcmp(path,tmp));
    }
    if(policy==3)CHECK(!strcmp(path,"/IROM/GXRCE0.DAT")||!strcmp(path,"/IROM/GXRCE1.DAT")||
        !strcmp(path,"/IROM/GXRCE.TMP")||!strcmp(path,"/ATA1/GXRCE.DAT")||!strcmp(path,"/ATA1/GXRCE.OK"));
}
int32_t rv_native_open(const char *path,uint32_t flags)
{
    int32_t result=fixture_open(path,flags);
    if(result==-1)++missing_minus1;
    return result;
}
int32_t rv_native_create(const char *path,uint32_t flags)
{
    ++mutations.create;mutation_path(path);
    if(policy)printf("MUTATION phase=%s op=create path=%s\n",phase,path);
    return fixture_create(path,flags);
}
int32_t rv_native_write(int32_t handle,const void *p,uint32_t n)
{
    unsigned fd=(unsigned)(handle-17);int32_t result;
    CHECK(fd<2&&fds[fd].live);++mutations.write;mutation_path(files[fds[fd].file].path);
    result=fixture_write(handle,p,n);
    if(policy)printf("MUTATION phase=%s op=write path=%s actual=%d\n",phase,files[fds[fd].file].path,result);
    return result;
}
int32_t rv_native_delete(const char *path)
{
    ++mutations.remove;mutation_path(path);
    if(policy)printf("MUTATION phase=%s op=delete path=%s\n",phase,path);
    return fixture_delete(path);
}
int32_t rv_native_rename(const char *from,const char *to)
{
    ++mutations.rename;mutation_path(from);mutation_path(to);
    if(policy)printf("MUTATION phase=%s op=rename from=%s to=%s\n",phase,from,to);
    return fixture_rename(from,to);
}
static void readonly_begin(const char *name)
{
    phase=name;readonly_start=mutations;memcpy(before_files,files,sizeof(files));policy=1;
}
static void readonly_end(void)
{
    CHECK(!memcmp(&mutations,&readonly_start,sizeof(mutations)));
    CHECK(!memcmp(files,before_files,sizeof(files)));
    printf("READONLY_PASS phase=%s create=0 write=0 delete=0 rename=0 all_files_identical=1\n",phase);
    policy=0;
}
static void check_file(const char *path,const uint8_t *bytes,unsigned n)
{ File *f=file(path);CHECK(f&&f->length==n&&!memcmp(f->bytes,bytes,n)); }
static void external_remove(const char *path)
{ File *f=file(path);CHECK(f);f->exists=0;printf("EXTERNAL_REMOVE path=%s\n",path); }
static void dump(const char *path,const char *name)
{
    char destination[1024];File *f=file(path);FILE *out;
    if(!f)return;
    CHECK(snprintf(destination,sizeof(destination),"%s/%s",evidence_dir,name)>0);
    out=fopen(destination,"wb");CHECK(out);
    CHECK(fwrite(f->bytes,1,f->length,out)==f->length);CHECK(!fclose(out));
}
static unsigned slot_count(void){return unit==0?3u:unit==2?2u:0u;}
static int changed(unsigned slot)
{
    if(old_generation==105)return (unit==0&&(slot==1||slot==2))||(unit==2&&(slot==1||slot==2));
    CHECK(old_generation==106||old_generation==107);
    if(old_generation==107)return 0;
    return (unit==0||unit==2)&&slot==2;
}
static void current_values(unsigned slot,int kept)
{
    static const int8_t defaults[ENG_PARAMS]={0};EngRecipeRef ref;EngTweak t;
    root.inflight=1;CHECK(eng_current(&ref,&t)==ENG_OK);root.inflight=0;
    CHECK(ref.unit==unit&&ref.slot==slot);
    CHECK(!memcmp(t.v,kept?saved_values:defaults,ENG_PARAMS));
}
static unsigned selected_mask(void)
{
    unsigned i,mask=0;
    for(i=0;i<slot_count();++i)mask|=1u<<(saved_slots[i]-1);
    return mask;
}
static void rows(const uint8_t *raw,const uint8_t *expected,unsigned saved_mask,int panels)
{
    unsigned slot,i,length,bank=be32(raw+be32(raw+156)+64*unit+16);
    const EngList *list=eng_list();RvUiSnapshot *ui=rv_ui_snapshot(&root);char label[33];
    if(unit==1) {CHECK(root.state==RV_READY&&!ui&&!list->opened&&RV_BYTE(0x2022f5ac)==7);matches_stock();return;}
    CHECK(root.state==RV_READY&&session()->rows==fixture_rows()&&ui&&list->opened);
    for(slot=1;slot<=fixture_rows();++slot) {
        const uint8_t *record=raw+bank+32+64*(slot-1);
        if(record[1]){length=record[2];CHECK(length<=32);memcpy(label,record+4,length);label[length]=0;}
        else {CHECK(snprintf(label,sizeof(label),"%02u",slot)>0);length=2;}
        CHECK(!strcmp(list->row[slot-1].ascii,label));
        for(i=0;i<length;++i)CHECK(ui->glyphs[slot-1][2*i]==1&&ui->glyphs[slot-1][2*i+1]==(uint8_t)label[i]);
        CHECK(!ui->glyphs[slot-1][2*length]);
        printf("ROW phase=%s generation=%u slot=%02u label=%s\n",phase,be32(raw+28),slot,label);
    }
    for(slot=1;slot<=fixture_rows();++slot) {
        int kept=(saved_mask&(1u<<(slot-1)))!=0;
        select_slot(slot);current_values(slot,kept);
        if(!kept)matches_recipe(raw,slot,expected);
        if(panels) {
            panel_open();CHECK(root.state==RV_READY&&ig_host_panel()->last_store==RV_OK);
            CHECK(strcmp(ig_host_panel()->text[0],"SaveFail"));close_key(0);menu();
        }
    }
    CHECK(root.state==RV_READY&&session()->rows==fixture_rows());
}
static void load_generation(unsigned generation,unsigned source)
{
    int32_t result=rv_load(&root,&rv_trust);
    printf("LOAD phase=%s result=%d generation=%u source=%u state=%u\n",phase,result,session()->generation,session()->selected_source,root.state);
    CHECK(result==RV_OK&&root.state==RV_READY&&session()->generation==generation&&session()->selected_source==source);
}
static void install_first(const uint8_t *raw,unsigned n,const uint8_t *expected)
{
    CHECK(!file("/IROM/GXRCE0.DAT")&&!file("/IROM/GXRCE1.DAT"));
    CHECK(rv_native_open("/IROM/absent",0)==-1);
    put_file("/ATA1/GXRCE.DAT",raw,n);load_generation(be32(raw+28),RV_SOURCE_CARD);menu();
    CHECK(root.state==RV_READY&&ig_host_install_status()==RV_OK);
    CHECK(!file("/ATA1/GXRCE.DAT"));check_file("/ATA1/GXRCE.OK",raw,n);check_file("/IROM/GXRCE0.DAT",raw,n);
    CHECK(!file("/IROM/GXRCE1.DAT"));rows(raw,expected,0,0);
}
static void update_clean(void)
{
    external_remove("/ATA1/GXRCE.OK");CHECK(!file("/ATA1/GXRCE.DAT"));
    put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);reboot();load_generation(109,RV_SOURCE_CARD);menu();
    CHECK(root.state==RV_READY&&ig_host_install_status()==RV_OK);
    CHECK(!file("/ATA1/GXRCE.DAT"));check_file("/ATA1/GXRCE.OK",new_raw,new_bytes);
    check_file("/IROM/GXRCE0.DAT",base_raw,base_bytes);check_file("/IROM/GXRCE1.DAT",new_raw,new_bytes);
}
static void binding(const uint8_t *raw,unsigned bytes,unsigned slot,GxtsBinding *b)
{
    Gxr2View view;CHECK(gxr2_validate(raw,bytes,&trust,&units[unit],0,&view)==GXR2_OK);
    CHECK(gxts_bind(&view,unit,slot,b)==GXTS_OK);
}
static void verify_saved(unsigned index,int cold109)
{
    char path[32],name[64];unsigned i,slot=saved_slots[index];GxtsBinding old_binding,new_binding;GxtsState state;
    GxtsStatus status;File *f;
    slot_tweak_path(path,slot,0);f=file(path);CHECK(f&&f->length==GXTS_BYTES);
    CHECK(!memcmp(f->bytes,saved[index],GXTS_BYTES));slot_tweak_path(path,slot,1);CHECK(!file(path));
    binding(base_raw,base_bytes,slot,&old_binding);binding(new_raw,new_bytes,slot,&new_binding);
    CHECK(gxts_decode(f->bytes,f->length,&old_binding,&state)==GXTS_OK&&state.generation==1);
    for(i=0;i<6;++i)CHECK(state.values[i]==saved_values[i]);
    status=gxts_decode(f->bytes,f->length,&new_binding,&state);
    CHECK(status==(changed(slot)?GXTS_IDENTITY:GXTS_OK));
    menu();select_slot(slot);current_values(slot,!cold109||!changed(slot));panel_open();
    CHECK(root.state==RV_READY&&ig_host_panel()->last_store==RV_OK&&strcmp(ig_host_panel()->text[0],"SaveFail"));
    close_key(0);menu();
    slot_tweak_path(path,slot,0);CHECK(snprintf(name,sizeof(name),"slot-%02u-%s.BIN",slot,cold109?"cold109":"saved-old")>0);dump(path,name);
    printf("GXTS_PASS phase=%s unit=%u slot=%u effective=%s file_generation=1 bytes=240 old_binding=OK new_binding=%s old_file_retained=1 SaveFail=0 disabled=0\n",
           phase,unit,slot,cold109&&changed(slot)?"0,0,0,0,0,0":"3,2,-2,1,0,0",changed(slot)?"IDENTITY":"OK");
}
static void save_tweak(unsigned index)
{
    static const unsigned panel_row[4]={9,8,4,7};char path[32],tmp[32];
    unsigned i,slot=saved_slots[index];Mutations start;
    phase="save-old";save_slot=slot;menu();select_slot(slot);close_key(0);menu();
    start=mutations;memcpy(before_files,files,sizeof(files));policy=2;panel_open();
    for(i=0;i<4;++i) {
        if(i)panel_open();
        CHECK(ig_host_panel()->parameter==i&&ig_host_panel()->last_store==RV_OK);
        CHECK(strcmp(ig_host_panel()->text[0],"SaveFail"));select_slot(panel_row[i]);
    }
    close_key(1);CHECK(root.state==RV_READY&&ig_host_panel()->last_store==RV_OK);
    CHECK(strcmp(ig_host_panel()->text[0],"SaveFail"));
    slot_tweak_path(path,slot,0);CHECK(file(path)&&file(path)->length==GXTS_BYTES);memcpy(saved[index],file(path)->bytes,GXTS_BYTES);
    CHECK(snprintf(tmp,sizeof(tmp),"%.11s.TMP",path)>0);CHECK(!file(tmp));
    for(i=0;i<64;++i)if(strncmp(files[i].path,path,11))CHECK(!memcmp(&files[i],&before_files[i],sizeof(File)));
    CHECK(mutations.create==start.create+1&&mutations.write>start.write&&mutations.rename==start.rename+1&&mutations.remove==start.remove);
    printf("SAVE_PASS unit=%u slot=%u allowed=1 create=%u write=%u delete=%u rename=%u path=%s values=3,2,-2,1,0,0 binding_generation=%u\n",
           unit,slot,mutations.create-start.create,mutations.write-start.write,mutations.remove-start.remove,mutations.rename-start.rename,path,old_generation);
    policy=0;verify_saved(index,0);
}
static void cold109(unsigned source,int keep_ok)
{
    unsigned i,mask=selected_mask();
    if(file("/ATA1/GXRCE.DAT"))external_remove("/ATA1/GXRCE.DAT");
    if(!keep_ok)external_remove("/ATA1/GXRCE.OK");
    CHECK(!file("/ATA1/GXRCE.DAT"));
    if(keep_ok)check_file("/ATA1/GXRCE.OK",new_raw,new_bytes);else CHECK(!file("/ATA1/GXRCE.OK"));
    readonly_begin("cold109");reboot();load_generation(109,source);menu();readonly_end();
    CHECK(ig_host_install_status()==RV_UNAVAILABLE);
    for(i=0;i<slot_count();++i)if(changed(saved_slots[i]))mask&=~(1u<<(saved_slots[i]-1));
    rows(new_raw,new_golden,mask,1);
    for(i=0;i<slot_count();++i)verify_saved(i,1);
    printf("IV_B_PASS unit=%u generation=109 source=%u rows=16 card=%s no_writes=1 SaveFail=0 disabled=0\n",unit,source,keep_ok?"OK-only":"empty");
}
static void conflict(int pair,int keep_ok)
{
    unsigned i;static const uint8_t sentinel[]={7,9,23,41};
    if(pair){install_first(base_raw,base_bytes,golden);update_clean();}
    else install_first(new_raw,new_bytes,new_golden);
    put_file("/ATA1/KEEP.TXT",sentinel,sizeof(sentinel));put_file("/IROM/KEEP.BIN",sentinel,sizeof(sentinel));
    put_file("/ATA1/GXRCE.DAT",base_raw,base_bytes);
    readonly_begin("old-card");reboot();load_generation(old_generation,RV_SOURCE_CARD);menu();
    CHECK(ig_host_install_status()==RV_CONFLICT);rows(base_raw,golden,0,1);
    CHECK(ig_host_install_status()==RV_CONFLICT);readonly_end();
    printf("IV_A_PASS unit=%u layout=%s generation=%u source=CARD install=RV_CONFLICT rows=16 no_writes=1 SaveFail=0 disabled=0\n",unit,pair?"old-A/new-B":"new-A",old_generation);
    for(i=0;i<slot_count();++i)save_tweak(i);
    cold109(pair?RV_SOURCE_B:RV_SOURCE_A,keep_ok);
    check_file("/ATA1/KEEP.TXT",sentinel,sizeof(sentinel));check_file("/IROM/KEEP.BIN",sentinel,sizeof(sentinel));
    if(pair){check_file("/IROM/GXRCE0.DAT",base_raw,base_bytes);check_file("/IROM/GXRCE1.DAT",new_raw,new_bytes);}
    else {check_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);CHECK(!file("/IROM/GXRCE1.DAT"));}
}
static void gxts_update(void)
{
    unsigned i;
    install_first(base_raw,base_bytes,golden);
    for(i=0;i<slot_count();++i)save_tweak(i);
    readonly_begin("cold-old");reboot();load_generation(old_generation,RV_SOURCE_A);menu();readonly_end();
    rows(base_raw,golden,selected_mask(),1);for(i=0;i<slot_count();++i)verify_saved(i,0);
    phase="update107";policy=3;update_clean();policy=0;
    readonly_begin("updated107");menu();readonly_end();
    for(i=0;i<slot_count();++i)verify_saved(i,1);
    cold109(RV_SOURCE_B,1);
    printf("D_PASS old=%u saved=1 delete_OK_first=1 installed107=1 cold109=1 SaveFail=0 disabled=0\n",old_generation);
}
int main(int argc,char **argv)
{
    uint8_t rawtrust[232];unsigned i;
    if(argc!=9)return 2;
    scenario=argv[1];unit=(unsigned)strtoul(argv[2],0,10);CHECK(unit<3);evidence_dir=argv[8];
    base_bytes=load_file(argv[3],base_raw,sizeof(base_raw));new_bytes=load_file(argv[4],new_raw,sizeof(new_raw));
    old_generation=be32(base_raw+28);
    CHECK((old_generation==105||old_generation==106||old_generation==107)&&be32(new_raw+28)==109);
    CHECK(load_file(argv[5],rawtrust,sizeof(rawtrust))==232);
    CHECK(load_file(argv[6],golden,sizeof(golden))==sizeof(golden));
    CHECK(load_file(argv[7],new_golden,sizeof(new_golden))==sizeof(new_golden));
    memcpy(trust.body_sha256,rawtrust+8,32);memcpy(trust.resident_build_id,rawtrust+40,32);memcpy(trust.resident_abi_id,rawtrust+72,16);
    for(i=0;i<3;++i){memcpy(&trust.modules[i].unit,&units[i],sizeof(units[i]));trust.modules[i].stock_crc32=be32(rawtrust+100+48*i);memcpy(trust.modules[i].stock_sha256,rawtrust+104+48*i,32);}
    (void)es_aliases_unused;rename_refuse_existing=1;reboot();
    if(!strcmp(scenario,"r5-conflict-pair-ok"))conflict(1,1);
    else if(!strcmp(scenario,"r5-conflict-pair-empty"))conflict(1,0);
    else if(!strcmp(scenario,"r5-conflict-single-ok"))conflict(0,1);
    else if(!strcmp(scenario,"r5-conflict-single-empty"))conflict(0,0);
    else if(!strcmp(scenario,"r5-update-reject")||!strcmp(scenario,"r5-update-replace")) {
        rename_refuse_existing=strstr(scenario,"reject")!=NULL;gxts_update();
    }
    else if(!strcmp(scenario,"r5-first-reject")||!strcmp(scenario,"r5-first-replace")) {
        rename_refuse_existing=strstr(scenario,"reject")!=NULL;
        install_first(new_raw,new_bytes,new_golden);
        readonly_begin("first-cold109");reboot();load_generation(109,RV_SOURCE_A);menu();readonly_end();
        CHECK(ig_host_install_status()==RV_UNAVAILABLE);rows(new_raw,new_golden,0,1);
        check_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);CHECK(!file("/IROM/GXRCE1.DAT"));
        check_file("/ATA1/GXRCE.OK",new_raw,new_bytes);
        puts("FIRST_PASS generation=109 rows=16 DAT_to_OK=1 cold109=1 SaveFail=0 disabled=0");
    }
    else CHECK(0);
    CHECK(opens==closes&&missing_minus1>0&&!native_fail_op&&!hidden_left[0]&&!hidden_left[1]);
    for(i=0;i<2;++i)CHECK(!fds[i].live);
    dump("/IROM/GXRCE0.DAT","IROM-GXRCE0.DAT");dump("/IROM/GXRCE1.DAT","IROM-GXRCE1.DAT");
    dump("/ATA1/GXRCE.DAT","card-GXRCE.DAT");dump("/ATA1/GXRCE.OK","card-GXRCE.OK");
    printf("OK scenario=%s unit=%u assertions=%u missing_open=-1 missing_count=%u creates=%u writes=%u deletes=%u renames=%u\n",scenario,unit,assertions,missing_minus1,mutations.create,mutations.write,mutations.remove,mutations.rename);
    return 0;
}
