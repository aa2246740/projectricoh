#include "probes.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdalign.h>
#include <sanitizer/asan_interface.h>

enum { BASE=0x20000000u, HEAP=0x20600000u, END=0x20800000u };
enum { MAIN_BLOCK, WITNESS_BLOCK, CAPACITY_BLOCK };
typedef struct { uint32_t base,bytes,role,live; } Allocation;
static alignas(16) uint8_t memory[END-BASE],candidate[RV_MAX_FILE+1],irom[32769],loaded[RV_MAX_FILE];
static Allocation allocations[64];
static struct { uint32_t open,source,offset; } descriptors[3];
static RvRoot root;
RvRoot *rv_host_root=&root;
static uint32_t next_address,allocation_count,allocation_role,length,irom_bytes=9;
static uint32_t checks,service_calls,forbidden,writes,rpc_calls,draws,capacity_attempts,capacity_frees;
static uint32_t capacity_limit,capacity_pending,capacity_last,allocation_witnesses;
static uint32_t free_calls,free_refuse,stale_frees,closes,read_error,close_error,malformed_reply;
static uint32_t inspect_calls,inspect_fail,state_reads_after_inspect_failure,code_crc,entries_called[10];
static uint32_t service_histogram[17][13],unit_index,settings_before,rows_captures;
static const uint32_t sizes[5]={65536,49152,40960,32768,16384};
static const char *unit_names[3]={"jlaunch","qlaunch","l08firm"};
static FILE *capture;
#define CHECK(x) do { ++checks; if (!(x)) { fprintf(stderr,"engine=%d line=%d %s\n",PV_ENGINE,__LINE__,#x); exit(1); } } while(0)

static PvState *state(void)
{ RvSession *s=rv_session(&root); return s?(PvState *)(memory+(s->context.state_address-BASE)):0; }
void *rv_host_address(uint32_t a)
{
    unsigned i;
    CHECK(a>=BASE&&a<END);
    for(i=0;i<allocation_count;++i) {
        Allocation *x=&allocations[i];
        if(a>=x->base&&a-x->base<x->bytes) {
            CHECK(x->live);
            CHECK(x->role!=CAPACITY_BLOCK);
            if(x->role==WITNESS_BLOCK&&inspect_fail)++state_reads_after_inspect_failure;
        }
    }
    return memory+(a-BASE);
}
void *pv_host_pointer(uint32_t a,uint32_t n)
{
    unsigned i;
    CHECK(n&&a>=BASE&&a<END&&n<=END-a);
    for(i=0;i<allocation_count;++i) {
        Allocation *x=&allocations[i];
        if(a>=x->base&&a-x->base<x->bytes)CHECK(n<=x->bytes-(a-x->base));
    }
    return rv_host_address(a);
}
uint32_t pv_host_address(const void *p,uint32_t n)
{
    uintptr_t a=(uintptr_t)p,begin=(uintptr_t)memory;
    CHECK(a>=begin&&a-begin<sizeof(memory)&&n<=sizeof(memory)-(a-begin));
    return BASE+(uint32_t)(a-begin);
}
uint32_t rv_irq_save(void){return 0;}
void rv_irq_restore(uint32_t n){(void)n;}
void rv_cache_sync(void){}
int32_t rv_native_context(void){return 0;}
uint32_t rv_native_alloc(uint32_t n)
{
    Allocation *x; uint32_t a;
    if(allocation_role==CAPACITY_BLOCK) {
        CHECK(n==sizes[capacity_attempts%5]);++capacity_attempts;
        if(n>capacity_limit)return 0;
    }
    CHECK(allocation_count<64);
    a=next_address+16;next_address=(a+n+15)&~15u;CHECK(next_address<END);
    x=&allocations[allocation_count++];*x=(Allocation){a,n,allocation_role,1};
    RV_WORD(a-12)=0;RV_WORD(a-8)=0;RV_BYTE(a-8)=1;RV_WORD(a-4)=n;
    if(allocation_role==CAPACITY_BLOCK)__asan_poison_memory_region(memory+(a-BASE),n);
    if(allocation_role==WITNESS_BLOCK)++allocation_witnesses;
    return a;
}
void rv_native_free(uint32_t a)
{
    unsigned i;++free_calls;
    for(i=0;i<allocation_count&&allocations[i].base!=a;++i){}
    CHECK(i<allocation_count&&allocations[i].live);
    if(root.heap_epoch!=root.epoch[RV_HEAP_E])++stale_frees;
    CHECK(allocations[i].role==CAPACITY_BLOCK);
    if(!free_refuse){RV_BYTE(a-8)=0;allocations[i].live=0;}
}
int32_t rv_native_open(const char *path,uint32_t flags)
{
    unsigned src,i;
    CHECK(flags==0);
    if(!strcmp(path,"/ATA1/GXRCE.DAT"))src=2;
    else if(!strcmp(path,"/IROM/GXRCE0.DAT"))src=0;
    else if(!strcmp(path,"/IROM/GXRCE1.DAT"))src=1;
    else {CHECK(0);return -1;}
    for(i=0;i<3&&descriptors[i].open;++i){}
    CHECK(i<3);descriptors[i].open=1;descriptors[i].source=src;descriptors[i].offset=0;
    return 10+(int32_t)i;
}
int32_t rv_native_read(int32_t fd,void *out,uint32_t n)
{
    unsigned i=(unsigned)(fd-10);uint32_t available;const uint8_t *src;
    CHECK(i<3&&descriptors[i].open);
    if(read_error)return -77;
    src=descriptors[i].source==2?candidate:irom;
    available=(descriptors[i].source==2?length:irom_bytes)-descriptors[i].offset;
    if(n>available)n=available;if(n>512)n=512;
    memcpy(out,src+descriptors[i].offset,n);descriptors[i].offset+=n;return (int32_t)n;
}
int32_t rv_native_close(int32_t fd)
{
    unsigned i=(unsigned)(fd-10);CHECK(i<3&&descriptors[i].open);
    descriptors[i].open=0;++closes;return close_error?-99:0;
}
int32_t rv_native_create(const char *p,uint32_t n){(void)p;(void)n;++writes;CHECK(0);return -1;}
int32_t rv_native_write(int32_t f,const void *p,uint32_t n){(void)f;(void)p;(void)n;++writes;CHECK(0);return -1;}
int32_t rv_native_delete(const char *p){(void)p;++writes;CHECK(0);return -1;}
int32_t rv_native_rename(const char *p,const char *q){(void)p;(void)q;++writes;CHECK(0);return -1;}
uint32_t rv_native_unit(uint32_t n){CHECK(n==1);return 0x200b1000;}
int32_t rv_native_rpc_ready(void){return 1;}
int32_t rv_native_rpc_limit(void){return 65536;}
int32_t rv_rpc8_native(uint32_t op,uint32_t value){(void)op;(void)value;++rpc_calls;CHECK(0);return -1;}
int32_t rv_native_preview(uint32_t n){(void)n;CHECK(0);return -1;}
int32_t rv_native_sd_id(void *p){unsigned i;for(i=0;i<16;++i)((uint8_t *)p)[i]=(uint8_t)(i+1);return 0;}
int32_t rv_native_language(void){return 1;}
int32_t rv_native_ascii(const char *src,uint32_t n,void *out,uint32_t language)
{ CHECK(n==12&&language==1);memcpy(out,src,n);((char *)out)[n]=0;return 0; }
int32_t rv_native_layer(uint32_t a,uint32_t b,uint32_t c){(void)a;(void)b;(void)c;CHECK(0);return -1;}
int32_t rv_native_draw(uint32_t layer,uint32_t address,uint32_t extra)
{CHECK(layer==2&&address==rv_session(&root)->context.ui_state_address&&extra==0);++draws;return 0;}

/* Independent policy around the real service implementation. The service
 * archive's api.c alone is compiled with rv_service=pi_observe_service. */
static int allowed(uint32_t id,uint32_t op)
{
    switch(id) {
    case 1:return op==1||op==2||op==4||op==6;
    case 2:return op==1||op==2||op==3;
    case 6:return op==1||op==3;
    case 7:case 8:case 13:return op==1;
    case 9:return op==12;
    case 10:return op==1||op==3||op==4;
    case 11:return op==1||op==2;
    case 14:return op<=2;
    default:return 0;
    }
}
int32_t pi_observe_service(RvRoot *r,uint32_t id,uint32_t op,const RvRequest *q,RvReply *p)
{
    int32_t result;PvState *v=state();++service_calls;
    if(!allowed(id,op)){++forbidden;CHECK(0);}
    CHECK(id<17&&op<13);++service_histogram[id][op];
    if(capacity_pending)CHECK(id==RV_LEASE&&op==2&&q->args[1]==capacity_pending);
    if(id==RV_LEASE&&op==1) {
        allocation_role=v&&v->witness.attempted&&!v->witness.token?WITNESS_BLOCK:CAPACITY_BLOCK;
    }
    if(id==RV_LEASE&&op==3) {
        ++inspect_calls;CHECK(q->args[1]==root.lease&&q->args[8]==v->witness.token);
        if(inspect_fail){memset(p,0,sizeof(*p));p->version=1;p->bytes=32;p->status=RV_STALE;return RV_STALE;}
    }
    result=rv_service(r,id,op,q,p);
    if(id==RV_LEASE&&op==1&&allocation_role==CAPACITY_BLOCK&&result==RV_OK) {
        capacity_pending=p->token;capacity_last=service_calls;
    }
    if(id==RV_LEASE&&op==2) {
        CHECK(capacity_pending&&capacity_last+1==service_calls);
        ++capacity_frees;
        if(!result){CHECK(p->detail==0x100);capacity_pending=0;}
        else CHECK(p->detail==0x101);
    }
    allocation_role=MAIN_BLOCK;
    if(malformed_reply){malformed_reply=0;p->actual=0;}
    return result;
}

int32_t rv_invoke(uint32_t address,const RvApi *api,uint32_t context,const RvRequest *q,RvReply *p)
{
    static RvEngineEntry const entries[10]={pv_bootstrap,pv_init,pv_menu_open,pv_event,pv_panel_open,
        pv_panel_event,pv_panel_abort,pv_apply_step,pv_shutdown,pv_abort};
    RvSession *ss=rv_session(&root);uint32_t off=address-ss->image_address,index;
    CHECK(!api&&root.inflight==1&&context==root.lease);
    CHECK(q->args[10]==root.block+offsetof(RvSession,context)&&q->args[11]==120);
    CHECK(off>=ss->code_begin&&(off-ss->code_begin)%16==0);
    index=(off-ss->code_begin)/16;CHECK(index<10);++entries_called[index];
    /* Portable C entry dispatch is deliberate. M32R bytes are loaded and
     * relocated by rv_load, but are not executable on the host CPU. */
    return entries[index](api,context,q,p);
}
static int32_t invoke(uint32_t index,uint32_t a,uint32_t b,RvReply *p)
{
    RvSession *ss=rv_session(&root);RvRequest q={0};q.args[8]=a;q.args[9]=b;
    return rv_engine(&root,ss->code_begin+16*index,&q,p);
}
static void reset(void)
{
    unsigned i;
    __asan_unpoison_memory_region(memory,sizeof(memory));memset(memory,0,sizeof(memory));
    memset(&root,0,sizeof(root));memset(allocations,0,sizeof(allocations));memset(descriptors,0,sizeof(descriptors));
    next_address=HEAP;allocation_count=0;allocation_role=MAIN_BLOCK;allocation_witnesses=0;
    capacity_limit=65536;capacity_pending=capacity_attempts=capacity_frees=0;
    free_calls=free_refuse=read_error=close_error=inspect_fail=state_reads_after_inspect_failure=malformed_reply=0;
    RV_WORD(0x200d3488)=HEAP;RV_WORD(0x200d348c)=END;RV_WORD(0x200c0dc4)=END-HEAP;
    RV_WORD(0x2040f804)=1;RV_WORD(0x200c0dac)=0x200e0000;RV_WORD(0x200c0db0)=0x1000;
    RV_BYTE(0x200e06dd)=9;RV_BYTE(0x200e06de)=9;
    memcpy(RV_PTR(0x200b1004),unit_names[unit_index],8);RV_BYTE(0x200b1030)=1;RV_BYTE(0x200b1031)=0x51;
    rv_reset(&root);for(i=0;i<12;++i)root.epoch[i]=1;
    root.flags=RF_SD;root.pins[0]=0xdf2bcaf5;root.pins[1]=0x6700e6ff;root.pins[2]=0x1b3c7000;
    irom_bytes=9;memcpy(irom,"123456789",9);
    settings_before=pv_crc32(RV_PTR(0x200e0000),0x1000);
}
static void load(void)
{
    RvSession *ss;unsigned i;uint8_t *image;
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&root.state==RV_READY);
    ss=rv_session(&root);CHECK(ss&&ss->selected_source==RV_SOURCE_CARD&&ss->source_bytes==length);
    CHECK(ss->context.header.bytes==120&&ss->context.lease_max_bytes==65536);
    CHECK(ss->context.ui_state_bytes==0&&ss->context.state_bytes>=sizeof(PvState));
    CHECK(ss->capabilities==(RV_READ_CAPS|CAP_UI));
    image=RV_PTR(ss->image_address);memcpy(loaded,image,length);
    for(i=0;i<rv_be16(candidate+120);++i) {
        const uint8_t *rel=candidate+rv_be32(candidate+144)+8*i;
        CHECK(rv_be32(image+rv_be32(rel))==ss->image_address+rv_be32(rel+4));
    }
    code_crc=pv_crc32(image+ss->code_begin,ss->code_end-ss->code_begin);
    CHECK(state()->witness.baseline_code_crc==code_crc&&allocation_witnesses==0);
}
static void sample(void)
{RvReply p;CHECK(invoke(2,0,0,&p)==RV_CONSUMED&&p.status==RV_OK);}
static void command(uint32_t op,uint32_t value)
{RvReply p;CHECK(invoke(7,op,value,&p)==RV_CONSUMED&&p.status==RV_OK);}
static void invariants(void)
{
    RvSession *ss=rv_session(&root);
    CHECK(!writes&&!rpc_calls&&!forbidden&&!stale_frees);
    CHECK(pv_crc32(RV_PTR(0x200e0000),0x1000)==settings_before);
    CHECK(!memcmp(loaded,RV_PTR(ss->image_address),length));
    CHECK(pv_crc32(RV_PTR(ss->context.code_address),ss->context.code_bytes)==code_crc);
}
static void capture_page(uint32_t page)
{
    unsigned row;command(PV_PAGE,page);
    for(row=0;row<16;++row)fprintf(capture,"%s\n",state()->rows[row]);
    ++rows_captures;
}
static void success_path(void)
{
    RvReply p;PvState *v;uint32_t token,checks_before,sample_before;unsigned i;
    reset();load();capacity_limit=49152;sample();v=state();
    CHECK(v->sample==1);
    if(PV_ENGINE==PV_LIFE) {
        CHECK(allocation_witnesses==1&&v->witness.bytes==PV_WITNESS_BYTES&&v->witness.allocations==1);
        CHECK(v->witness.crc==v->witness.baseline_crc&&v->witness.canary_bad==0);
        CHECK(v->capacity[0].state==2&&v->capacity[0].maximum_bytes==49152);
        token=v->witness.token;checks_before=v->witness.checks;
        /* Same session, later menu boundary: generic init must not replace RAM. */
        rv_notify(&root,11,0,0);CHECK(rv_load(&root,&rv_trust)==RV_OK);sample();
        CHECK(v->witness.token==token&&allocation_witnesses==1&&v->witness.checks==checks_before+1);
        capacity_limit=40960;command(PV_PAGE,6);command(PV_SAMPLE,0);
        CHECK(v->capacity[1].state==2&&v->capacity[1].maximum_bytes==40960);
        rv_notify(&root,25,0,0);CHECK(rv_load(&root,&rv_trust)==RV_OK);
        capacity_limit=32768;command(PV_PAGE,7);command(PV_SAMPLE,0);
        CHECK(v->capacity[2].state==2&&v->capacity[2].maximum_bytes==32768);
        CHECK(v->witness.token==token&&v->witness.crc==v->witness.baseline_crc&&allocation_witnesses==1);
        CHECK(capacity_attempts==15&&capacity_frees==9&&!capacity_pending);
        for(i=0;i<3;++i)CHECK(v->capacity[i].witness_bytes==PV_WITNESS_BYTES&&v->capacity[i].boot==1&&v->capacity[i].heap==1);
        command(PV_SAMPLE,0);CHECK(capacity_attempts==15);
        CHECK(invoke(7,PV_CAPACITY,2,&p)==RV_CONSUMED&&p.status==RV_CONFLICT);
        command(PV_READ_A,0);CHECK(v->irom.state==PV_IROM_UNREFERENCED&&v->irom.crc==0xcbf43926&&v->irom.actual==9);
        irom_bytes=32768;for(i=0;i<irom_bytes;++i)irom[i]=(uint8_t)i;
        command(PV_READ_B,0);CHECK(v->irom.state==PV_IROM_UNREFERENCED&&v->irom.actual==32768&&v->irom.reads==64);
        command(PV_READ_A,0);
    } else if(PV_ENGINE==PV_NOTICE) {
        CHECK(v->unit.valid&&v->unit.main_version==0x151&&!memcmp(v->unit.name,unit_names[unit_index],8));
        CHECK((v->valid&(PV_HAVE_SD|PV_HAVE_UNIT))==(PV_HAVE_SD|PV_HAVE_UNIT));
    } else {
        CHECK(v->wb0==9&&v->wb1==9&&(v->valid&PV_HAVE_S));
        CHECK(pv_crc32(RV_PTR(0x200e0000),0x1000)==settings_before);
        RV_BYTE(0x200e06dd)=10;settings_before=pv_crc32(RV_PTR(0x200e0000),0x1000);
        rv_notify(&root,13,0,0);CHECK(rv_load(&root,&rv_trust)==RV_OK);sample();CHECK(v->wb0==10&&v->wb1==9);
    }
    /* H08's actual slim row wire format, not only the older PV_SELECT_ROW. */
    command(3,0);CHECK(v->page==3);sample_before=v->sample;
    CHECK(invoke(7,0x6dd,1,&p)==RV_CONSUMED&&p.status==RV_UNSUPPORTED&&v->sample==sample_before);
    {
        RvPrivateContext *c=&rv_session(&root)->context;
        c->input_fields=15;c->input_sequence=1;c->input[0]=0x25;c->input[1]=7;c->input[2]=2;c->input[3]=99;
        CHECK(invoke(3,0,0,&p)==RV_PASS&&p.status==RV_OK);
        CHECK(v->input.event==0x25&&v->input.activity==99&&v->input.valid_fields==15&&v->input.state==PV_UNKNOWN);
        CHECK(!(v->valid&PV_HAVE_REFRESH));
    }
    for(i=0;i<(PV_ENGINE==PV_LIFE?17u:12u);++i)capture_page(i);
    /* A synthetic renderer buffer exercises real list/text services only. */
    rv_session(&root)->context.ui_state_bytes=256;command(PV_PAGE,0);CHECK(draws>0);
    CHECK(invoke(8,0,0,&p)==RV_CLOSE_AND_PASS&&p.status==RV_OK&&root.ui_restore[6]==0);
    invariants();
}
static void failure_paths(void)
{
    RvReply p;uint32_t before,old_token;
    if(PV_ENGINE==PV_LIFE) {
        reset();load();free_refuse=1;
        CHECK(invoke(2,0,0,&p)==RV_FAULT);
        CHECK(state()->capacity[0].state==3&&state()->capacity[0].freed_mask==0&&capacity_attempts==1&&free_calls==1);
        CHECK(state()->capacity[0].free_detail[0]==0x101);
        reset();load();sample();old_token=state()->witness.token;before=free_calls;inspect_fail=1;
        CHECK(invoke(2,0,0,&p)==RV_FAULT&&state_reads_after_inspect_failure==0&&free_calls==before);
        CHECK(state()->witness.token==old_token&&allocation_witnesses==1);
        reset();load();sample();RV_BYTE(state()->witness.address+PV_WITNESS_BYTES/2)^=1;
        CHECK(invoke(2,0,0,&p)==RV_FAULT&&(state()->sticky&PV_DATA_BAD));
        reset();load();sample();read_error=1;before=closes;command(PV_READ_A,0);
        CHECK(state()->irom.state==PV_IROM_FAILED&&closes==before+1&&state()->irom.native_result==(uint32_t)-77);
        reset();load();sample();close_error=1;before=closes;command(PV_READ_A,0);
        CHECK(state()->irom.state==PV_IROM_FAILED&&closes==before+1);
    }
    reset();load();malformed_reply=1;CHECK(invoke(2,0,0,&p)==RV_FAULT);
    reset();load();sample();
    {
        RvSession *ss=rv_session(&root);uint32_t a=ss->context.state_address;
        ss->context.state_address=BASE;CHECK(invoke(2,0,0,&p)==RV_FAULT);
        ss->context.state_address=a;
    }
    reset();load();sample();before=free_calls;
    rv_notify(&root,16,0,0);CHECK(!rv_session(&root)&&free_calls==before);
    CHECK(!writes&&!rpc_calls&&!forbidden&&!stale_frees);
}
int main(int argc,char **argv)
{
    FILE *f;unsigned i;uint32_t data[12];char rows[16][13];GxrceView view;uint8_t changed;
    CHECK(argc==3);f=fopen(argv[1],"rb");CHECK(f);length=(uint32_t)fread(candidate,1,sizeof(candidate),f);CHECK(!ferror(f));CHECK(fclose(f)==0);
    CHECK(length>256&&length<=32768);
    CHECK(rv_validate(candidate,length,&rv_trust,&view)==GXRCE_OK);
    changed=candidate[80];candidate[80]^=1;CHECK(rv_validate(candidate,length,&rv_trust,&view)!=GXRCE_OK);candidate[80]=changed;
    changed=candidate[length-1];candidate[length-1]^=1;CHECK(rv_validate(candidate,length,&rv_trust,&view)!=GXRCE_OK);candidate[length-1]=changed;
    capture=fopen(argv[2],"w");CHECK(capture);
    CHECK(pv_crc32("123456789",9)==0xcbf43926u);
    for(i=0;i<12;++i)data[i]=0x10203040+i;
    pv_encode(2,7,73,3,PV_ENGINE,data,rows);for(i=0;i<16;++i)fprintf(capture,"%s\n",rows[i]);++rows_captures;
    for(unit_index=0;unit_index<3;++unit_index)success_path();
    unit_index=0;failure_paths();CHECK(fclose(capture)==0);
    printf("{\"engine\":%d,\"checks\":%u,\"service_calls\":%u,\"forbidden_calls\":%u,\"writes\":%u,\"rpc_calls\":%u,\"witness_bytes\":%u,\"captures\":%u,\"state_bytes\":%zu,\"capacity_memory_poisoned\":true,\"m32r_executed\":false,\"entries\":[",PV_ENGINE,checks,service_calls,forbidden,writes,rpc_calls,PV_WITNESS_BYTES,rows_captures,sizeof(PvState));
    for(i=0;i<10;++i)printf("%s%u",i?",":"",entries_called[i]);
    printf("],\"service_histogram\":[");
    for(i=0;i<17;++i){unsigned j;printf("%s[",i?",":"");for(j=0;j<13;++j)printf("%s%u",j?",":"",service_histogram[i][j]);printf("]");}
    printf("]}\n");
    __asan_unpoison_memory_region(memory,sizeof(memory));
    return 0;
}
