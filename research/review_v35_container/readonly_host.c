#define main inherited_main
#include "isolated/candidate/host_v34c.c"
#undef main
int main(int argc,char **argv)
{
 uint8_t tr[232];unsigned i;CHECK(argc==7);scenario="readonly-review";unit=(unsigned)atoi(argv[1]);CHECK(unit<3);
 new_bytes=load_file(argv[2],new_raw,sizeof(new_raw));base_bytes=new_bytes;memcpy(base_raw,new_raw,new_bytes);
 CHECK(load_file(argv[3],tr,sizeof(tr))==232);CHECK(load_file(argv[4],new_golden,sizeof(new_golden))==sizeof(new_golden));memcpy(golden,new_golden,sizeof(golden));
 memcpy(trust.body_sha256,tr+8,32);memcpy(trust.resident_build_id,tr+40,32);memcpy(trust.resident_abi_id,tr+72,16);
 for(i=0;i<3;i++){trust.modules[i].unit=units[i];trust.modules[i].stock_crc32=be32(tr+100+48*i);memcpy(trust.modules[i].stock_sha256,tr+104+48*i,32);}
 clean();ready(1);CHECK(!(session()->capabilities&CAP_FILE_WRITE));menu();CHECK(session()->rows==8&&ig_host_install_status()==RV_UNSUPPORTED);
 apply_ok(1);matches_recipe(new_raw,1,new_golden);CHECK(!writes&&!renames&&!log_writes&&!internal_mutations);
 CHECK(file("/ATA1/GXRCE.DAT")&&!file("/ATA1/GXRCE.OK")&&!file("/IROM/GXRCE0.DAT")&&!file("/IROM/GXRCE1.DAT"));
 file("/ATA1/GXRCE.DAT")->exists=0;reboot();CHECK(rv_load(&root,&rv_trust)!=RV_OK&&root.state==RV_DISABLED_UNTIL_REBOOT);matches_stock();CHECK(opens==closes);
 printf("READONLY_FIX unit=%u rows=8 recipe_apply=PASS file_writes=0 rename=0 no_IROM_install=1 card_removed=native04\n",unit);return 0;
}
