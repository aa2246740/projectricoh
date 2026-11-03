#include "diag.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sanitizer/asan_interface.h>

#define CHECK(x) do{++checks;if(!(x)){fprintf(stderr,"line=%u %s\n",__LINE__,#x);exit(91);}}while(0)
static _Alignas(16) uint8_t memory[0x800000];
static RvRoot r;
static uint8_t diag_file[16384],full_file[100000],settings_before[4096];
static uint32_t diag_bytes,full_bytes,checks,opens,reads,closes,allocs,frees,invokes,psw=0xc1;
static int mode,read_fail,close_fail,free_fail,header_fail,missing_diag,missing_full;
static const char *test_name;
typedef struct {uint32_t base,bytes,live;} Span;
static Span spans[128];static unsigned span_count;
typedef struct {unsigned live,which;uint32_t pos;} Fd;
static Fd fds[4];
const uint8_t rv_skip_01[4]={0},rv_skip_02[4]={0},rv_skip_05[4]={0},rv_skip_06[4]={0},
    rv_skip_07[4]={0},rv_skip_08[4]={0},rv_close_07[4]={0};

void *rv_host_address(uint32_t a)
{if(a==RV_ROOT)return &r;CHECK(a>=0x20000000u&&a<0x20800000u);return memory+(a-0x20000000u);}
uint32_t diag_host_address(const void *p)
{
    uintptr_t a=(uintptr_t)p,b=(uintptr_t)memory;
    CHECK(a>=b&&a-b<sizeof(memory));return 0x20000000u+(uint32_t)(a-b);
}
uint32_t rv_irq_save(void){uint32_t old=psw;psw&=~0x40u;return old;}
void rv_irq_restore(uint32_t value){psw=value;}
void rv_cache_sync(void){}
static void metadata(Span *s)
{
    __asan_unpoison_memory_region(rv_host_address(s->base),12);
    RV_WORD(s->base)=0;RV_BYTE(s->base+4)=(uint8_t)s->live;RV_WORD(s->base+8)=s->bytes;
}
uint32_t rv_native_alloc(uint32_t n)
{
    /* The host loader workspace contains 64-bit pointers. Keep payloads
     * aligned to eight here; target M32R rounds payloads to four. */
    unsigned i,j;uint32_t need=(n+12u+7u)&~7u,a;
    if(!n||need>=262144)return 0;
    for(i=0;i<span_count;++i)if(!spans[i].live&&spans[i].bytes>=need)break;
    if(i==span_count)return 0;
    CHECK(span_count<127);
    if(spans[i].bytes-need>=28){
        for(j=span_count;j>i+1;--j)spans[j]=spans[j-1];
        spans[i+1]=(Span){spans[i].base+need,spans[i].bytes-need,0};
        ++span_count;spans[i].bytes=need;metadata(&spans[i+1]);
    }
    spans[i].live=1;a=spans[i].base+12;
    __asan_unpoison_memory_region(rv_host_address(a),spans[i].bytes-12);metadata(&spans[i]);++allocs;
    if(header_fail&&r.state==RV_READY&&n>=16384){RV_BYTE(a-8)=3;header_fail=0;}
    return a;
}
void rv_native_free(uint32_t a)
{
    unsigned i,j;for(i=0;i<span_count&&spans[i].base+12!=a;++i){}
    CHECK(i<span_count&&spans[i].live);
    if(free_fail&&r.state==RV_READY){free_fail=0;return;}
    spans[i].live=0;metadata(&spans[i]);++frees;
    __asan_poison_memory_region(rv_host_address(a),spans[i].bytes-12);
    if(i+1<span_count&&!spans[i+1].live){
        spans[i].bytes+=spans[i+1].bytes;
        for(j=i+1;j+1<span_count;++j)spans[j]=spans[j+1];--span_count;
    }
    if(i&&!spans[i-1].live){
        spans[i-1].bytes+=spans[i].bytes;
        for(j=i;j+1<span_count;++j)spans[j]=spans[j+1];--span_count;--i;
    }
    metadata(&spans[i]);
}
int32_t rv_native_open(const char *path,uint32_t flags)
{
    unsigned i,which;CHECK(!flags);++opens;
    if(!strcmp(path,"/IROM/GXRCE0.DAT")||!strcmp(path,"/IROM/GXRCE1.DAT"))return -2;
    if(!strcmp(path,"/IROM/T5000A.BIN")||!strcmp(path,"/IROM/T5000B.BIN")||
       !strcmp(path,"/IROM/T2800A.BIN")||!strcmp(path,"/IROM/T2800B.BIN")||
       !strcmp(path,"/IROM/TM000A.BIN")||!strcmp(path,"/IROM/TM000B.BIN"))return -1;
    if(!strcmp(path,"/ATA1/GXRCE.DAT")){if(missing_diag)return -2;which=0;}
    else {CHECK(!strcmp(path,"/ATA1/GXRCF.DAT"));if(missing_full)return -2;which=1;}
    for(i=0;i<4&&fds[i].live;++i){}CHECK(i<4);fds[i]=(Fd){1,which,0};return 20+(int32_t)i;
}
int32_t rv_native_read(int32_t fd,void *out,uint32_t n)
{
    unsigned i=(unsigned)(fd-20);uint32_t count;uint8_t *data;
    CHECK(i<4&&fds[i].live&&n);++reads;
    if(fds[i].which&&read_fail&&fds[i].pos>=1024){int result=read_fail;read_fail=0;return result==1?-9:(int32_t)n+1;}
    data=fds[i].which?full_file:diag_file;count=(fds[i].which?full_bytes:diag_bytes)-fds[i].pos;
    if(count>n)count=n;if(count>73)count=73;
    memcpy(out,data+fds[i].pos,count);fds[i].pos+=count;return (int32_t)count;
}
int32_t rv_native_close(int32_t fd)
{
    unsigned i=(unsigned)(fd-20);CHECK(i<4&&fds[i].live);fds[i].live=0;++closes;
    if(fds[i].which&&close_fail){close_fail=0;return -7;}return 0;
}
int32_t rv_native_sd_id(void *p){const uint32_t id[4]={1,2,3,4};memcpy(p,id,16);return 0;}
int32_t rv_native_layer(uint32_t a,uint32_t b,uint32_t c){CHECK(a==2&&b==1&&!c);return 0;}
int32_t diag_native_context(void){return 0;}
int32_t diag_native_language(void){return 0;}
int32_t diag_native_ascii(const char *s,uint32_t n,void *out,uint32_t language)
{CHECK(n==12&&!language);memcpy(out,s,n+1);return 0;}
/* Any persistent/device write or RPC is a fatal fixture error. */
int32_t rv_native_write(int32_t f,const void *p,uint32_t n){(void)f;(void)p;(void)n;CHECK(0);return -1;}
int32_t rv_native_create(const char *p,uint32_t n){(void)p;(void)n;CHECK(0);return -1;}
int32_t rv_native_delete(const char *p){(void)p;CHECK(0);return -1;}
int32_t rv_native_rename(const char *p,const char *q){(void)p;(void)q;CHECK(0);return -1;}
int32_t rv_rpc8_native(uint32_t a,uint32_t b){(void)a;(void)b;CHECK(0);return -1;}
int32_t rv_native_preview(uint32_t a){(void)a;CHECK(0);return -1;}
int32_t rv_invoke(uint32_t entry,const RvApi *api,uint32_t context,const RvRequest *q,RvReply *reply)
{
    RvSession *s=rv_session(&r);uint32_t offset;CHECK(s&&!api&&context==r.lease);++invokes;
    offset=entry-s->image_address;
    switch(offset){
    case 256:return diag_bootstrap(api,context,q,reply);
    case 272:return diag_init(api,context,q,reply);
    case 288:return diag_menu(api,context,q,reply);
    case 304:return diag_event(api,context,q,reply);
    case 368:return diag_apply(api,context,q,reply);
    case 320:case 336:case 352:case 384:case 400:return diag_close(api,context,q,reply);
    default:CHECK(0);return RV_FAULT;
    }
}
static void reset(void)
{
    __asan_unpoison_memory_region(memory,sizeof(memory));memset(memory,0,sizeof(memory));memset(&r,255,244);
    memcpy(r.pins,rv_pins,12);RV_WORD(0x200d3488)=0x20704800;RV_WORD(0x200d348c)=0x20744800;
    RV_WORD(0x200c0dc4)=0x40000;span_count=1;spans[0]=(Span){0x2070480c,0x3fff4,0};
    __asan_poison_memory_region(rv_host_address(0x20704800),262144);metadata(&spans[0]);
    RV_WORD(0x2022f5a8)=0x2022d610;RV_BYTE(0x2022f5ac)=7;
    RV_BYTE(0x2022f71c)=5;RV_WORD(0x2022f720)=0x2022f000;
    RV_WORD(0x205a27d8)=RV_NATIVE_VIEWS;RV_BYTE(0x205a27d4)=1;
    RV_BYTE(RV_NATIVE_VIEWS)=33;RV_WORD(RV_NATIVE_VIEWS+4)=0x2022f71c;
    RV_WORD(0x205d9bf8)=8;RV_WORD(0x205d9c00)=56;RV_BYTE(0x205a280f)=2;
    memcpy(RV_PTR(0x2040f81c),"jlaunch",8);RV_BYTE(0x2040f848)=1;RV_BYTE(0x2040f849)=0x51;RV_WORD(0x2040f804)=1;
    RV_WORD(0x200c0dac)=0x20500000;RV_WORD(0x200c0db0)=4096;
    memset(RV_PTR(0x20500000),0xa7,4096);memcpy(settings_before,RV_PTR(0x20500000),4096);
}
static uint32_t read_file(const char *path,uint8_t *out,size_t n)
{FILE *f=fopen(path,"rb");size_t got;CHECK(f);got=fread(out,1,n,f);CHECK(!ferror(f)&&!fclose(f));return (uint32_t)got;}
static void fix_crc(void)
{rv_put32(full_file+24,gxrce_crc32(full_file+256,full_bytes-256));rv_put32(full_file+20,0);rv_put32(full_file+20,gxrce_crc32(full_file,256));}
int main(int argc,char **argv)
{
    RvSession *s;DiagState *d;uint32_t frame[32]={0},i,a,b,old_reads,code_crc,expected_pin=0,ui,cell;
    CHECK(argc==4);test_name=argv[3];diag_bytes=read_file(argv[1],diag_file,sizeof(diag_file));
    full_bytes=read_file(argv[2],full_file,sizeof(full_file));CHECK(full_bytes==58160);reset();
    if(!strcmp(test_name,"unit-q")){memcpy(RV_PTR(0x2040f81c),"qlaunch",8);expected_pin=1;}
    if(!strcmp(test_name,"unit-m")){memcpy(RV_PTR(0x2040f81c),"l08firm",8);expected_pin=2;}
    if(!strcmp(test_name,"missing-full"))missing_full=1;
    if(!strcmp(test_name,"missing-diag"))missing_diag=1;
    if(!strcmp(test_name,"read-error"))read_fail=1;
    if(!strcmp(test_name,"read-oversize"))read_fail=2;
    if(!strcmp(test_name,"close-error"))close_fail=1;
    if(!strcmp(test_name,"free-error"))free_fail=1;
    if(!strcmp(test_name,"allocation-header"))header_fail=1;
    if(!strcmp(test_name,"unit-unknown"))memcpy(RV_PTR(0x2040f81c),"unknown",8);
    if(!strcmp(test_name,"cmp-version"))RV_BYTE(0x2040f84b)=1;
    if(!strcmp(test_name,"short-0"))full_bytes=0;
    if(!strcmp(test_name,"short-255"))full_bytes=255;
    if(!strcmp(test_name,"short-256"))full_bytes=256;
    if(!strcmp(test_name,"truncated"))--full_bytes;
    if(!strcmp(test_name,"trailing"))full_file[full_bytes++]=0xab;
    if(!strcmp(test_name,"header-crc"))full_file[20]^=1;
    if(!strcmp(test_name,"body-id")){full_file[48]^=1;fix_crc();}
    if(!strcmp(test_name,"build-id")){full_file[80]^=1;fix_crc();}
    if(!strcmp(test_name,"abi-id")){full_file[212]^=1;fix_crc();}
    if(!strcmp(test_name,"payload-crc"))full_file[500]^=1;
    if(!strcmp(test_name,"reloc-layout")){rv_put32(full_file+rv_be32(full_file+144),252);fix_crc();}
    if(!strcmp(test_name,"reloc-cell")){
        cell=rv_be32(full_file+rv_be32(full_file+144));full_file[cell+3]^=4;fix_crc();
    }
    if(!strcmp(test_name,"pin-mismatch")){full_file[rv_be32(full_file+168)+24]^=1;fix_crc();}
    if(!strcmp(test_name,"heap-low"))CHECK(rv_native_alloc(170000));
    if(!strcmp(test_name,"heap-fragmented")){
        a=rv_native_alloc(65536);CHECK(rv_native_alloc(16384));b=rv_native_alloc(65536);
        CHECK(rv_native_alloc(16384));CHECK(rv_native_alloc(65536));rv_native_free(a);rv_native_free(b);
    }
    if(!strcmp(test_name,"ui-array"))RV_WORD(0x205a27d8)=0x207f0000;
    if(!strcmp(test_name,"ui-count0"))RV_BYTE(0x205a27d4)=0;
    if(!strcmp(test_name,"ui-count3"))RV_BYTE(0x205a27d4)=3;
    if(!strcmp(test_name,"ui-tag"))RV_BYTE(RV_NATIVE_VIEWS)=32;
    if(!strcmp(test_name,"ui-count2")){
        RV_BYTE(0x205a27d4)=2;RV_BYTE(RV_NATIVE_VIEWS+8)=33;RV_WORD(RV_NATIVE_VIEWS+12)=0x2022f71c;
    }
    code_crc=gxrce_crc32(full_file,full_bytes);
    rv_hook_observe(&r,1,frame);
    CHECK(!memcmp(settings_before,RV_PTR(0x20500000),4096));CHECK(gxrce_crc32(full_file,full_bytes)==code_crc);
    for(i=0;i<4;++i)CHECK(!fds[i].live);
    if(missing_diag||!strcmp(test_name,"ui-array")||!strcmp(test_name,"ui-count0")||
       !strcmp(test_name,"ui-count3")){
        CHECK(r.state==RV_DISABLED_UNTIL_REBOOT&&RV_BYTE(0x2022f5ac)==7&&!r.ui_restore[0]);
        printf("CASE %s PASS factory=7 disabled=1 no_device_or_file_writes=1\n",test_name);return 0;
    }
    s=rv_session(&r);CHECK(s&&r.state==RV_READY&&s->capabilities==(RV_READ_CAPS|CAP_UI));
    /* A parent tag at H01 is allowed by UI_LIST. Native code constructs the
     * image view after H01 returns, then H02 recognizes the owned list. */
    if(!strcmp(test_name,"ui-tag")){CHECK(RV_BYTE(0x2022f5ac)==16);RV_BYTE(RV_NATIVE_VIEWS)=33;}
    d=RV_PTR(s->image_address+rv_image_span(s->image_bytes,s->bss_bytes));
    CHECK(d->sampled&&d->words[0]==DIAG_SIGNATURE&&RV_BYTE(0x2022f5ac)==16&&s->rows==16);
    CHECK(d->words[11]>>30==DIAG_T_SKIP);CHECK(d->words[12]==0x03220120u);
    if(strcmp(test_name,"unit-unknown")&&strcmp(test_name,"cmp-version"))CHECK((d->words[11]>>16&0x3fff)==0x3fff);
    CHECK(!d->words[13]&&!d->words[14]);CHECK(d->words[1]||(header_fail==0));
    if(!strcmp(test_name,"good")||!strcmp(test_name,"unit-q")||!strcmp(test_name,"unit-m")||!strcmp(test_name,"ui-count2")){
        CHECK(d->words[2]==0&&d->words[3]==58160&&d->words[4]==code_crc&&d->words[8]==rv_pins[expected_pin]);
        CHECK(d->words[9]==rv_pins[expected_pin]&&d->words[10]==89240);
        CHECK((d->words[1]&0xffffffu)==0xffffffu);
    }
    if(missing_full)CHECK(d->words[2]>>24==1&&d->words[3]==0);
    if(!strcmp(test_name,"read-error")||!strcmp(test_name,"read-oversize"))CHECK(d->words[2]>>24==2);
    if(!strcmp(test_name,"close-error"))CHECK(d->words[2]>>24==4);
    if(!strcmp(test_name,"body-id"))CHECK((d->words[2]>>16&255)==GXRCE_BODY_ID);
    if(!strcmp(test_name,"build-id")||!strcmp(test_name,"abi-id"))CHECK((d->words[2]>>16&255)==GXRCE_RESIDENT_ID);
    if(!strcmp(test_name,"header-crc"))CHECK((d->words[2]>>16&255)==GXRCE_CRC);
    if(!strcmp(test_name,"payload-crc"))CHECK((d->words[2]>>8&255)==GXRCE_CRC);
    if(!strcmp(test_name,"truncated")||!strcmp(test_name,"trailing")||!strcmp(test_name,"short-256"))CHECK((d->words[2]>>8&255)==GXRCE_LENGTH);
    if(!strcmp(test_name,"short-0")||!strcmp(test_name,"short-255"))CHECK((d->words[2]>>16&255)==255);
    if(!strcmp(test_name,"reloc-cell")||!strcmp(test_name,"reloc-layout"))CHECK((d->words[2]>>8&255)==GXRCE_RELOCATION);
    if(!strcmp(test_name,"pin-mismatch"))CHECK((d->words[2]&255)==1&&d->words[8]!=d->words[9]);
    if(!strcmp(test_name,"unit-unknown")||!strcmp(test_name,"cmp-version"))CHECK((d->words[2]&255)==2);
    if(!strcmp(test_name,"heap-low"))CHECK((d->words[1]&0x7ff)==0x7f8&&!(d->words[1]&(1u<<22)));
    if(!strcmp(test_name,"heap-fragmented"))CHECK((d->words[1]&0x7ff)==0x7f0&&!(d->words[1]&(1u<<22)));
    if(!strcmp(test_name,"free-error"))CHECK(d->words[1]==0x02000001u);
    if(!strcmp(test_name,"allocation-header"))CHECK(d->words[1]==0x01000001u);
    if(!strcmp(test_name,"good"))for(i=0;i<16;++i)puts(d->rows[i]);
    old_reads=reads;ui=r.ui_block;
    for(i=1;i<=16;++i){RV_BYTE(0x2022f726)=i;rv_hook_observe(&r,8,frame);CHECK(s->cursor==i-1);}
    CHECK(reads==old_reads&&r.ui_block==ui);
    frame[11]=0;rv_hook_observe(&r,7,frame);CHECK(!r.ui_restore[0]&&RV_BYTE(0x2022f5ac)==7);
    rv_hook_observe(&r,1,frame);CHECK(reads==old_reads&&r.ui_block==ui&&RV_BYTE(0x2022f5ac)==16);
    CHECK(!memcmp(settings_before,RV_PTR(0x20500000),4096)&&psw==0xc1);
    printf("CASE %s PASS actual_resident_loader=1 real_diag_C=1 source_bridge=1 "
           "ASan_UBSan=1 opens=%u reads=%u closes=%u allocs=%u frees=%u invokes=%u checks=%u "
           "RPC=0 file_writes=0 S_writes=0 IROM_install=0\n",test_name,opens,reads,closes,allocs,frees,invokes,checks);
    (void)mode;return 0;
}
