#include "probe.h"
#include "../resident_v34c/acceptance/containers/product/src/firmware/engine/panel/panel_store.h"
#include "../resident_v34c/acceptance/containers/product/src/firmware/card_container_v2/gxrce.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "local/trust.inc"

#define CHECK(x) do{++checks;if(!(x)){fprintf(stderr,"line %u: %s\n",__LINE__,#x);exit(91);}}while(0)
int32_t old_rv_native_seed(RvPrivateContext *);
static _Alignas(16) uint8_t memory[0x800000];
static RvRoot root;
RvRoot *rv_host_root=&root;
static uint32_t checks,psw,next_alloc,tick_value,write_calls,rename_calls,invokes,product_invokes;
static uint32_t n_base,probe_bytes,full_bytes,bx_fail,installed_generation,first_publishes,later_publishes;
static void *store_pointer;
static uint32_t store_base,store_bytes;
static uint8_t probe_raw[65536],full_raw[65536];
static uint8_t expected_headers[2][256];
static Gxr2Trust product_trust;
typedef struct {uint8_t bytes[65536];uint32_t n;int exists;} File;
static File files[5];
static const char *paths[5]={"/IROM/GXRCE0.DAT","/IROM/GXRCE1.DAT","/ATA1/GXRCE.DAT","/ATA1/GXRBX0.BIN","/ATA1/GXRBX1.BIN"};
static struct {int live,which,write;uint32_t at;} fds[8];
#include "local/native_model.h"
const uint8_t rv_skip_01[4]={0},rv_skip_02[4]={0},rv_skip_05[4]={0},rv_skip_06[4]={0},
    rv_skip_07[4]={0},rv_skip_08[4]={0},rv_close_07[4]={0};

void *rv_host_address(uint32_t a)
{
    if(a==RV_ROOT)return &root;
    if(n_base&&a>=n_base&&a-n_base<sizeof(P0State))return (uint8_t *)p0_host_state()+a-n_base;
    if(store_base&&a>=store_base&&a-store_base<store_bytes)return (uint8_t *)store_pointer+(a-store_base);
    CHECK(a>=0x20000000u&&a<0x20800000u);return memory+(a-0x20000000u);
}
uint32_t p0_host_address(const void *p)
{
    uintptr_t a=(uintptr_t)p,b=(uintptr_t)p0_host_state(),m=(uintptr_t)memory;
    if(a>=b&&a-b<sizeof(P0State)){CHECK(n_base);return n_base+(uint32_t)(a-b);}
    if(store_base&&a>=(uintptr_t)store_pointer&&a-(uintptr_t)store_pointer<store_bytes)return store_base+(uint32_t)(a-(uintptr_t)store_pointer);
    CHECK(a>=m&&a-m<sizeof(memory));return 0x20000000u+(uint32_t)(a-m);
}
uint32_t rv_irq_save(void){uint32_t old=psw;psw&=~0x40u;return old;}
void rv_irq_restore(uint32_t p){psw=p;}
void rv_cache_sync(void){}
uint32_t p0_irq_enabled(void){return psw&0x40u;}
uint32_t p0_tick(void){uint32_t t=tick_value;tick_value+=7;return t;}
void p0_empty(uint32_t *p,uint32_t n,const uint16_t *t,const uint32_t *c){(void)p;(void)n;(void)t;(void)c;}
void p0_decrement(uint32_t *p,uint32_t n,const uint16_t *t,const uint32_t *c)
{volatile uint32_t i=n;(void)p;(void)t;(void)c;while(i)--i;}
uint32_t rv_native_alloc(uint32_t n)
{
    uint32_t a=next_alloc,span=(n+12u+7u)&~7u;
    if(a+span>0x20744800u)return 0;
    next_alloc+=span;RV_WORD(a)=0;RV_BYTE(a+4)=1;RV_WORD(a+8)=span;return a+12;
}
void rv_native_free(uint32_t a){CHECK(RV_BYTE(a-8)==1);RV_BYTE(a-8)=0;}
int32_t rv_native_context(void){return 0;}
int32_t rv_native_language(void){return 0;}
int32_t rv_native_rpc_ready(void){return 1;}
int32_t rv_native_rpc_limit(void){return 512;}
uint32_t rv_native_unit(uint32_t x){(void)x;return 0;}
int32_t rv_native_ascii(const char *p,uint32_t n,void *out,uint32_t lang)
{CHECK(!lang&&n<=31);memcpy(out,p,n+1);return (int32_t)n;}
int32_t rv_native_layer(uint32_t a,uint32_t b,uint32_t c){CHECK(a==2&&b==1&&!c);return 0;}
int32_t rv_native_draw(uint32_t a,uint32_t b,uint32_t c){(void)a;(void)b;(void)c;return 0;}
int32_t rv_rpc8_native(uint32_t a,uint32_t b){(void)a;(void)b;CHECK(0);return -1;}
int32_t rv_native_preview(uint32_t a){(void)a;CHECK(0);return -1;}
int32_t rv_native_sd_id(void *p){const uint32_t id[4]={1,2,3,4};memcpy(p,id,16);return 0;}
static int open_file(int i,int writing)
{
    unsigned fd;for(fd=0;fd<8&&fds[fd].live;++fd){}CHECK(fd<8);
    fds[fd].live=1;fds[fd].which=i;fds[fd].write=writing;fds[fd].at=0;return 100+(int)fd;
}
int32_t rv_native_open(const char *p,uint32_t mode)
{
    unsigned i;CHECK(!mode);for(i=0;i<5&&strcmp(p,paths[i]);++i){}
    CHECK(i<5);return files[i].exists?open_file((int)i,0):-1;
}
int32_t rv_native_create(const char *p,uint32_t mode)
{
    unsigned i;CHECK(mode==2);
    for(i=3;i<5&&strcmp(p,paths[i]);++i){}CHECK(i<5);
    if(bx_fail)return -1;
    files[i].n=0;files[i].exists=1;return open_file((int)i,1);
}
int32_t rv_native_read(int32_t fd,void *p,uint32_t n)
{
    uint32_t take;unsigned i=(unsigned)(fd-100);File *f;
    CHECK(i<8&&fds[i].live&&!fds[i].write);f=&files[fds[i].which];
    take=f->n-fds[i].at;if(take>n)take=n;if(take>73)take=73;
    memcpy(p,f->bytes+fds[i].at,take);fds[i].at+=take;return (int32_t)take;
}
int32_t rv_native_write(int32_t fd,const void *p,uint32_t n)
{
    unsigned i=(unsigned)(fd-100);File *f;
    CHECK(i<8&&fds[i].live&&fds[i].write&&fds[i].which>=3);++write_calls;
    f=&files[fds[i].which];if(n>89)n=89;CHECK(fds[i].at+n<=4096);
    memcpy(f->bytes+fds[i].at,p,n);fds[i].at+=n;if(f->n<fds[i].at)f->n=fds[i].at;return (int32_t)n;
}
int32_t rv_native_close(int32_t fd){unsigned i=(unsigned)(fd-100);CHECK(i<8&&fds[i].live);fds[i].live=0;return 0;}
int32_t rv_native_rename(const char *a,const char *b){(void)a;(void)b;++rename_calls;CHECK(0);return -1;}
int32_t rv_native_delete(const char *a){(void)a;CHECK(0);return -1;}

int32_t rv_invoke(uint32_t entry,const RvApi *api,uint32_t token,const RvRequest *q,RvReply *r)
{
    RvSession *s=rv_session(&root);uint32_t off;CHECK(s&&!api);++invokes;off=entry-s->image_address;
    if(s->selected_source!=RV_SOURCE_CARD) {
        /* Product entries are doubles only for observing loader selection.
         * Full product runtime behavior is outside this test. */
        CHECK(rv_services_init(&s->context));
        if(!product_invokes++) {
            uint32_t *e=&s->entries.init;unsigned i;
            s->entries.version=1;s->entries.bytes=40;for(i=0;i<9;++i)e[i]=off;r->actual=40;
        }
        r->status=RV_OK;return RV_CONSUMED;
    }
    if(!n_base) {
        n_base=s->image_address+s->image_bytes+64;
        CHECK(n_base+sizeof(P0State)<=s->image_address+rv_image_span(s->image_bytes,s->bss_bytes)+2048);
    }
    switch(off) {
    case 256:return p0_bootstrap(api,token,q,r);
    case 272:return p0_init(api,token,q,r);
    case 288:return p0_menu(api,token,q,r);
    case 304:return p0_event(api,token,q,r);
    case 368:return p0_apply(api,token,q,r);
    case 320:case 336:case 352:case 384:case 400:return p0_close(api,token,q,r);
    default:CHECK(0);return RV_FAULT;
    }
}

static void seed_file(unsigned i,const uint8_t *p,uint32_t bytes)
{CHECK(bytes<=65536);memcpy(files[i].bytes,p,bytes);files[i].n=bytes;files[i].exists=1;}
static void reset(void)
{
    memset(memory,0,sizeof(memory));memset(&root,255,244);memcpy(root.pins,rv_pins,12);
    memset(files,0,sizeof(files));memset(fds,0,sizeof(fds));n_base=store_base=store_bytes=0;store_pointer=0;p0_host_reset();
    psw=0xc1;next_alloc=0x20704804;tick_value=1000;write_calls=rename_calls=invokes=product_invokes=bx_fail=0;
    RV_WORD(0x200d3488)=0x20704800;RV_WORD(0x200d348c)=0x20744800;RV_WORD(0x200c0dc4)=0x40000;
    native_seed_boot();
    RV_WORD(0x205d9bf8)=8;RV_WORD(0x205d9c00)=56;RV_BYTE(0x205a280f)=2;
    memcpy(RV_PTR(0x2040f81c),"jlaunch",8);RV_BYTE(0x2040f848)=1;RV_BYTE(0x2040f849)=0x51;RV_WORD(0x2040f804)=1;
    memset(RV_PTR(0x20500000),0xa7,4096);RV_WORD(0x200c0dac)=0x20500000;RV_WORD(0x200c0db0)=4096;
    seed_file(0,full_raw,full_bytes);seed_file(1,full_raw,full_bytes);seed_file(2,probe_raw,probe_bytes);
    memcpy(expected_headers[0],full_raw,256);memcpy(expected_headers[1],full_raw,256);
}
static uint32_t hook(unsigned which,uint32_t key,uint32_t caller,uint32_t keep)
{uint32_t frame[32]={0};frame[7]=key;frame[11]=keep;frame[16]=caller;rv_hook_observe(&root,which,frame);CHECK(psw==0xc1);return frame[1];}
static void enter(void)
{
    RvSession *s;P0State *n;RvUiSnapshot *ui;uint8_t private_before[256];
    uint32_t kind=RV_BYTE(0x2022f71c),table=RV_WORD(0x2022f720);
    CHECK(hook(1,0,0,0)==(uint32_t)(uintptr_t)rv_skip_01&&root.state==RV_READY);
    s=rv_session(&root);n=p0_host_state();ui=rv_ui_snapshot(&root);
    CHECK(s&&s->selected_source==RV_SOURCE_CARD&&s->capabilities==(RV_READ_CAPS|CAP_UI));
    CHECK(s->context.ui_state_capacity==256&&s->context.ui_state_bytes==236);
    CHECK(RV_BYTE(0x2022f71c)==kind&&RV_WORD(0x2022f720)==table);
    CHECK(RV_BYTE(s->context.ui_state_address)==5&&ui&&ui->state[0]==5);
    CHECK(s->rows==16&&root.ui_restore[0]==0x2022d610&&root.ui_restore[6]==s->list);
    CHECK(RV_WORD(0x2022f5a8)==s->list&&RV_BYTE(0x2022f5ac)==16);
    CHECK(!memcmp(ui->glyphs[0],n->rows[0],strlen(n->rows[0])+1));
    CHECK(n->phase!=P0_NEW&&n->reference_start);
    if(kind!=5){
        memcpy(private_before,RV_PTR(s->context.ui_state_address),256);
        CHECK(old_rv_native_seed(&s->context)==RV_UNAVAILABLE);
        CHECK(!memcmp(private_before,RV_PTR(s->context.ui_state_address),256));++first_publishes;
    }else ++later_publishes;
    CHECK(hook(2,0,0,0)==(uint32_t)(uintptr_t)rv_skip_02);
    native_finish_constructor(s->cursor+1);
    CHECK(RV_WORD(0x2022f5a8)==s->list&&RV_BYTE(0x2022f5ac)==16);
}
static void unchanged(void)
{
    uint32_t i;CHECK(!rename_calls);
    for(i=0;i<2;++i)CHECK(files[i].n==full_bytes&&!memcmp(files[i].bytes,expected_headers[i],256)&&!memcmp(files[i].bytes+256,full_raw+256,full_bytes-256));
    CHECK(!root.grain);for(i=0;i<4096;++i)CHECK(RV_BYTE(0x20500000+i)==0xa7);
    for(i=0;i<8;++i)CHECK(!fds[i].live);
}
static void calibrate(void)
{
    CHECK(p0_host_state()->phase==P0_REFERENCE);tick_value=p0_host_state()->reference_start+10000;
    hook(7,0x23,0x202c2d84,0);
    CHECK(p0_host_state()->phase==P0_BENCH&&p0_host_state()->reference_delta==10000);
    CHECK(!root.ui_restore[0]);enter();
}
static void admit_all(void)
{
    unsigned i;P0State *n=p0_host_state();
    for(i=0;i<P0_ADMISSION_STEPS;++i){
        hook(8,0,0,1);CHECK(n->admitted==i+1&&!n->used&&!n->error);
    }
}
static void fix(uint8_t *p,uint32_t n)
{rv_put32(p+24,gxrce_crc32(p+256,n-256));rv_put32(p+20,0);rv_put32(p+20,gxrce_crc32(p,256));}

static void envelope(void)
{
    uint8_t changed[65536];GxrceView v;unsigned i;
    CHECK(rv_validate(probe_raw,probe_bytes,&rv_trust,&v)==GXRCE_OK);
    CHECK(v.build_number==1&&v.bss_bytes>0&&!memcmp(probe_raw+228,"LUTP0001",8));
    for(i=0;i<3;++i){unsigned off=i==0?48:i==1?80:212;memcpy(changed,probe_raw,probe_bytes);changed[off]^=1;fix(changed,probe_bytes);
        CHECK(rv_validate(changed,probe_bytes,&rv_trust,&v)==(i==0?GXRCE_BODY_ID:GXRCE_RESIDENT_ID));}
    memcpy(changed,probe_raw,probe_bytes);memcpy(changed+48,p0_running_body,32);fix(changed,probe_bytes);
    CHECK(rv_validate(changed,probe_bytes,&rv_trust,&v)==GXRCE_BODY_ID);
    memcpy(changed,probe_raw,probe_bytes);changed[400]^=1;CHECK(rv_validate(changed,probe_bytes,&rv_trust,&v)==GXRCE_CRC);
    CHECK(rv_validate(probe_raw,probe_bytes-1,&rv_trust,&v)==GXRCE_LENGTH);
}

static int32_t verify_envelope(void *unused,const PsObject *o,const uint8_t *p,uint32_t n,PsInfo *info)
{
    GxrceView v;(void)unused;CHECK(o->kind==PS_ENGINE);
    if(rv_validate(p,n,&rv_trust,&v))return RV_VERIFY;
    info->generation=v.build_number;info->bytes=n;info->crc32=gxrce_crc32(p,n);return RV_OK;
}
static uint32_t port_address(void *unused,const void *p,uint32_t n)
{(void)unused;(void)n;return p0_host_address(p);}
static int32_t verify_product(void *unused,const PsObject *o,const uint8_t *p,uint32_t n,PsInfo *info)
{
    Gxr2View v;(void)unused;CHECK(o->kind==PS_ENGINE);
    if(gxr2_gate_validate(p,n,&product_trust,&product_trust.modules[0].unit,0,&v)!=GXR2_OK)return RV_VERIFY;
    info->generation=v.build_number;info->bytes=n;info->crc32=gxrce_crc32(p,n);return RV_OK;
}
static void install_rejection(uint32_t generation,int product_gate)
{
    RvSession *s;RvLease *lease;PnPort port;PsStore store;PsInstallResult result;
    uint32_t a,i;reset();enter();s=rv_session(&root);
    for(i=0;i<2;++i){rv_put32(files[i].bytes+28,generation);fix(files[i].bytes,full_bytes);memcpy(expected_headers[i],files[i].bytes,256);}
    a=rv_native_alloc(65536);CHECK(a);lease=&s->leases[1];*lease=(RvLease){99,~99u,a,65536,4};
    store_base=rv_native_alloc(sizeof(store));store_bytes=sizeof(store);store_pointer=&store;CHECK(store_base);
    s->leases[2]=(RvLease){100,~100u,store_base,store_bytes,4};
    memset(&port,0,sizeof(port));port.api=rv_services_init(&s->context);port.context=root.lease;port.io_lease=root.lease;
    port.address=port_address;for(i=0;i<6;++i)port.epochs[i]=root.epoch[i];
    ps_init(&store,&port,RV_PTR(a),65536,product_gate?verify_product:verify_envelope,0);
    /* Weaken verification to envelope-only to reach the actual downgrade
     * comparison. The real product's semantic gate rejects P0 earlier. */
    root.inflight=1;CHECK(ps_install(&store,probe_raw,probe_bytes,&result)==(product_gate?RV_VERIFY:RV_CONFLICT));root.inflight=0;
    CHECK(!result.installed&&!result.delivered&&!write_calls);unchanged();
}

static uint32_t read_file(const char *name,uint8_t *out)
{FILE *f=fopen(name,"rb");size_t n;CHECK(f);n=fread(out,1,65536,f);CHECK(!ferror(f)&&!fclose(f));return (uint32_t)n;}

static void seed_regressions(void)
{
    unsigned i;RvSession *s;uint8_t before[256],native[32];uint32_t saved_table;
    for(i=0;i<3;++i){static const unsigned kinds[]={0,4,9};reset();native_kind(kinds[i]);enter();unchanged();}
    reset();enter();s=rv_session(&root);saved_table=RV_WORD(0x2022f720);native_kind(0);
    memcpy(before,RV_PTR(s->context.ui_state_address),256);memcpy(native,RV_PTR(0x2022f71c),32);
    s->context.ui_state_capacity=235;CHECK(rv_native_seed(&s->context)==RV_UNAVAILABLE);
    s->context.ui_state_capacity=256;RV_WORD(0x2022f720)=0x2022f000;
    CHECK(rv_native_seed(&s->context)==RV_UNAVAILABLE);RV_WORD(0x2022f720)=0;
    CHECK(rv_native_seed(&s->context)==RV_UNAVAILABLE);RV_WORD(0x2022f720)=saved_table;
    CHECK(!memcmp(before,RV_PTR(s->context.ui_state_address),256)&&!memcmp(native,RV_PTR(0x2022f71c),32));
    CHECK(rv_native_seed(&s->context)==RV_OK&&!memcmp(native,RV_PTR(0x2022f71c),32));unchanged();
    /* Historical r1 hand-seeded state: compatibility regression only. */
    reset();RV_BYTE(0x2022f71c)=5;RV_WORD(0x2022f720)=0x2022f000;
    RV_BYTE(0x2022f725)=RV_BYTE(0x2022f726)=1;RV_WORD(RV_NATIVE_VIEWS+4)=0x2022f71c;
    enter();CHECK(old_rv_native_seed(&rv_session(&root)->context)==RV_OK);unchanged();
}

int main(int argc,char **argv)
{
    unsigned i,j;RvSession *s;P0State *n;uint32_t before;Gxr2View view;CHECK(argc==4);
    probe_bytes=read_file(argv[1],probe_raw);full_bytes=read_file(argv[2],full_raw);installed_generation=rv_be32(full_raw+28);
    CHECK(installed_generation==113||installed_generation==114);
    memset(&product_trust,0,sizeof(product_trust));memcpy(product_trust.body_sha256,rv_trust.body,32);
    memcpy(product_trust.resident_build_id,rv_trust.build,32);memcpy(product_trust.resident_abi_id,rv_trust.abi,16);
    for(i=0;i<3;++i){static const char names[3][8]={"jlaunch","qlaunch","l08firm"};
        memcpy(product_trust.modules[i].unit.name,names[i],8);product_trust.modules[i].unit.main_version=0x151;
        product_trust.modules[i].stock_crc32=rv_pins[i];}
    CHECK(gxr2_gate_validate(full_raw,full_bytes,&product_trust,&product_trust.modules[0].unit,0,&view)==GXR2_OK);
    CHECK(gxr2_gate_validate(probe_raw,probe_bytes,&product_trust,&product_trust.modules[0].unit,0,&view)==GXR2_VERSION);
    envelope();seed_regressions();install_rejection(installed_generation,1);
    install_rejection(113,0);install_rejection(114,0);install_rejection(115,0);install_rejection(0xffffffffu,0);
    reset();enter();calibrate();admit_all();n=p0_host_state();
    for(i=0;i<P0_SAMPLES;++i){RV_BYTE(0x2022f726)=(i&15)+1;hook(8,0,0,1);CHECK(n->used==i+1);CHECK(!n->error);}
    CHECK(n->phase==P0_DONE&&n->flush_ok==1);
    for(i=0;i<6;++i)for(j=0;j<4;++j){unsigned mask=0,k;
        for(k=0;k<3;++k)mask|=1u<<(n->samples[i*12+j*3+k].kind&255);CHECK(mask==7);}
    for(i=3;i<5;++i)if(files[i].exists&&files[i].n==4096&&rv_be32(files[i].bytes+2432+20)==72){
        FILE *f=fopen(argv[3],"wb");CHECK(f);CHECK(fwrite(files[i].bytes,1,4096,f)==4096&&!fclose(f));break;}
    CHECK(i<5);before=n->used;hook(8,0,0,1);CHECK(n->used==before);unchanged();
    CHECK(hook(7,0x29,0x202bd890,0)==(uint32_t)(uintptr_t)rv_close_07);
    CHECK(!root.ui_restore[0]&&RV_BYTE(0x2022f5ac)==7&&RV_WORD(0x2022f5a8)==0x2022d610);unchanged();
    enter();CHECK(n->used==72&&n->phase==P0_DONE);
    hook(7,0x23,0x202c2d74,1);CHECK(!root.ui_restore[0]);unchanged();
    /* Remove DAT: select the exact real gen113 or gen114 installed artifact. */
    reset();files[2].exists=0;rv_reset(&root);CHECK(rv_load(&root,&rv_trust)==RV_OK);
    s=rv_session(&root);CHECK(s&&s->selected_source==RV_SOURCE_A&&s->generation==installed_generation);
    CHECK(s->crc==gxrce_crc32(full_raw,full_bytes)&&!write_calls);unchanged();
    reset();files[2].exists=files[0].exists=0;rv_reset(&root);CHECK(rv_load(&root,&rv_trust)==RV_OK);
    CHECK(rv_session(&root)->selected_source==RV_SOURCE_B&&rv_session(&root)->generation==installed_generation);unchanged();
    reset();files[2].bytes[80]^=1;fix(files[2].bytes,files[2].n);rv_reset(&root);
    CHECK(rv_load(&root,&rv_trust)==RV_OK&&rv_session(&root)->selected_source==RV_SOURCE_A);
    CHECK(root.flags&RF_QUARANTINE);unchanged();
    reset();enter();tick_value=p0_host_state()->reference_start-4u;hook(7,0x23,0x202c2d84,0);
    CHECK(p0_host_state()->phase==P0_ERROR&&p0_host_state()->error==5);unchanged();
    reset();tick_value=0xfffff000u;enter();calibrate();CHECK(p0_host_state()->reference_delta==10000);unchanged();
    reset();enter();bx_fail=1;calibrate();CHECK(!p0_host_state()->flush_ok);unchanged();
    printf("PASS host installed=%u assertions=%u first_entry_non5=%u later_type5=%u table=2022F56C capacity=256 native_view_count=1 samples=72 MENU_exit=1 old_seed_rejected=1 legacy_hand_seed=regression loader_fallback=A/B downgrade=CONFLICT no_product_writes=1 IRQ_restored=1\n",installed_generation,checks,first_publishes,later_publishes);
    return 0;
}
