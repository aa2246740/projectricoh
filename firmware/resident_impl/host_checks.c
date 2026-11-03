#include "resident.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint8_t memory[0x800000],fixture[RV_MAX_FILE+1],collision[RV_MAX_FILE+1],mutant[RV_MAX_FILE+1],large_code[RV_MAX_FILE+1],files[3][RV_MAX_FILE+1];
static const GxrceUnit units[3]={{"jlaunch",0x151,0},{"qlaunch",0x151,0},{"l08firm",0x151,0}};
static uint32_t large_length,alloc_failure;
static uint32_t file_length[3],file_enabled[3],file_opens[3],length;
static struct {unsigned live,source,position;} fds[2];
static struct {uint32_t base,epoch,live,length;} allocations[32];
static uint32_t heap_next,allocation_count,allocs,frees,stale_frees,opens,closes,active,max_active;
static uint32_t calls,init_calls,boot_calls,write_calls,rpc_w,ui_calls,cache_calls,checks;
static uint32_t fail_read,fail_close,overshoot,init_fail,bad_entries,reopen_mutation;
static uint32_t inject_kind,inject_n,inject_hook,kind_counts[8],first_ready,init_attempts,return_notify,engine_result,last_entry,engine_calls,free_reenter;
static RvRequest last_request;
static RvRoot root;
RvRoot *rv_host_root=&root;
const uint8_t rv_skip_01[4]={0},rv_skip_02[4]={0},rv_skip_05[4]={0},rv_skip_06[4]={0},rv_skip_07[4]={0},rv_skip_08[4]={0},rv_skip_10[4]={0};
const uint8_t rv_post_17[4]={0},rv_post_18[4]={0},rv_post_20[4]={0},rv_post_22[4]={0},rv_post_37[4]={0};
#define CHECK(x) do{++checks;if(!(x)){fprintf(stderr,"FAIL check=%u line=%d %s\n",checks,__LINE__,#x);exit(1);}}while(0)
void *rv_host_address(uint32_t a)
{
    uint32_t i;
    if(a<0x20000000u||a>=0x20800000u){fprintf(stderr,"invalid wire address %08x\n",a);exit(1);}
    if(a>=0x20704800u&&a<0x20744800u){
        for(i=0;i<allocation_count;++i)if(allocations[i].live&&allocations[i].epoch==root.epoch[RV_HEAP_E]&&a>=allocations[i].base&&a-allocations[i].base<allocations[i].length)break;
        if(i==allocation_count){fprintf(stderr,"stale/unowned heap read %08x\n",a);exit(1);}
    }
    return memory+(a-0x20000000u);
}
static void step(unsigned kind)
{
    ++calls;++kind_counts[kind];if(root.state==RV_READY&&!first_ready)first_ready=calls;
    if(inject_kind==kind&&kind_counts[kind]==inject_n){rv_notify(&root,inject_hook,0,0);inject_kind=0;}
}
uint32_t rv_irq_save(void){return 0;}
void rv_irq_restore(uint32_t n){(void)n;}
void rv_cache_sync(void){++cache_calls;step(6);}
uint32_t rv_native_alloc(uint32_t n)
{
    uint32_t a=heap_next;if(alloc_failure){step(1);return 0;}heap_next+=(n+3)&~3u;CHECK(heap_next<=0x20744800);CHECK(allocation_count<32);
    allocations[allocation_count].base=a;allocations[allocation_count].length=n;allocations[allocation_count].epoch=root.epoch[RV_HEAP_E];allocations[allocation_count++].live=1;++allocs;
    step(1);return a;
}
int32_t rv_native_free(uint32_t a)
{
    unsigned i;for(i=0;i<allocation_count&&allocations[i].base!=a;++i){}
    CHECK(i<allocation_count&&allocations[i].live);if(allocations[i].epoch!=root.epoch[RV_HEAP_E])++stale_frees;
    allocations[i].live=0;++frees;if(free_reenter)CHECK(rv_load(&root,&rv_trust,&units[0])==RV_BUSY);step(7);return 0;
}
int32_t rv_native_open(const char *p,uint32_t flags)
{
    static const char *names[3]={"/IROM/GXRCE0.DAT","/IROM/GXRCE1.DAT","/ATA1/GXRCE.DAT"};unsigned i,fd;
    CHECK(flags==0);step(2);
    for(i=0;i<3&&strcmp(p,names[i]);++i){}if(i==3||!file_enabled[i])return -1;
    for(fd=0;fd<2&&fds[fd].live;++fd){}if(fd==2)return -1;
    fds[fd].live=1;fds[fd].source=i;fds[fd].position=0;++opens;++file_opens[i];++active;if(active>max_active)max_active=active;
    if(reopen_mutation&&i==0&&file_opens[i]>1)files[0][320]^=1;
    return fd+17;
}
int32_t rv_native_read(int32_t fd,void *p,uint32_t n)
{
    unsigned i=fd-17,source,k;CHECK(i<2&&fds[i].live);source=fds[i].source;
    if(fail_read){step(3);return -1;}
    k=file_length[source]-fds[i].position;if(k>n)k=n;if(k>17)k=17;
    memcpy(p,files[source]+fds[i].position,k);fds[i].position+=k;step(3);
    return overshoot?(int32_t)n+1:(int32_t)k;
}
int32_t rv_native_close(int32_t fd)
{unsigned i=fd-17;CHECK(i<2&&fds[i].live);fds[i].live=0;--active;++closes;step(4);return fail_close?-1:0;}
int32_t rv_native_create(const char *p,uint32_t n){(void)p;(void)n;++write_calls;return -1;}
int32_t rv_native_write(int32_t f,const void *p,uint32_t n){(void)f;(void)p;(void)n;++write_calls;return -1;}
int32_t rv_native_delete(const char *p){(void)p;++write_calls;return -1;}
int32_t rv_native_rename(const char *p,const char *q){(void)p;(void)q;++write_calls;return -1;}
int32_t rv_native_context(void){return 0;}
uint32_t rv_native_unit(uint32_t n){CHECK(n==1);return 0x2040f818;}
int32_t rv_native_sd_id(void *p){uint32_t id[4]={1,2,3,4};memcpy(p,id,16);step(5);return 0;}
int32_t rv_native_rpc_ready(void){return 1;}
int32_t rv_native_rpc_limit(void){return 9;}
int32_t rv_rpc8_native(uint32_t letter,uint32_t value){if(letter==22)++rpc_w;return (int32_t)value;}
int32_t rv_native_preview(uint32_t a){CHECK(a==0);++ui_calls;return 0;}
int32_t rv_native_language(void){return 1;}
int32_t rv_native_ascii(const char *p,uint32_t n,void *out,uint32_t language)
{uint8_t *b=out;uint32_t i;(void)language;for(i=0;i<n;++i){b[2*i]=1;b[2*i+1]=p[i];}b[2*n]=b[2*n+1]=0;return 0;}
int32_t rv_native_layer(uint32_t a,uint32_t b,uint32_t c){(void)a;(void)b;(void)c;++ui_calls;return 0;}
int32_t rv_native_draw(uint32_t a,uint32_t b,uint32_t c){(void)a;(void)b;(void)c;++ui_calls;return 0;}
static void seal(uint8_t *p,uint32_t n)
{rv_put32(p+24,gxrce_crc32(p+256,n-256));rv_put32(p+20,0);rv_put32(p+20,gxrce_crc32(p,256));}
static uint32_t tag_word(uint8_t tag)
{union {uint32_t word;uint8_t bytes[4];} u={0};u.bytes[0]=tag;return u.word;}
static void buffer_header(void *p,uint32_t n)
{RvBufferHeader *h=p;memset(p,0,n);h->version=1;h->bytes=n;}
static RvRequest request(void)
{
    RvRequest q={1,64,0,{0}};
    q.args[0]=root.lease;q.args[1]=root.lease;q.args[2]=root.epoch[RV_BOOT_E];q.args[3]=root.epoch[RV_HEAP_E];
    q.args[4]=root.epoch[RV_LINK_E];q.args[5]=root.epoch[RV_UNIT_E];q.args[6]=root.epoch[RV_VIEW_E];q.args[7]=root.epoch[RV_S_E];return q;
}
static void forbidden_init_writes(void)
{
    RvRequest q=request();RvReply p;uint32_t scratch=root.image_address+34000;RvSettingsPlan *s=RV_PTR(scratch);
    buffer_header(s,80);s->count=1;s->writes[0].offset=0x36e;s->writes[0].value=4;
    q.args[10]=scratch;q.args[11]=80;CHECK(rv_service(&root,RV_SETTINGS,2,&q,&p)==RV_CAPABILITY);
    buffer_header(s,40);q.args[11]=40;CHECK(rv_service(&root,RV_UI_LIST,1,&q,&p)==RV_CAPABILITY);
    q=request();CHECK(rv_service(&root,RV_RPC8,1,&q,&p)==RV_OK);q.args[1]=p.token;q.args[8]=3;
    CHECK(rv_service(&root,RV_RPC8,3,&q,&p)==RV_CAPABILITY);q.args[8]=0;CHECK(rv_service(&root,RV_RPC8,5,&q,&p)==RV_OK);
    memset(&q,0,sizeof(q));q.version=1;q.bytes=64;q.args[0]=root.epoch[RV_IO_E];q.args[2]=1;q.args[5]=4;q.args[8]=100;
    CHECK(rv_service(&root,RV_STORAGE,3,&q,&p)==RV_CAPABILITY);
    ++init_attempts;
}
/* This is a host-only engine double. No directory/row-pool parser from
 * this function is linked into resident. The Python fixture independently
 * reconstructs and checks all three stock410 pins against zlib.crc32. */
static int engine_pin(void)
{
    static const uint8_t kinds[8]={0,1,2,3,0,1,1,1};
    static const uint16_t lengths[4]={62,33,96,56};
    const uint8_t *p=RV_PTR(root.image_address),*d,*e,*pool,*bucket;
    RvSession *s=rv_session(&root);RvRequest q=request();RvReply reply;
    uint32_t module,dir,dir_end,map,map_begin,map_end,tables,tables_end,table,crc,row,kind,off,count,n,total=128;
    for(module=0;module<3&&!rv_equal(&s->unit,&units[module],12);++module){}
    if(module==3)return 0;
    dir=rv_be32(p+156);dir_end=dir+rv_be32(p+160);
    if(dir_end-dir<64*(module+1))return 0;
    d=p+dir+64*module;
    if(!rv_equal(d,units[module].name,8)||rv_be16(d+8)!=0x151||rv_be16(d+10))return 0;
    map=rv_be32(d+12);map_begin=rv_be32(p+168);map_end=map_begin+rv_be32(p+172);
    if(map<map_begin||map>map_end||128>map_end-map)return 0;
    tables=rv_be32(p+192);tables_end=tables+rv_be32(p+196);
    if(tables_end-tables<64)return 0;pool=p+tables;
    if(!rv_equal(pool,"GXDP",4))return 0;
    table=rv_be32(d+20);if(table<tables||table>tables_end||32>tables_end-table)return 0;
    if(!rv_equal(p+table,"GXDT",4))return 0;e=p+table+16;
    if(e[0]!=4||e[1]||rv_be16(e+2)!=2)return 0;
    crc=rv_crc_update(~0u,p+map,128);
    for(row=0;row<8;++row){
        kind=kinds[row];bucket=pool+16+12*kind;count=rv_be16(bucket);n=rv_be16(bucket+2);off=rv_be32(bucket+4);
        if(n!=lengths[kind]||e[8+row]>=count||off>tables_end-tables||count*n>tables_end-tables-off)return 0;
        crc=rv_crc_update(crc,pool+off+e[8+row]*n,n);total+=n;
    }
    crc=~rv_crc_update(crc,e+2,2);total+=2;
    q.args[8]=module+1;
    CHECK(rv_service(&root,RV_QUERY,3,&q,&reply)==RV_OK&&reply.actual==4&&reply.token==0);
    return total==538&&crc==reply.detail;
}

int32_t rv_invoke(uint32_t address,const RvApi *api,uint32_t context,const RvRequest *q,RvReply *p)
{
    CHECK(api==&rv_api&&context==root.lease);CHECK(root.inflight==1);
    if(address!=root.image_address+256&&address!=root.image_address+260){
        CHECK(root.state==RV_READY);last_entry=address-root.image_address;last_request=*q;++engine_calls;
        p->version=1;p->bytes=32;return (int32_t)engine_result;
    }
    CHECK(root.state!=RV_READY);
    p->version=1;p->bytes=32;step(8-1); /* kind 7 also tests return-side lifecycle checks. */
    if(address==root.image_address+256) {
        RvEngineEntries *e=RV_PTR(q->args[10]);uint32_t *methods=&e->init;unsigned i;
        ++boot_calls;CHECK(root.state==RV_VALIDATED&&cache_calls==boot_calls);e->version=1;e->bytes=40;p->actual=40;
        for(i=0;i<9;++i)methods[i]=260+4*i;
        if(bad_entries==1)methods[5]=261;if(bad_entries==2)methods[7]=128;
        return RV_PASS;
    }
    CHECK(address==root.image_address+260);++init_calls;CHECK(root.state==RV_VALIDATED);
    {const RvInitWire *wire=RV_PTR(q->args[10]);CHECK(q->args[11]==36&&wire->header.version==1&&wire->header.bytes==36&&wire->image_address==root.image_address&&wire->image_bytes==root.image_bytes&&!wire->grain_address);}
    forbidden_init_writes();
    if(!engine_pin())return RV_FAULT;
    p->capabilities=CAP_UI|CAP_S|CAP_W;if(return_notify)rv_notify(&root,return_notify,0,0);
    return init_fail?RV_FAULT:RV_PASS;
}
static void setup(void)
{
    unsigned i;memset(memory,0,sizeof(memory));memset(fds,0,sizeof(fds));memset(file_opens,0,sizeof(file_opens));
    memset(allocations,0,sizeof(allocations));memset(kind_counts,0,sizeof(kind_counts));
    heap_next=0x20704800;allocation_count=allocs=frees=stale_frees=opens=closes=active=max_active=0;
    calls=init_calls=boot_calls=write_calls=rpc_w=ui_calls=cache_calls=0;first_ready=init_attempts=return_notify=engine_calls=last_entry=free_reenter=0;engine_result=RV_CONSUMED;
    alloc_failure=fail_read=fail_close=overshoot=init_fail=bad_entries=reopen_mutation=inject_kind=inject_n=inject_hook=0;
    rv_reset(&root);for(i=RV_HEAP_E;i<RV_EPOCH_COUNT;++i)root.epoch[i]=1;root.flags[F_RX]=2;root.flags[F_SD]=1;
    for(i=0;i<3;++i){file_enabled[i]=i==0;file_length[i]=length;memcpy(files[i],fixture,length);}
    RV_WORD(0x200d3488)=0x20704800;RV_WORD(0x200d348c)=0x20744800;RV_WORD(0x2040f804)=1;
    memcpy(RV_PTR(0x2040f81c),units[0].name,8);((uint8_t *)RV_PTR(0x2040f848))[0]=1;((uint8_t *)RV_PTR(0x2040f848))[1]=0x51;
    RV_WORD(0x2022f5a8)=0x2022d610;RV_BYTE(0x2022f5ac)=7;
    RV_WORD(0x200c0dac)=0x20600000;RV_WORD(0x200c0db0)=4096;RV_BYTE(0x2060036e)=4;
    RV_BYTE(0x206003aa)=1;RV_BYTE(0x20600c9d)=2;RV_BYTE(0x205d9a7f)=4;
    RV_WORD(0x205d9bf8)=8;RV_WORD(0x205d9c00)=56;RV_BYTE(0x2022f71c)=5;RV_BYTE(0x205a280f)=2;RV_BYTE(0x205a27d4)=1;RV_WORD(0x205a27d8)=0x205a3000;
    RV_WORD(0x205a3000)=tag_word(33);RV_WORD(0x205a3004)=0x2022f71c;
}
static int32_t load(void){return rv_load(&root,&rv_trust,&units[0]);}
static void check_no_publish(void)
{
    CHECK(root.state!=RV_READY&&root.image_address==0&&root.lease==0);CHECK(active==0&&opens==closes);
    CHECK(!first_ready&&!write_calls&&!rpc_w&&!ui_calls&&!stale_frees);
    CHECK(RV_WORD(0x2022f5a8)==0x2022d610&&RV_BYTE(0x2022f5ac)==7&&RV_WORD(0x205a3004)==0x2022f71c);
}
static void gate_checks(void)
{
    GxrceView v;uint32_t i,reloc=rv_be32(fixture+144),dir=rv_be32(fixture+156);
    for(i=0;i<256;++i)CHECK(rv_validate(fixture,i,&rv_trust,&v)==GXRCE_LENGTH);
    for(i=0;i<3;++i)CHECK(rv_validate(fixture,length,&rv_trust,&v)==GXRCE_OK);
    CHECK(rv_validate(collision,length,&rv_trust,&v)==GXRCE_OK);
    CHECK(gxrce_crc32(fixture,length)==gxrce_crc32(collision,length)&&memcmp(fixture,collision,length));
    CHECK(gxrce_crc32((const uint8_t *)"123456789",9)==0xcbf43926u);
#define MUTATE(statement,want) do{memcpy(mutant,fixture,length);statement;seal(mutant,length);CHECK(rv_validate(mutant,length,&rv_trust,&v)==(want));}while(0)
    MUTATE(mutant[48]^=1,GXRCE_BODY_ID);MUTATE(mutant[80]^=1,GXRCE_RESIDENT_ID);MUTATE(mutant[212]^=1,GXRCE_RESIDENT_ID);
    MUTATE(mutant[dir]^=1,GXRCE_OK);MUTATE(mutant[rv_be32(fixture+168)+44]^=1,GXRCE_OK);
    MUTATE(mutant[rv_be32(fixture+192)+16+82]^=1,GXRCE_OK);
    MUTATE(rv_put32(mutant+reloc,252),GXRCE_RELOCATION);
    MUTATE(rv_put32(mutant+reloc+4,length+64),GXRCE_RELOCATION);
    MUTATE(rv_put32(mutant+352,length+64);rv_put32(mutant+reloc+4,length+64),GXRCE_RELOCATION);
    MUTATE(rv_put32(mutant+112,257),GXRCE_LAYOUT);MUTATE(rv_put32(mutant+144,256),GXRCE_LAYOUT);
    memcpy(mutant,fixture,length);mutant[320]^=1;CHECK(rv_validate(mutant,length,&rv_trust,&v)==GXRCE_CRC);
    CHECK(rv_validate(fixture,length-1,&rv_trust,&v)==GXRCE_LENGTH);
#undef MUTATE
}
static void limit_checks(void)
{
    GxrceView v;RvReply reply;RvRequest q={1,64,0,{0}};uint32_t i;
    static const uint32_t expected[3]={0xdf2bcaf5,0x6700e6ff,0x1b3c7000};
    setup();
    for(i=0;i<3;++i){q.args[8]=i+1;CHECK(rv_service(&root,RV_QUERY,3,&q,&reply)==RV_OK&&reply.detail==expected[i]);}
    q.args[8]=0;CHECK(rv_service(&root,RV_QUERY,3,&q,&reply)==RV_ARGUMENT);
    q.args[8]=4;CHECK(rv_service(&root,RV_QUERY,3,&q,&reply)==RV_ARGUMENT);
    q.args[8]=1;q.args[9]=1;CHECK(rv_service(&root,RV_QUERY,3,&q,&reply)==RV_ARGUMENT);
    memcpy(mutant,fixture,length);mutant[34]=0x12;mutant[35]=0x34;seal(mutant,length);
    CHECK(rv_validate(mutant,length,&rv_trust,&v)==GXRCE_OK);
    memcpy(mutant,large_code,large_length);CHECK(rv_validate(mutant,large_length,&rv_trust,&v)==GXRCE_OK&&v.sections[0].length==24576);
    rv_put32(mutant+136,24580);rv_put32(mutant+148,0);mutant[120]=mutant[121]=0;seal(mutant,large_length);
    CHECK(rv_validate(mutant,large_length,&rv_trust,&v)==GXRCE_LAYOUT);
    setup();memset(files[0]+length,0,RV_MAX_FILE-length);file_length[0]=RV_MAX_FILE;
    rv_put32(files[0]+16,RV_MAX_FILE);rv_put32(files[0]+208,rv_be32(files[0]+208)+RV_MAX_FILE-length);rv_put32(files[0]+116,8192);seal(files[0],RV_MAX_FILE);
    CHECK(rv_validate(files[0],RV_MAX_FILE,&rv_trust,&v)==GXRCE_OK);
    CHECK(load()==RV_OK&&root.image_bytes==49152&&root.bss_bytes==8192);
    rv_put32(files[0]+116,8193);seal(files[0],RV_MAX_FILE);CHECK(rv_validate(files[0],RV_MAX_FILE,&rv_trust,&v)==GXRCE_LENGTH);
    setup();alloc_failure=1;CHECK(load()!=RV_OK);check_no_publish();CHECK(!opens&&!boot_calls&&!allocs);
}

static void loader_checks(void)
{
    unsigned i;uint32_t relocated,raw_target=rv_be32(fixture+352),image,before;
    setup();CHECK(load()==RV_OK);image=root.image_address;
    CHECK(root.state==RV_READY&&root.selected_source==RV_SOURCE_A&&boot_calls==1&&init_calls==1&&init_attempts==1);
    CHECK(allocs==1&&!frees&&max_active==1&&!active&&opens==closes&&!first_ready);
    relocated=rv_be32(RV_PTR(image+352));CHECK(relocated==image+raw_target);
    for(i=0;i<64;++i)CHECK(RV_BYTE(image+length+i)==0);
    setup();init_fail=1;free_reenter=1;CHECK(load()!=RV_OK);check_no_publish();CHECK(init_calls==1&&init_attempts==1&&frees==1);
    setup();return_notify=14;CHECK(load()!=RV_OK);check_no_publish();
    setup();bad_entries=1;CHECK(load()!=RV_OK);check_no_publish();CHECK(!init_calls);
    setup();bad_entries=2;CHECK(load()!=RV_OK);check_no_publish();CHECK(!init_calls);
    setup();fail_read=1;CHECK(load()!=RV_OK);check_no_publish();
    setup();fail_close=1;CHECK(load()!=RV_OK);check_no_publish();
    setup();overshoot=1;CHECK(load()!=RV_OK);check_no_publish();
    setup();file_length[0]=length-1;CHECK(load()!=RV_OK);check_no_publish();
    setup();memset(files[0]+length,0,RV_MAX_FILE+1-length);file_length[0]=RV_MAX_FILE+1;CHECK(load()!=RV_OK);check_no_publish();
    setup();reopen_mutation=1;CHECK(load()!=RV_OK);check_no_publish();
    for(i=0;i<6;++i) {
        static const unsigned kind[6]={1,2,3,4,5,6};
        setup();inject_kind=kind[i];inject_n=1;inject_hook=i==0?16:i==4?22:19;
        if(i==4){file_enabled[0]=0;file_enabled[2]=1;}
        CHECK(load()!=RV_OK);check_no_publish();
    }
    setup();CHECK(load()==RV_OK);image=root.image_address;before=opens;
    rv_notify(&root,19,0,1);CHECK(root.state==RV_FENCED&&root.image_address==image);CHECK(load()==RV_OK);
    CHECK(root.image_address==image&&opens==before&&allocs==1&&init_calls==2&&boot_calls==1);
    rv_notify(&root,20,0,0);CHECK(root.flags[F_RX]&1);rv_notify(&root,20,1,-5);CHECK(root.flags[F_RX]&1);
    rv_notify(&root,20,0,0);CHECK(root.flags[F_RX]==5);rv_notify(&root,20,1,0);CHECK(root.flags[F_RX]==6);
    CHECK(load()==RV_OK);image=root.image_address;
    rv_notify(&root,22,0,0);CHECK(root.image_address==image&&root.state==RV_READY&&!root.flags[F_SD]);
    rv_notify(&root,22,1,0);CHECK(root.flags[F_SD]==1);
    rv_notify(&root,16,0,0);CHECK(!rv_session(&root)&&!root.image_address&&!stale_frees);
    CHECK(load()==RV_OK&&root.image_address!=image&&allocs==2);
}
static void selection_checks(void)
{
    setup();file_enabled[0]=0;file_enabled[1]=1;CHECK(load()==RV_OK&&root.selected_source==RV_SOURCE_B);
    setup();file_enabled[1]=1;file_enabled[2]=1;rv_put32(files[1]+28,8);seal(files[1],length);rv_put32(files[2]+28,9);seal(files[2],length);
    CHECK(load()==RV_OK&&root.selected_source==RV_SOURCE_CARD);
    setup();file_enabled[2]=1;rv_put32(files[2]+28,0xffffffffu);seal(files[2],length);files[2][320]^=1;
    CHECK(load()==RV_OK&&root.selected_source==RV_SOURCE_A);
    setup();file_enabled[1]=1;files[1][320]^=1;seal(files[1],length);CHECK(load()==RV_CONFLICT);check_no_publish();
    setup();file_enabled[1]=1;memcpy(files[1],collision,length);CHECK(load()==RV_CONFLICT);check_no_publish();
    setup();file_enabled[1]=1;memcpy(files[1],collision,length);file_enabled[2]=1;rv_put32(files[2]+28,8);seal(files[2],length);
    CHECK(load()==RV_OK&&root.selected_source==RV_SOURCE_CARD);
    setup();file_enabled[2]=1;files[2][320]^=1;seal(files[2],length);
    CHECK(load()==RV_OK&&root.selected_source==RV_SOURCE_A&&root.fault==(uint32_t)RV_CONFLICT);
    setup();file_enabled[2]=1;memcpy(files[2],collision,length);
    CHECK(load()==RV_OK&&root.selected_source==RV_SOURCE_A&&root.fault==(uint32_t)RV_CONFLICT);
    setup();file_enabled[1]=1;CHECK(load()==RV_OK&&root.selected_source==RV_SOURCE_A);
}
static void abort_checks(void)
{
    uint32_t owned_state=0x20710000,owned_labels=0x20710100;
    setup();root.ui_restore[0]=0x205a3000;root.ui_restore[1]=1;root.ui_restore[2]=tag_word(33);root.ui_restore[3]=0x2022f71c;
    root.ui_restore[4]=owned_state;root.ui_restore[6]=owned_labels;RV_WORD(0x205a3004)=owned_state;
    RV_WORD(0x2022f5a8)=owned_labels;RV_BYTE(0x2022f5ac)=16;RV_BYTE(0x2022f726)=15;
    root.reserved[0]=0x20704800;root.reserved[1]=~root.reserved[0];root.flags[F_HEAP]=0;
    rv_ui_abort(&root);CHECK(RV_WORD(0x205a3004)==0x2022f71c&&RV_WORD(0x205a3000)==tag_word(33));
    CHECK(RV_WORD(0x2022f5a8)==0x2022d610&&RV_BYTE(0x2022f5ac)==7&&RV_BYTE(0x2022f726)==0);
    CHECK(root.ui_restore[0]==0&&root.ui_restore[6]==0&&!ui_calls);
    rv_ui_abort(&root);CHECK(RV_WORD(0x205a3004)==0x2022f71c);
    root.ui_restore[0]=0x205a3000;root.ui_restore[1]=1;root.ui_restore[2]=tag_word(33);root.ui_restore[3]=0x2022f71c;root.ui_restore[4]=owned_state;
    RV_WORD(0x205a3004)=owned_state;RV_WORD(0x205a3000)=tag_word(34);
    rv_ui_abort(&root);CHECK(RV_WORD(0x205a3004)==owned_state&&RV_WORD(0x205a3000)==tag_word(34));
}
static void grain_checks(void)
{
    uint8_t packet[144],expected[144];unsigned i,k,level,category;uint32_t before;
    static const unsigned offsets[5]={0x1a,0x14,0x75,0x1e,0x26};
    setup();root.state=RV_READY;rv_grain_commit(&root,4,1);before=calls;
    for(category=0;category<6;++category)for(i=0;i<20;++i)for(level=0;level<5;++level) {
        memset(packet,0xa5,sizeof(packet));for(k=0;k<5;++k)packet[offsets[k]]=0;
        memcpy(expected,packet,144);RV_BYTE(0x205d9a7f)=category;RV_BYTE(0x206003aa)=i;RV_BYTE(0x20600c9d)=level;
        if((category==0||category==4)&&i<=16&&((0x11126u>>i)&1)){expected[0x1a]=21;expected[0x10]=0;expected[0x32]=1;expected[0x6f]=level>=1&&level<=3?level:1;}
        rv_grain(&root,packet);CHECK(memcmp(packet,expected,144)==0);
    }
    RV_BYTE(0x205d9a7f)=4;RV_BYTE(0x206003aa)=1;
    for(k=0;k<5;++k){memset(packet,0,sizeof(packet));packet[offsets[k]]=1;memcpy(expected,packet,144);rv_grain(&root,packet);CHECK(!memcmp(packet,expected,144));}
    memset(packet,0,144);memcpy(expected,packet,144);RV_WORD(0x200c0db0)=0xc9d;rv_grain(&root,packet);CHECK(!memcmp(packet,expected,144));RV_WORD(0x200c0db0)=4096;
    RV_BYTE(0x2060036e)=3;rv_grain(&root,packet);CHECK(!memcmp(packet,expected,144));RV_BYTE(0x2060036e)=4;
    root.flags[F_UNCERTAIN]=1;rv_grain(&root,packet);CHECK(!memcmp(packet,expected,144));
    root.flags[F_UNCERTAIN]=0;rv_notify(&root,19,0,1);CHECK(!root.flags[F_GRAIN]);rv_grain(&root,packet);CHECK(!memcmp(packet,expected,144));
    CHECK(calls==before&&!rpc_w&&!opens);
}
static void service_checks(void)
{
    RvRequest q;RvReply p;RvEventSnapshot *events;uint32_t scratch;unsigned i;
    setup();CHECK(load()==RV_OK);root.inflight=1;q=request();scratch=root.image_address+34000;
    for(i=0;i<18;++i)rv_record(&root,10,1,i,0);
    events=RV_PTR(scratch);buffer_header(events,280);q.args[10]=scratch;q.args[11]=280;
    CHECK(rv_service(&root,RV_EVENTS,1,&q,&p)==RV_OK);CHECK(events->count==16&&events->first_sequence==3&&events->last_sequence==18&&events->dropped==2);
    CHECK(events->events[0].sequence==3&&events->events[15].sequence==18);
    q=request();q.args[4]--;CHECK(rv_service(&root,RV_EPOCHS,1,&q,&p)==RV_STALE);
    q=request();q.args[10]=0xfffffffcu;q.args[11]=8;CHECK(rv_service(&root,RV_CRC32,1,&q,&p)==RV_RANGE);
    q=request();q.flags=1;CHECK(rv_service(&root,RV_QUERY,0,&q,&p)==RV_ARGUMENT);
    q=request();CHECK(rv_service(&root,RV_SHA256,1,&q,&p)==RV_UNSUPPORTED);
    q=request();CHECK(rv_service(&root,RV_CRC32,1,&q,&p)==RV_OK&&p.detail==0);
    q.args[13]=1;CHECK(rv_service(&root,RV_CRC32,1,&q,&p)==RV_ARGUMENT);
    root.inflight=0;q=request();CHECK(rv_service(&root,RV_UNIT,1,&q,&p)==RV_OWNER);
    root.event_head=~0u;rv_record(&root,10,0,0,0);CHECK(root.state==RV_FENCED&&root.fault==(uint32_t)RV_RANGE);
    setup();root.epoch[RV_HEAP_E]=~0u;rv_notify(&root,16,0,0);CHECK(root.state==RV_FENCED&&root.flags[F_STOP]);
}

static void integrated_faults(void)
{
    unsigned i;
    for(i=0;i<7;++i){
        setup();
        switch(i){
        case 0:files[0][320]^=1;break;
        case 1:files[0][48]^=1;seal(files[0],length);break;
        case 2:files[0][rv_be32(fixture+156)]^=1;seal(files[0],length);break;
        case 3:files[0][rv_be32(fixture+168)]^=1;seal(files[0],length);break;
        case 4:rv_put32(files[0]+rv_be32(fixture+144),252);seal(files[0],length);break;
        case 5:files[0][212]^=1;seal(files[0],length);break;
        default:rv_put32(files[0]+352,length+64);rv_put32(files[0]+rv_be32(fixture+144)+4,length+64);seal(files[0],length);break;
        }
        CHECK(load()!=RV_OK);check_no_publish();
        if(i==2||i==3)CHECK(boot_calls==1&&init_calls==1);else CHECK(!boot_calls&&!init_calls);
    }
}
static void hook_checks(void)
{
    uint32_t frame[32]={0},caller=0x20301234,unit_epoch,boot,heap,image;
    RvSession *s;
    setup();CHECK(load()==RV_OK);s=rv_session(&root);
    root.ui_restore[6]=root.image_address+33000;root.ui_restore[7]=root.image_address+33100;
    RV_WORD(0x2022f5a8)=root.ui_restore[6];s->rows=16;s->cursor=11;
    frame[1]=0x11223344;frame[15]=11;rv_hook_observe(&root,2,frame);
    CHECK(frame[7]==11&&frame[1]==(uint32_t)(uintptr_t)rv_skip_02);
    rv_hook_observe(&root,5,frame);CHECK(frame[13]==root.ui_restore[7]&&frame[1]==(uint32_t)(uintptr_t)rv_skip_05);
    frame[1]=0x11223344;frame[7]=99;rv_hook_observe(&root,6,frame);
    CHECK(frame[1]==(uint32_t)(uintptr_t)rv_skip_06&&frame[7]==0&&last_entry==272);
    frame[1]=0x11223344;frame[4]=0x21;frame[24]=0x10203040;frame[25]=0x50607080;frame[26]=0x90a0b0c0;
    rv_hook_observe(&root,10,frame);
    CHECK(frame[1]==(uint32_t)(uintptr_t)rv_skip_10&&last_entry==268);
    CHECK(last_request.args[8]==0x21&&last_request.args[9]==0x10203040&&last_request.args[12]==0x50607080&&last_request.args[13]==0x90a0b0c0);
    frame[4]=0x22;rv_hook_observe(&root,10,frame);CHECK(last_entry==272);
    s->rows=9;rv_hook_observe(&root,10,frame);CHECK(last_entry==276);
    {uint32_t before=engine_calls;frame[1]=0x11223344;rv_hook_observe(&root,8,frame);CHECK(engine_calls==before&&frame[1]==(uint32_t)(uintptr_t)rv_skip_08);}
    frame[1]=0x11223344;RV_WORD(0x205d9c00)=55;
    {uint32_t before=engine_calls;rv_hook_observe(&root,10,frame);CHECK(engine_calls==before&&frame[1]==0x11223344);}
    RV_WORD(0x205d9c00)=56;engine_result=RV_CLOSE_AND_PASS;rv_hook_observe(&root,10,frame);
    CHECK(frame[1]==0x11223344&&RV_WORD(0x2022f5a8)==0x2022d610);
    setup();frame[16]=caller;unit_epoch=root.epoch[RV_UNIT_E];rv_hook_observe(&root,20,frame);
    CHECK(frame[16]==(uint32_t)(uintptr_t)rv_post_20&&(root.flags[F_RX]&1)&&root.epoch[RV_UNIT_E]==unit_epoch+1);
    frame[15]=0;rv_hook_observe(&root,276,frame);CHECK(frame[16]==caller&&frame[15]==0&&!(root.flags[F_RX]&1)&&root.post[2]==0);
    setup();CHECK(load()==RV_OK);image=root.image_address;boot=root.epoch[RV_BOOT_E];heap=root.epoch[RV_HEAP_E];
    rv_notify(&root,17,0,5);CHECK(root.state==RV_FENCED&&root.image_address==image&&root.epoch[RV_BOOT_E]==boot&&root.epoch[RV_HEAP_E]==heap);
    CHECK(load()==RV_OK&&root.image_address==image);
    frame[16]=caller;frame[11]=0;rv_hook_observe(&root,18,frame);
    CHECK(frame[16]==caller&&root.image_address==0&&root.epoch[RV_BOOT_E]==boot+1&&root.epoch[RV_HEAP_E]==heap+1);
}

int main(int argc,char **argv)
{
    FILE *f;size_t n;
    CHECK(argc==4);f=fopen(argv[1],"rb");CHECK(f);length=(uint32_t)fread(fixture,1,sizeof(fixture),f);CHECK(!fclose(f)&&length>384&&length<RV_MAX_FILE);
    f=fopen(argv[2],"rb");CHECK(f);n=fread(collision,1,sizeof(collision),f);CHECK(!fclose(f)&&n==length);
    f=fopen(argv[3],"rb");CHECK(f);large_length=(uint32_t)fread(large_code,1,sizeof(large_code),f);CHECK(!fclose(f));
    gate_checks();limit_checks();loader_checks();selection_checks();integrated_faults();abort_checks();grain_checks();service_checks();hook_checks();
    printf("PASS_HOST checks=%u sanitizer=ASan+UBSan transport=mock engine=mock native_execution=0\n",checks);return 0;
}
