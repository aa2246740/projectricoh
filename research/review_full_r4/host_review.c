/* Original native-boundary double; product, services and resident are unchanged. */
#define main original_fixture_main
#define rv_native_create original_create
#define rv_native_write original_write
#define rv_native_delete original_delete
#define rv_native_rename original_rename
#include "../../firmware/engine_fix_r2/containers/product/host_checks.c"
#undef main
#undef rv_native_create
#undef rv_native_write
#undef rv_native_delete
#undef rv_native_rename

static unsigned creates,deletes,write_calls,rename_calls;
static const char *outdir;
static File before_files[64];
int32_t rv_native_create(const char *path,uint32_t mode)
{++creates;printf("CREATE %s\n",path);return original_create(path,mode);}
int32_t rv_native_write(int32_t fd,const void *p,uint32_t n)
{++write_calls;return original_write(fd,p,n);}
int32_t rv_native_delete(const char *path)
{int32_t rc; ++deletes;rc=original_delete(path);printf("DELETE %s rc=%d\n",path,rc);return rc;}
int32_t rv_native_rename(const char *from,const char *to)
{int exists=file(to)!=NULL;int32_t rc;++rename_calls;rc=original_rename(from,to);
 printf("RENAME %s %s target_existed=%d rc=%d\n",from,to,exists,rc);return rc;}

static void exact(const char *path,const uint8_t *raw,unsigned n)
{File *f=file(path);CHECK(f&&f->length==n&&!memcmp(f->bytes,raw,n));}
static void dump_file(const char *path,const char *name)
{char target[1024];FILE *f;File *x=file(path);if(!x)return;
 CHECK(snprintf(target,sizeof(target),"%s/%s",outdir,name)>0);f=fopen(target,"wb");CHECK(f);
 CHECK(fwrite(x->bytes,1,x->length,f)==x->length);CHECK(!fclose(f));}
static void review_tweak_path(char p[32],unsigned slot,unsigned copy)
{CHECK(snprintf(p,32,"/IROM/T%s%02u%c.BIN",unit==0?"50":unit==1?"28":"M0",slot-1,'A'+copy)>0);}
static unsigned mutation_count(void){return creates+deletes+write_calls+rename_calls;}
static void all_rows(const uint8_t *raw,const uint8_t *expected)
{unsigned i;const EngList *list=eng_list();CHECK(root.state==RV_READY&&session()->rows==16&&list->opened);
 for(i=1;i<=16;i++){unsigned bank=be32(raw+be32(raw+156)+64*unit+16);const uint8_t *r=raw+bank+32+64*(i-1);
  if(r[1]){char label[33];memcpy(label,r+4,r[2]);label[r[2]]=0;CHECK(!strcmp(list->row[i-1].ascii,label));}
  select_slot(i);matches_recipe(raw,i,expected);}}
static void cold(unsigned generation)
{unsigned start=mutation_count();CHECK(!file("/ATA1/GXRCE.DAT"));reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);
 CHECK(session()->generation==generation);menu();CHECK(root.state==RV_READY&&mutation_count()==start);
 printf("COLD generation=%u source=%u ready=1 no_mutations=1\n",generation,session()->selected_source);}
static void install_old(void)
{put_file("/ATA1/GXRCE.DAT",base_raw,base_bytes);CHECK(rv_load(&root,&rv_trust)==RV_OK);menu();
 CHECK(root.state==RV_READY&&ig_host_install_status()==RV_OK);exact("/IROM/GXRCE0.DAT",base_raw,base_bytes);}
static void swap_new(int keep_ok)
{File *f;if(!keep_ok&&(f=file("/ATA1/GXRCE.OK")))f->exists=0;
 if((f=file("/ATA1/GXRCE.DAT")))f->exists=0;put_file("/ATA1/GXRCE.DAT",new_raw,new_bytes);reboot();
 CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->generation==106&&session()->selected_source==RV_SOURCE_CARD);}
static void current_cont(unsigned slot,int value)
{EngRecipeRef ref;EngTweak t;root.inflight=1;CHECK(eng_current(&ref,&t)==ENG_OK);root.inflight=0;
 CHECK(ref.unit==unit&&ref.slot==slot&&t.v[0]==value);}
static void save_attempt(unsigned slot,int value)
{uint32_t frame[32]={0};uint8_t preview_rows[408],committed_rows[408];unsigned row,pos=0,map,changes=0;
 menu();select_slot(slot);panel_open();
 map=be32(new_raw+be32(new_raw+156)+64*unit+12);
 for(row=0;row<7;row++){const uint8_t *d=new_raw+map+32+12*row;unsigned n=be16(d+4);memcpy(committed_rows+pos,RV_PTR(be32(d)),n);pos+=n;}
 CHECK(pos==sizeof(committed_rows));pos=0;select_slot((unsigned)(value+6));
 for(row=0;row<7;row++){const uint8_t *d=new_raw+map+32+12*row;unsigned n=be16(d+4);memcpy(preview_rows+pos,RV_PTR(be32(d)),n);pos+=n;}
 CHECK(pos==sizeof(preview_rows));
 for(row=0;row<sizeof(preview_rows);row++)if(preview_rows[row]!=committed_rows[row])changes++;
 printf("PREVIEW row_byte_changes=%u\n",changes);
 frame[11]=0;frame[7]=0x23;frame[16]=0x202c2d84;rv_hook_observe(&root,7,frame);
 printf("SAVE slot=%u value=%d status=%d state=%u flags=%u panel_open=%u\n",slot,value,
        ig_host_panel()->last_store,root.state,root.flags,ig_host_panel()->open);
 if(root.state==RV_DISABLED_UNTIL_REBOOT){pos=0;for(row=0;row<7;row++){const uint8_t *d=new_raw+map+32+12*row;unsigned n=be16(d+4);
  CHECK(!memcmp(preview_rows+pos,RV_PTR(be32(d)),n));pos+=n;}
  CHECK(changes>0);printf("DISABLED unsaved_preview_rows_retained=408 native_list_restored=%u native_rows=%u\n",RV_WORD(0x2022f5a8)==0x2022d610,RV_BYTE(0x2022f5ac));}}
static void require_saved(unsigned slot,int value)
{save_attempt(slot,value);CHECK(root.state==RV_READY&&ig_host_panel()->last_store==RV_OK&&!ig_host_panel()->open);
 current_cont(slot,value);}
static unsigned newest_generation(const uint8_t *raw,unsigned n,unsigned slot)
{Gxr2View v;GxtsBinding b;GxtsState s;char p[32];unsigned c,gen=0;
 CHECK(gxr2_validate(raw,n,&trust,&units[unit],0,&v)==GXR2_OK);CHECK(gxts_bind(&v,unit,slot,&b)==GXTS_OK);
 for(c=0;c<2;c++){File *f;review_tweak_path(p,slot,c);f=file(p);if(f&&gxts_decode(f->bytes,f->length,&b,&s)==GXTS_OK&&s.generation>gen)gen=s.generation;}
 return gen;}
static void card_cases(void)
{int keep=!strcmp(scenario,"old-ok");unsigned i;File *f;
 if(!strcmp(scenario,"installed")||keep)install_old();
 if(!strcmp(scenario,"never-run"))put_file("/ATA1/GXRCE.DAT",base_raw,base_bytes);
 if(!strcmp(scenario,"partial-a")||!strcmp(scenario,"partial-both"))put_file("/IROM/GXRCE0.DAT",base_raw,1024);
 if(!strcmp(scenario,"partial-b")||!strcmp(scenario,"partial-both"))put_file("/IROM/GXRCE1.DAT",base_raw,1024);
 if(strstr(scenario,"partial"))put_file("/IROM/GXRCE.TMP",base_raw,2048);
 swap_new(keep);i=invoke(session()->entries.menu_open,0,0);
 printf("INSTALL result=%u status=%d ready=%u DAT=%u OK=%u validA=%d validB=%d\n",i,ig_host_install_status(),root.state==RV_READY,
        file("/ATA1/GXRCE.DAT")!=NULL,file("/ATA1/GXRCE.OK")!=NULL,valid_irom(0),valid_irom(1));
 if(keep){CHECK(root.state==RV_DISABLED_UNTIL_REBOOT&&ig_host_install_status()==RV_UNCERTAIN);
  exact("/ATA1/GXRCE.OK",base_raw,base_bytes);exact("/IROM/GXRCE1.DAT",new_raw,new_bytes);return;}
 if(!strcmp(scenario,"partial-both")){CHECK(root.state==RV_READY&&ig_host_install_status()==RV_VERIFY);
  CHECK(!valid_irom(0)&&!valid_irom(1)&&file("/ATA1/GXRCE.DAT"));
  file("/ATA1/GXRCE.DAT")->exists=0;reboot();CHECK(rv_load(&root,&rv_trust)!=RV_OK&&root.state==RV_DISABLED_UNTIL_REBOOT);
  puts("COUNTEREXAMPLE two_partial_copies update_not_persistent DAT_removed_disables=1");return;}
 CHECK(root.state==RV_READY&&ig_host_install_status()==RV_OK&&!file("/ATA1/GXRCE.DAT"));
 exact("/ATA1/GXRCE.OK",new_raw,new_bytes);CHECK(valid_irom(0)||valid_irom(1));all_rows(new_raw,new_golden);
 for(i=0;i<64;i++)if(files[i].exists&&!strcmp(files[i].path,"/IROM/GXRCE.TMP"))CHECK(0);
 cold(106);f=file("/ATA1/GXRCE.OK");if(f)f->exists=0;cold(106);}
static void older_card(void)
{unsigned start;int layout_b=strstr(scenario,"ab")!=NULL;int keep_ok=strstr(scenario,"ok")!=NULL;
 if(layout_b){put_file("/IROM/GXRCE0.DAT",base_raw,base_bytes);put_file("/IROM/GXRCE1.DAT",new_raw,new_bytes);}
 else put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);
 if(keep_ok)put_file("/ATA1/GXRCE.OK",new_raw,new_bytes);put_file("/ATA1/GXRCE.DAT",base_raw,base_bytes);
 memcpy(before_files,files,sizeof(files));start=mutation_count();CHECK(rv_load(&root,&rv_trust)==RV_OK);
 CHECK(session()->generation==105&&session()->selected_source==RV_SOURCE_CARD);menu();all_rows(base_raw,golden);
 CHECK(root.state==RV_READY&&ig_host_install_status()==RV_CONFLICT&&mutation_count()==start&&!memcmp(before_files,files,sizeof(files)));
 puts("OLDER_CARD generation=105 install=CONFLICT no_mutations=1 ready=1");file("/ATA1/GXRCE.DAT")->exists=0;
 cold(106);CHECK(session()->selected_source==(layout_b?RV_SOURCE_B:RV_SOURCE_A));}
static void repeat_saves(void)
{unsigned i;int use_old=!strcmp(scenario,"repeat-old");const uint8_t *raw=use_old?base_raw:new_raw;
 unsigned n=use_old?base_bytes:new_bytes;static const int values[8]={1,2,3,2,1,0,-1,-2};
 put_file("/IROM/GXRCE0.DAT",raw,n);CHECK(rv_load(&root,&rv_trust)==RV_OK);menu();
 for(i=0;i<8;i++){require_saved(1,values[i]);CHECK(newest_generation(raw,n,1)==i+1);}
 cold(use_old?105:106);select_slot(1);current_cont(1,-2);
 puts("REPEAT eight_saves=PASS both_copies_exist=1 rejecting_rename=1");}
static void changed_binding(void)
{unsigned slot=!strcmp(scenario,"binding-keep")?5:strstr(scenario,"slot2")?2:1;int both=strstr(scenario,"both")!=NULL;
 int replace=strstr(scenario,"replace")!=NULL;char path[32];unsigned gen;
 CHECK(unit!=1||slot==5);install_old();require_saved(slot,1);if(both)require_saved(slot,2);
 gen=newest_generation(base_raw,base_bytes,slot);CHECK(gen==(both?2u:1u));
 review_tweak_path(path,slot,0);dump_file(path,"old-A.BIN");review_tweak_path(path,slot,1);dump_file(path,"old-B.BIN");
 swap_new(0);menu();CHECK(root.state==RV_READY&&ig_host_install_status()==RV_OK);
 select_slot(slot);current_cont(slot,slot==5?(both?2:1):0);panel_open();
 CHECK(ig_host_panel()->last_store==RV_OK&&strcmp(ig_host_panel()->text[0],"SaveFail"));close_key(0);
 cold(106);select_slot(slot);current_cont(slot,slot==5?(both?2:1):0);
 rename_refuse_existing=replace?0u:1u;save_attempt(slot,3);
 if(slot!=5&&!replace){CHECK(root.state==RV_DISABLED_UNTIL_REBOOT&&ig_host_panel()->last_store==RV_UNCERTAIN);
  CHECK(newest_generation(base_raw,base_bytes,slot)==gen);puts("COUNTEREXAMPLE changed_binding first_save_rejected disables=1 old_GXTS_retained=1");
  cold(106);select_slot(slot);current_cont(slot,0);save_attempt(slot,3);
  CHECK(root.state==RV_DISABLED_UNTIL_REBOOT&&ig_host_panel()->last_store==RV_UNCERTAIN);
  CHECK(newest_generation(base_raw,base_bytes,slot)==gen);puts("COUNTEREXAMPLE reboot_does_not_repair_save_path=1");}
 else {CHECK(root.state==RV_READY&&ig_host_panel()->last_store==RV_OK);current_cont(slot,3);
  CHECK(newest_generation(new_raw,new_bytes,slot)==(slot==5?gen+1:1));puts("CONTROL save_after_update=PASS");}
 review_tweak_path(path,slot,0);dump_file(path,"after-A.BIN");review_tweak_path(path,slot,1);dump_file(path,"after-B.BIN");}
static void all_tweaks(void)
{Gxr2View view;GxtsBinding b;GxtsState state;uint8_t raw[GXTS_BYTES];char path[32];unsigned s,c,start;
 CHECK(gxr2_validate(base_raw,base_bytes,&trust,&units[unit],0,&view)==GXR2_OK);install_old();
 for(s=1;s<=16;s++){
  CHECK(gxts_bind(&view,unit,s,&b)==GXTS_OK);
  for(c=0;c<2;c++){unsigned i;for(i=0;i<6;i++)state.values[i]=b.def[i];state.values[0]=(int)c+1;
   state.generation=7+c;CHECK(gxts_encode(&b,&state,raw)==GXTS_OK);review_tweak_path(path,s,c);put_file(path,raw,GXTS_BYTES);}}
 reboot();CHECK(rv_load(&root,&rv_trust)==RV_OK);menu();for(s=1;s<=16;s++){select_slot(s);current_cont(s,2);}
 swap_new(0);menu();CHECK(root.state==RV_READY&&ig_host_install_status()==RV_OK);
 memcpy(before_files,files,sizeof(files));start=mutation_count();
 for(c=0;c<2;c++){
  if(c)cold(106);
  for(s=1;s<=16;s++){int changed=(unit==0&&(s==1||s==2))||(unit==2&&s==1);
   select_slot(s);current_cont(s,changed?0:2);panel_open();CHECK(ig_host_panel()->last_store==RV_OK&&strcmp(ig_host_panel()->text[0],"SaveFail"));close_key(0);menu();
   printf("ALL_TWEAKS cold=%u slot=%u old=2 new=%d\n",c,s,changed?0:2);}}
 CHECK(mutation_count()==start&&!memcmp(before_files,files,sizeof(files)));puts("ALL_TWEAKS no_files_changed=1 all16_checked_twice=1");}
static void accepted_f02(void)
{put_file("/IROM/GXRCE0.DAT",new_raw,new_bytes);put_file("/ATA1/GXRCE.DAT",base_raw,base_bytes);
 CHECK(rv_load(&root,&rv_trust)==RV_OK&&session()->generation==105);
 hidden_path[0]="/IROM/GXRCE0.DAT";hidden_left[0]=3;rename_refuse_existing=0;menu();
 CHECK(hidden_hits==3&&root.state==RV_READY&&ig_host_install_status()==RV_OK);
 exact("/IROM/GXRCE0.DAT",base_raw,base_bytes);CHECK(!file("/ATA1/GXRCE.DAT"));
 puts("ACCEPTED_F02 visible_CARD_105_overwrites_hidden_IROM_106=1 not_a_new_finding=1");}
int main(int argc,char **argv)
{uint8_t wire[232];unsigned i;CHECK(argc==9);scenario=argv[1];unit=(unsigned)strtoul(argv[2],0,10);outdir=argv[8];CHECK(unit<3);
 base_bytes=load_file(argv[3],base_raw,sizeof(base_raw));new_bytes=load_file(argv[4],new_raw,sizeof(new_raw));
 CHECK(load_file(argv[5],wire,sizeof(wire))==232);CHECK(load_file(argv[6],golden,sizeof(golden))==sizeof(golden));
 CHECK(load_file(argv[7],new_golden,sizeof(new_golden))==sizeof(new_golden));
 memcpy(trust.body_sha256,wire+8,32);memcpy(trust.resident_build_id,wire+40,32);memcpy(trust.resident_abi_id,wire+72,16);
 for(i=0;i<3;i++){trust.modules[i].unit=units[i];trust.modules[i].stock_crc32=be32(wire+100+48*i);memcpy(trust.modules[i].stock_sha256,wire+104+48*i,32);}
 (void)es_aliases_unused;rename_refuse_existing=1;reboot();
 if(!strcmp(scenario,"accepted-f02"))accepted_f02();else if(!strcmp(scenario,"all-tweaks"))all_tweaks();else if(!strncmp(scenario,"repeat-",7))repeat_saves();else if(!strncmp(scenario,"binding-",8))changed_binding();
 else if(!strncmp(scenario,"older-",6))older_card();else card_cases();
 CHECK(opens==closes);for(i=0;i<2;i++)CHECK(!fds[i].live);
 dump_file("/IROM/GXRCE0.DAT","IROM-A.DAT");dump_file("/IROM/GXRCE1.DAT","IROM-B.DAT");
 dump_file("/ATA1/GXRCE.DAT","card.DAT");dump_file("/ATA1/GXRCE.OK","card.OK");
 printf("OK scenario=%s unit=%u assertions=%u creates=%u writes=%u deletes=%u renames=%u state=%u\n",scenario,unit,assertions,creates,write_calls,deletes,rename_calls,root.state);return 0;}
