/* First-build projection uses the official native enum and literal stores.
 * This does not execute M32R or the complete native rendering implementation. */
#include "local/review_support.c"
#include "local/native_enum.h"

static int boundary(unsigned remembered)
{
    uint32_t first[32]={0},second[32]={0},draw[32]={0};
    uint32_t serial,expected,mode,native,shadow;
    put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);
    if(remembered) {load108();save_cont(remembered,remembered==3?2:0);}
    reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);
    /* The test does not call menu() or install tag 33 before H01. */
    RV_BYTE(RV_NATIVE_VIEWS)=32;RV_BYTE(0x205a27d4)=1;
    first[15]=99;rv_hook_observe(&root,1,first);
    CHECK(root.state==RV_READY&&!first[1]&&first[15]==99);
    expected=remembered?remembered:1;
    CHECK(eng_list()->cursor==expected&&session()->cursor+1==expected);
    if(remembered)current_slot(remembered,remembered==3?2:0);
    else CHECK(!has_current());
    shadow=root.ui_block;
    CHECK(RV_BYTE(shadow+9)==expected&&RV_BYTE(shadow+10)==expected);
    CHECK(RV_BYTE(0x2022f725)==expected&&RV_BYTE(0x2022f726)==expected);
    mode=RV_BYTE(0x2050036e);CHECK(mode<11);
    second[7]=mode;rv_hook_observe(&root,2,second);
    CHECK(!second[1]&&second[7]==mode);
    /* 0x20287158/164, followed by the tag-33 push at 0x202871A4. */
    native=native_mode_rows[mode];
    RV_BYTE(0x2022f725)=RV_BYTE(0x2022f726)=native;
    RV_BYTE(RV_NATIVE_VIEWS+8)=33;RV_WORD(RV_NATIVE_VIEWS+12)=0x2022f71c;
    RV_BYTE(0x205a27d4)=2;
    serial=root.entry_serial;
    draw[13]=0xabcdef00;rv_hook_observe(&root,5,draw);
    CHECK(draw[1]==(uint32_t)(uintptr_t)rv_skip_05&&draw[13]==root.ui_restore[7]);
    CHECK(root.entry_serial==serial);
    CHECK(RV_BYTE(0x2022f725)==native&&RV_BYTE(0x2022f726)==native);
    CHECK(RV_BYTE(shadow+9)==expected&&RV_BYTE(shadow+10)==expected);
    printf("FIRST_BUILD parent_tag=32 count_before=1 count_after=2 remembered=%u S_mode=%u engine_cursor=%u native_cursor=%u snapshot_cursor=%u H05_engine_entries=0\n",
           remembered,mode,expected,native,RV_BYTE(shadow+10));
    if(native!=expected) {
        printf("FAIL_REQUIRED_CURSOR highlighted=%u required=%u after_native_stores_and_H05\n",native,expected);
        return 1;
    }
    puts("PASS_REQUIRED_CURSOR");return 0;
}

int main(int argc,char **argv)
{
    uint8_t wire[232];unsigned i,remembered,policy;int result;
    CHECK(argc==10);scenario=argv[1];unit=(unsigned)strtoul(argv[2],0,10);CHECK(unit==0||unit==2);
    base_bytes=load_file(argv[3],base_raw,sizeof(base_raw));new_bytes=load_file(argv[4],new_raw,sizeof(new_raw));
    CHECK(load_file(argv[5],wire,sizeof(wire))==232&&load_file(argv[6],golden,sizeof(golden))==sizeof(golden));
    CHECK(load_file(argv[7],new_golden,sizeof(new_golden))==sizeof(new_golden));
    memcpy(trust.body_sha256,wire+8,32);memcpy(trust.resident_build_id,wire+40,32);memcpy(trust.resident_abi_id,wire+72,16);
    for(i=0;i<3;++i){trust.modules[i].unit=units[i];trust.modules[i].stock_crc32=be32(wire+100+48*i);memcpy(trust.modules[i].stock_sha256,wire+104+48*i,32);}
    policy=(unsigned)strtoul(argv[8],0,10);rename_refuse_existing=policy;
    remembered=(unsigned)strtoul(argv[9],0,10);CHECK(remembered==0||remembered==1||remembered==3||remembered==5||remembered==8);
    reboot();result=boundary(remembered);
    CHECK(opens==closes);for(i=0;i<2;++i)CHECK(!fds[i].live);
    return result;
}
