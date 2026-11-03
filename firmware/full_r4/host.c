/* Extend the existing fixture; product and resident C are compiled unchanged. */
#define main full_r3_fixture_main
#include "../engine_fix_r2/containers/product/host_checks.c"
#undef main

static const char *evidence_dir;
static unsigned missing_minus1,mark_collisions,main_request_seen;

static void dump(const char *native_path,const char *name)
{
    char path[1024];File *f=file(native_path);FILE *out;
    if(!f)return;
    CHECK(snprintf(path,sizeof(path),"%s/%s",evidence_dir,name)>0);
    out=fopen(path,"wb");CHECK(out);
    CHECK(fwrite(f->bytes,1,f->length,out)==f->length);CHECK(!fclose(out));
}
static void check_file(const char *path,const uint8_t *raw,unsigned bytes)
{File *f=file(path);CHECK(f&&f->length==bytes&&!memcmp(f->bytes,raw,bytes));}
static void all_rows(const uint8_t *raw,const uint8_t *expected)
{
    unsigned slot;CHECK(root.state==RV_READY&&session()->rows==16);
    for(slot=1;slot<=16;++slot){select_slot(slot);matches_recipe(raw,slot,expected);}
}
static void cold(const uint8_t *raw,const uint8_t *expected)
{
    unsigned w=writes,r=renames;
    CHECK(!file("/ATA1/GXRCE.DAT"));reboot();
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&root.state==RV_READY);
    CHECK(session()->generation==be32(raw+28));
    CHECK(session()->selected_source==RV_SOURCE_A||session()->selected_source==RV_SOURCE_B);
    menu();all_rows(raw,expected);CHECK(writes==w&&renames==r);
    printf("COLD_PASS generation=%u source=%u rows=16 no_writes=1\n",session()->generation,session()->selected_source);
}
static void first(const uint8_t *raw,unsigned bytes,const uint8_t *expected)
{
    unsigned i,w;
    CHECK(!file("/IROM/GXRCE0.DAT")&&!file("/IROM/GXRCE1.DAT"));
    CHECK(rv_native_open("/IROM/absent",0)==-1);++missing_minus1;
    put_file("/ATA1/GXRCE.DAT",raw,bytes);
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->selected_source==RV_SOURCE_CARD);
    CHECK(session()->generation==be32(raw+28));
    w=7504+((bytes+be32(raw+116)+3)&~3u);
    for(i=0;i<block_count;++i)if(blocks[i].live&&blocks[i].length==w)break;
    CHECK(i<block_count);main_request_seen=w;
    menu();CHECK(root.state==RV_READY&&ig_host_install_status()==RV_OK);
    CHECK(!file("/ATA1/GXRCE.DAT"));check_file("/ATA1/GXRCE.OK",raw,bytes);
    check_file("/IROM/GXRCE0.DAT",raw,bytes);CHECK(!file("/IROM/GXRCE1.DAT"));
    all_rows(raw,expected);
    printf("FIRST_PASS generation=%u main_request=%u rows=16 missing_open=-1 DAT_to_OK=1\n",be32(raw+28),w);
}
static void update(int keep_ok,int refuse)
{
    uint32_t result;
    first(base_raw,base_bytes,golden);
    check_file("/ATA1/GXRCE.OK",base_raw,base_bytes);
    if(!keep_ok)CHECK(rv_native_delete("/ATA1/GXRCE.OK")==0);
    rename_refuse_existing=(unsigned)refuse;
    put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);reboot();
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->selected_source==RV_SOURCE_CARD);
    CHECK(session()->generation==106);
    result=invoke(session()->entries.menu_open,0,0);
    check_file("/IROM/GXRCE0.DAT",base_raw,base_bytes);
    check_file("/IROM/GXRCE1.DAT",new_raw,new_bytes);
    if(keep_ok&&refuse){
        ++mark_collisions;
        CHECK(result!=RV_CONSUMED&&ig_host_install_status()==RV_UNCERTAIN);
        CHECK(root.state==RV_DISABLED_UNTIL_REBOOT);
        check_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);
        check_file("/ATA1/GXRCE.OK",base_raw,base_bytes);
        puts("EXPECTED_OK_COLLISION old_OK=105 DAT=106 IROM_A=105 IROM_B=106 install=RV_UNCERTAIN disabled=1");
        /* Inspect the committed IROM independently of the failed acknowledgement. */
        CHECK(rv_native_delete("/ATA1/GXRCE.DAT")==0);
        cold(new_raw,new_golden);
    }else{
        CHECK(result==RV_CONSUMED&&root.state==RV_READY&&ig_host_install_status()==RV_OK);
        CHECK(!file("/ATA1/GXRCE.DAT"));check_file("/ATA1/GXRCE.OK",new_raw,new_bytes);
        all_rows(new_raw,new_golden);cold(new_raw,new_golden);
        printf("UPDATE_PASS old=105 new=106 old_OK=%d rename=%s DAT_to_OK=1\n",keep_ok,refuse?"reject-existing":"replace-existing");
    }
}
static void downgrade(void)
{
    unsigned w,r;
    update(0,1);
    put_file("/ATA1/GXRCE.DAT",base_raw,base_bytes);reboot();w=writes;r=renames;
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->generation==106);
    CHECK(session()->selected_source==RV_SOURCE_B);
    menu();all_rows(new_raw,new_golden);
    CHECK(writes==w&&renames==r);
    check_file("/IROM/GXRCE0.DAT",base_raw,base_bytes);
    check_file("/IROM/GXRCE1.DAT",new_raw,new_bytes);
    check_file("/ATA1/GXRCE.DAT",base_raw,base_bytes);
    check_file("/ATA1/GXRCE.OK",new_raw,new_bytes);
    puts("DOWNGRADE_PASS IROM=106 card_DAT=105 selected=106 no_writes=1 no_rename=1 DAT_retained=1");
}
static void tweak_name(char path[32],unsigned slot,unsigned copy)
{CHECK(snprintf(path,32,"/IROM/T%s%02u%c.BIN",unit==0?"50":unit==1?"28":"M0",slot-1,'A'+copy)>0);}
static void tweaks(unsigned slot,int saved)
{
    static const int8_t value[ENG_PARAMS]={3,2,-2,1,0,0,0,0};
    static const int8_t defaults[ENG_PARAMS]={0};
    EngRecipeRef ref;EngTweak t;
    root.inflight=1;CHECK(eng_current(&ref,&t)==ENG_OK);root.inflight=0;
    CHECK(ref.unit==unit&&ref.slot==slot);
    CHECK(!memcmp(t.v,saved?value:defaults,ENG_PARAMS));
}
static void saved_tweak(unsigned slot)
{
    char path[32];unsigned i;File *f;
    static const int32_t value[6]={3,2,-2,1,0,0};
    tweak_name(path,slot,0);f=file(path);CHECK(f&&f->length==GXTS_BYTES&&be32(f->bytes+12)==1);
    for(i=0;i<6;++i)CHECK((int32_t)be32(f->bytes+196+8*i)==value[i]);
}
static void save_panel(unsigned slot)
{
    static const unsigned row[4]={9,8,4,7};unsigned i;
    menu();select_slot(slot);panel_open();
    for(i=0;i<4;++i){
        if(i)panel_open();
        CHECK(ig_host_panel()->parameter==i&&ig_host_panel()->last_store==RV_OK);
        CHECK(strcmp(ig_host_panel()->text[0],"SaveFail"));select_slot(row[i]);
    }
    close_key(1);CHECK(root.state==RV_READY&&ig_host_panel()->last_store==RV_OK);
    tweaks(slot,1);saved_tweak(slot);
}
static void gxts_update(void)
{
    static const unsigned slots[3]={1,2,5};
    uint8_t old[3][GXTS_BYTES];char path[32],name[80];
    unsigned i,n=unit==0?3u:1u,w,r,keep;
    CHECK(unit==0||unit==2);
    first(base_raw,base_bytes,golden);
    for(i=0;i<n;++i){
        save_panel(slots[i]);tweak_name(path,slots[i],0);
        memcpy(old[i],file(path)->bytes,GXTS_BYTES);
        CHECK(snprintf(name,sizeof(name),"slot-%02u-before.BIN",slots[i])>0);dump(path,name);
    }
    w=writes;r=renames;reboot();
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->generation==105);
    CHECK(session()->selected_source==RV_SOURCE_A);menu();
    CHECK(writes==w&&renames==r);
    for(i=0;i<n;++i){select_slot(slots[i]);tweaks(slots[i],1);}
    CHECK(rv_native_delete("/ATA1/GXRCE.OK")==0);
    put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);reboot();
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->generation==106);
    menu();CHECK(root.state==RV_READY&&ig_host_install_status()==RV_OK);
    CHECK(!file("/ATA1/GXRCE.DAT"));check_file("/ATA1/GXRCE.OK",new_raw,new_bytes);
    w=writes;r=renames;
    for(i=0;i<n;++i){
        keep=unit==0&&slots[i]==5;select_slot(slots[i]);tweaks(slots[i],(int)keep);panel_open();
        CHECK(root.state==RV_READY&&ig_host_panel()->last_store==RV_OK);
        CHECK(strcmp(ig_host_panel()->text[0],"SaveFail"));close_key(0);
        tweak_name(path,slots[i],0);check_file(path,old[i],GXTS_BYTES);
        printf("GXTS_PASS unit=%u slot=%u before=3,2,-2,1,0,0 after=%s SaveFail=0 disabled=0 old_file_retained=1\n",
               unit,slots[i],keep?"3,2,-2,1,0,0":"0,0,0,0,0,0");
    }
    CHECK(writes==w&&renames==r);
    /* The card has been acknowledged; reboot with the old GXTS files intact. */
    reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->generation==106);
    CHECK(session()->selected_source==RV_SOURCE_A||session()->selected_source==RV_SOURCE_B);menu();
    for(i=0;i<n;++i){
        keep=unit==0&&slots[i]==5;select_slot(slots[i]);tweaks(slots[i],(int)keep);
        tweak_name(path,slots[i],0);check_file(path,old[i],GXTS_BYTES);
        CHECK(snprintf(name,sizeof(name),"slot-%02u-after.BIN",slots[i])>0);dump(path,name);
    }
    CHECK(writes==w&&renames==r);puts("GXTS_COLD_PASS generation=106 values_rechecked=1 no_writes=1");
}
int main(int argc,char **argv)
{
    uint8_t rawtrust[232];unsigned i;
    if(argc!=9)return 2;
    scenario=argv[1];unit=(unsigned)strtoul(argv[2],0,10);CHECK(unit<3);evidence_dir=argv[8];
    base_bytes=load_file(argv[3],base_raw,sizeof(base_raw));new_bytes=load_file(argv[4],new_raw,sizeof(new_raw));
    CHECK(be32(base_raw+28)==105&&be32(new_raw+28)==106);
    CHECK(load_file(argv[5],rawtrust,sizeof(rawtrust))==232);
    CHECK(load_file(argv[6],golden,sizeof(golden))==sizeof(golden));
    CHECK(load_file(argv[7],new_golden,sizeof(new_golden))==sizeof(new_golden));
    memcpy(trust.body_sha256,rawtrust+8,32);memcpy(trust.resident_build_id,rawtrust+40,32);
    memcpy(trust.resident_abi_id,rawtrust+72,16);
    for(i=0;i<3;++i){
        memcpy(&trust.modules[i].unit,&units[i],sizeof(units[i]));
        trust.modules[i].stock_crc32=be32(rawtrust+100+48*i);
        memcpy(trust.modules[i].stock_sha256,rawtrust+104+48*i,32);
    }
    (void)es_aliases_unused;reboot();
    if(!strcmp(scenario,"r4-first-replace")||!strcmp(scenario,"r4-first-reject")){
        rename_refuse_existing=strstr(scenario,"reject")!=NULL;
        first(new_raw,new_bytes,new_golden);cold(new_raw,new_golden);
    }else if(!strcmp(scenario,"r4-update-ok-replace"))update(1,0);
    else if(!strcmp(scenario,"r4-update-ok-reject"))update(1,1);
    else if(!strcmp(scenario,"r4-update-clean-replace"))update(0,0);
    else if(!strcmp(scenario,"r4-update-clean-reject"))update(0,1);
    else if(!strcmp(scenario,"r4-downgrade"))downgrade();
    else if(!strcmp(scenario,"r4-gxts"))gxts_update();
    else CHECK(0);
    CHECK(opens==closes);for(i=0;i<2;++i)CHECK(!fds[i].live);
    dump("/IROM/GXRCE0.DAT","IROM-GXRCE0.DAT");dump("/IROM/GXRCE1.DAT","IROM-GXRCE1.DAT");
    dump("/ATA1/GXRCE.DAT","card-GXRCE.DAT");dump("/ATA1/GXRCE.OK","card-GXRCE.OK");
    CHECK(missing_minus1>0);
    printf("OK scenario=%s unit=%u assertions=%u opens=%u writes=%u renames=%u missing_open=-1 mark_collisions=%u main_request=%u\n",
           scenario,unit,assertions,opens,writes,renames,mark_collisions,main_request_seen);
    return 0;
}
