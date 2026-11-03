#include "local/additional_support.c"

static void partial_install(void)
{
    put_file("/IROM/GXRCE0.DAT",base_raw,1024);put_file("/IROM/GXRCE1.DAT",base_raw,1024);
    put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);load108();
    CHECK(ig_host_install_status()==RV_OK&&!file("/ATA1/GXRCE.DAT")&&file("/ATA1/GXRCE.OK"));
    CHECK(valid_irom(0)&&!valid_irom(1));
    CHECK(!memcmp(file("/IROM/GXRCE0.DAT")->bytes,new_raw,new_bytes));
    CHECK(file("/IROM/GXRCE1.DAT")->length==1024&&!memcmp(file("/IROM/GXRCE1.DAT")->bytes,base_raw,1024));
    cold108();CHECK(session()->selected_source==RV_SOURCE_A);
    if(unit==1){CHECK(RV_BYTE(0x2022f5ac)==7);matches_stock();}
    else CHECK(session()->rows==8&&session()->cursor==0);
    puts("R4_02_PASS readable_invalid_AB_repaired cold108=1");
}
static void direct_repeat(void)
{
    static const int expected[8]={1,2,3,2,1,0,-1,-2};
    PnPort port;PnGxts *tweak;EngTweak values;unsigned i;
    installed();root.inflight=1;tweak=direct_store(1,&port);CHECK(pn_gxts_load(tweak,&values)==RV_OK);
    tracing=1;
    for(i=0;i<8;++i) {
        values.v[0]=(int8_t)expected[i];CHECK(pn_gxts_save(tweak,&tweak->recipe,&values)==RV_OK);
        CHECK(tweak->selection.state.generation==i+1);
        CHECK(pn_gxts_load(tweak,&values)==RV_OK&&values.v[0]==expected[i]);
    }
    tracing=0;root.inflight=0;cold108();root.inflight=1;tweak=direct_store(1,&port);
    CHECK(pn_gxts_load(tweak,&values)==RV_OK&&values.v[0]==-2&&tweak->selection.state.generation==8);root.inflight=0;
    puts("EIGHT_SAVES_PASS values_and_generations=1 cold_reload=-2 rename_existing=0");
}
static void preference_pair(int both)
{
    char a[32],b[32];File *f;installed();select_slot(1);select_slot(5);
    path_for(a,1,0,0);path_for(b,1,0,1);f=file(b);CHECK(f&&file(a));f->bytes[12]^=1;
    if(both)file(a)->bytes[12]^=1;
    memcpy(durable_before,files,sizeof(files));cold108();no_files_changed();
    if(both)CHECK(!has_current()&&session()->cursor==0);
    else {current_slot(1,0);CHECK(session()->cursor==0);}
    select_slot(5);CHECK(ig_host_last_store()==RV_OK);cold108();current_slot(5,0);CHECK(session()->cursor==4);
}
int main(int argc,char **argv)
{
    uint8_t wire[232];unsigned i;
    CHECK(argc==9);scenario=argv[1];unit=(unsigned)strtoul(argv[2],0,10);CHECK(unit<3);
    base_bytes=load_file(argv[3],base_raw,sizeof(base_raw));new_bytes=load_file(argv[4],new_raw,sizeof(new_raw));
    CHECK(load_file(argv[5],wire,sizeof(wire))==232&&load_file(argv[6],golden,sizeof(golden))==sizeof(golden));
    CHECK(load_file(argv[7],new_golden,sizeof(new_golden))==sizeof(new_golden));
    memcpy(trust.body_sha256,wire+8,32);memcpy(trust.resident_build_id,wire+40,32);memcpy(trust.resident_abi_id,wire+72,16);
    for(i=0;i<3;++i){trust.modules[i].unit=units[i];trust.modules[i].stock_crc32=be32(wire+100+48*i);memcpy(trust.modules[i].stock_sha256,wire+104+48*i,32);}
    rename_refuse_existing=(unsigned)strtoul(argv[8],0,10);reboot();
    if(!strcmp(scenario,"partial-both"))partial_install();
    else if(!strcmp(scenario,"direct-repeat"))direct_repeat();
    else if(!strcmp(scenario,"last-pair-one"))preference_pair(0);
    else if(!strcmp(scenario,"last-pair-both"))preference_pair(1);
    else CHECK(0);
    CHECK(opens==closes);for(i=0;i<2;++i)CHECK(!fds[i].live);
    printf("OK scenario=%s unit=%u assertions=%u rename=%s real_missing=-1\n",scenario,unit,assertions,rename_refuse_existing?"reject":"replace");return 0;
}
