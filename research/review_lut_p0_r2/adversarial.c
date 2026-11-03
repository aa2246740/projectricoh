#define main baseline_main
#define hook base_hook
#define rv_native_alloc base_alloc
#define rv_native_ascii base_ascii
#define p0_tick base_tick
#define rv_native_create base_create
#define rv_native_write base_write
#include "../../firmware/lut_p0_timing/host_checks.c"
#undef main
#undef hook
#undef rv_native_alloc
#undef rv_native_ascii
#undef p0_tick
#undef rv_native_create
#undef rv_native_write

void trace_config(void *, uint32_t *);
void trace_begin(unsigned);
void trace_end(void);
void trace_summary(void);
void p0_actual_kernel(uint32_t *,uint32_t,const uint16_t *,const uint32_t *);
static unsigned fail_alloc, fail_ascii, ascii_calls, tick_step=7;
static unsigned case_number, callback_kernel_calls, callback_pairs, timer_open;
static unsigned observed_admissions[4], observed_admission_count;
static unsigned counted_callbacks, io_calls, interrupted_runs, resumed_runs;
static uint32_t native_before[6];
static const char *out_dir;

uint32_t rv_native_alloc(uint32_t n)
{if(n==sizeof(RvUiSnapshot)&&fail_alloc){--fail_alloc;return 0;}return base_alloc(n);}
int32_t rv_native_ascii(const char *p,uint32_t n,void *q,uint32_t lang)
{
    CHECK(!timer_open);++ascii_calls;
    if(fail_ascii&&ascii_calls==fail_ascii){memset(q,0x7f,70);return -1;}
    return base_ascii(p,n,q,lang);
}
uint32_t p0_tick(void)
{
    uint32_t t=tick_value;
    if(p0_host_state()->phase==P0_BENCH)timer_open=!timer_open;
    tick_value+=tick_step;return t;
}
int32_t rv_native_create(const char *p,uint32_t mode)
{CHECK(!timer_open);++io_calls;return base_create(p,mode);}
int32_t rv_native_write(int32_t fd,const void *p,uint32_t n)
{CHECK(!timer_open);++io_calls;return base_write(fd,p,n);}
void p0_kernel(uint32_t *p,uint32_t count,const uint16_t *t,const uint32_t *c)
{
    P0State *n=p0_host_state();++callback_kernel_calls;callback_pairs+=count;
    if(n->phase==P0_BENCH&&n->admitted<4){
        CHECK(observed_admission_count<4);
        observed_admissions[observed_admission_count++]=count;
    }
    p0_actual_kernel(p,count,t,c);
}
static uint32_t hook(unsigned h,uint32_t key,uint32_t caller,uint32_t keep)
{
    uint32_t result;callback_kernel_calls=callback_pairs=timer_open=0;
    trace_begin(case_number);result=base_hook(h,key,caller,keep);trace_end();
    CHECK(!timer_open&&callback_kernel_calls<=2&&callback_pairs<=8192);
    if(h==8)++counted_callbacks;return result;
}
static void remember(void)
{
    native_before[0]=RV_BYTE(0x2022f725);native_before[1]=RV_BYTE(0x2022f726);
    native_before[2]=RV_WORD(0x2022f5a8);native_before[3]=RV_BYTE(0x2022f5ac);
    native_before[4]=RV_WORD(RV_NATIVE_VIEWS+4);native_before[5]=RV_WORD(RV_NATIVE_VIEWS+12);
}
static void restored(void)
{
    CHECK(RV_BYTE(0x2022f725)==native_before[0]&&RV_BYTE(0x2022f726)==native_before[1]);
    CHECK(RV_WORD(0x2022f5a8)==native_before[2]&&RV_BYTE(0x2022f5ac)==native_before[3]);
    CHECK(RV_WORD(RV_NATIVE_VIEWS+4)==native_before[4]&&RV_WORD(RV_NATIVE_VIEWS+12)==native_before[5]);
    CHECK(!root.ui_restore[0]);unchanged();
}
static void begin(void)
{
    ++case_number;reset();fail_alloc=fail_ascii=ascii_calls=0;tick_step=7;
    observed_admission_count=timer_open=0;
    RV_BYTE(0x2022f725)=2;RV_BYTE(0x2022f726)=6;remember();
}
static void open_page(void)
{
    /* Native construction writes are separate from P0, as in the real order. */
    if(!root.ui_restore[0])remember();
    CHECK(hook(1,0,0,0)==(uint32_t)(uintptr_t)rv_skip_01);
    CHECK(hook(2,0,0,0)==(uint32_t)(uintptr_t)rv_skip_02);
    native_finish_constructor(rv_session(&root)->cursor+1);
    native_before[4]=RV_WORD(RV_NATIVE_VIEWS+4);native_before[5]=RV_WORD(RV_NATIVE_VIEWS+12);
}
static void confirm(unsigned caller,unsigned keep)
{hook(7,0x23,caller,keep);restored();}
static void reference_ok(void)
{
    tick_value=p0_host_state()->reference_start+10000;
    confirm(0x202c2d84,0);
    CHECK(p0_host_state()->phase==P0_BENCH&&p0_host_state()->reference_delta==10000);
}
static void menu(void)
{hook(7,0x29,0x202bd890,0);restored();}
static void advance(unsigned count)
{unsigned i;for(i=0;i<count;++i)hook(8,0,0,1);}
static void all_admissions(void)
{
    static const unsigned expected[]={4,64,512,4096};unsigned i;
    advance(4);CHECK(p0_host_state()->admitted==4&&!p0_host_state()->error);
    CHECK(observed_admission_count==4);
    for(i=0;i<4;++i)CHECK(observed_admissions[i]==expected[i]);
}
static void finish(void)
{
    P0State *n=p0_host_state();
    if(!root.ui_restore[0])open_page();
    while(n->admitted<4){unsigned old=n->admitted;advance(1);CHECK(n->admitted==old+1&&!n->used&&!n->error);}
    while(n->used<72){unsigned old=n->used;advance(1);CHECK(n->used==old+1&&!n->error);}
    CHECK(n->phase==P0_DONE&&n->flush_ok==1);menu();
}
static unsigned latest(void)
{
    unsigned i,result=5;uint32_t gen=0;
    for(i=3;i<5;++i)if(files[i].exists&&files[i].n==4096&&rv_be32(files[i].bytes+16)>gen){result=i;gen=rv_be32(files[i].bytes+16);}
    CHECK(result<5);return result;
}
static void save_log(const char *name)
{
    char path[2048];unsigned i=latest();FILE *f;
    CHECK(snprintf(path,sizeof(path),"%s/%s.BIN",out_dir,name)>0);f=fopen(path,"wb");CHECK(f);
    CHECK(fwrite(files[i].bytes,1,4096,f)==4096&&!fclose(f));
}
static void setup_phase(unsigned p)
{
    begin();open_page();
    if(p==0)return;reference_ok();open_page();
    if(p<=5){advance(p-1);return;}
    all_admissions();
    if(p==6)advance(1);else if(p==7)advance(37);else if(p==8)advance(72);
    else{tick_step=0x80000000u;advance(1);tick_step=7;CHECK(p0_host_state()->phase==P0_ERROR);}
}
static void poison_stays_invalid(void)
{
    P0State *n=p0_host_state();
    CHECK(n->reference_flags&P0_REF_INTERRUPTED);
    open_page();tick_value=n->reference_start+10000;confirm(0x202c2d84,0);
    open_page();advance(80);menu();
    CHECK(n->phase==P0_ERROR&&n->error==7&&!n->used);++interrupted_runs;
}
static void previous_cases(void)
{
    unsigned retries,j,row;P0State *n;
    for(retries=1;retries<=3;++retries){
        begin();fail_alloc=retries;
        for(j=0;j<retries;++j){CHECK(!hook(1,0,0,0));n=p0_host_state();restored();
            CHECK(n->phase==P0_NEW&&!n->reference_start&&!n->reference_flags);
            confirm(0x202c2d84,0);native_finish_constructor(1);remember();}
        tick_value=100000;open_page();CHECK(n->reference_start==100000);
        reference_ok();finish();if(retries==1)save_log("first-publish-retry");
    }
    for(row=1;row<=16;++row){
        begin();fail_ascii=row;CHECK(!hook(1,0,0,0));restored();
        CHECK(p0_host_state()->phase==P0_NEW&&!p0_host_state()->reference_start);
        fail_ascii=0;tick_value=100000;open_page();reference_ok();finish();
    }
    begin();open_page();n=p0_host_state();menu();
    CHECK(!n->reference_start&&!n->reference_end&&!n->reference_delta);
    tick_value=61000;open_page();tick_value=71000;confirm(0x202c2d84,0);
    CHECK(n->reference_delta==10000&&n->error==7&&n->phase==P0_ERROR);
    open_page();advance(80);menu();save_log("reference-reopen");
    printf("PASS previous cases; first UI failures=1..3; first glyph failures=1..16\n");
}
static void exit_matrix(void)
{
    unsigned p,exit_kind,caller,keep;P0State *n;
    for(p=0;p<10;++p)for(exit_kind=0;exit_kind<3;++exit_kind){
        setup_phase(p);n=p0_host_state();
        if(exit_kind==0)menu();
        else if(exit_kind==1){hook(6,0,0,1);restored();}
        else{fail_ascii=ascii_calls+1;hook(8,0,0,1);restored();fail_ascii=0;}
        if(p==0){poison_stays_invalid();if(!exit_kind)save_log("menu-reference");}
        else if(exit_kind<2&&p<9){finish();++resumed_runs;}
        else{open_page();advance(80);menu();CHECK(n->phase==P0_ERROR&&n->error&&n->flush_ok);}
    }
    for(p=0;p<10;++p)for(caller=0;caller<2;++caller)for(keep=0;keep<2;++keep){
        setup_phase(p);n=p0_host_state();
        if(!p)tick_value=n->reference_start+10000;
        confirm(caller?0x202c2d74:0x202c2d84,keep);
        if(p<9){finish();++resumed_runs;}else CHECK(n->phase==P0_ERROR);
    }
    for(p=0;p<10;++p){
        setup_phase(p);n=p0_host_state();hook(1,0,0,0);
        if(!p){CHECK(n->error==7);menu();poison_stays_invalid();save_log("h01-reference-retry");}
        else if(p<9){finish();++resumed_runs;}else{menu();CHECK(n->phase==P0_ERROR);}
    }
    printf("PASS MENU/H06/publish failures and H01 retries at REF, admission0..4, sample1/37, DONE, ERROR; OK caller74/84 keep0/1\n");
}
static void admission_limits(void)
{
    unsigned p;P0State *n;
    for(p=0;p<4;++p){
        begin();open_page();reference_ok();open_page();advance(p);n=p0_host_state();
        tick_step=n->admission_budget+1;advance(1);tick_step=7;
        CHECK(n->phase==P0_ERROR&&n->error==9&&n->admitted==p&&!n->used);
        advance(80);CHECK(!callback_kernel_calls&&observed_admission_count==p+1);
        menu();save_log(p==0?"over-budget0":p==1?"over-budget1":p==2?"over-budget2":"over-budget3");
    }
    begin();open_page();reference_ok();open_page();n=p0_host_state();tick_step=n->admission_budget;
    all_admissions();tick_step=7;finish();
    begin();tick_value=0;CHECK(!hook(1,0,0,0));restored();
    CHECK(p0_host_state()->phase==P0_ERROR&&p0_host_state()->error==5);
    printf("PASS admission exact boundary and each over-budget stop; callback max=8192 pairs\n");
}
static void power_cycle(void)
{
    static File persisted[2];P0State *n;uint32_t old;unsigned i;
    begin();open_page();n=p0_host_state();old=n->reference_start;
    CHECK(!files[3].exists&&!files[4].exists);reset();remember();
    tick_value=50000;open_page();n=p0_host_state();CHECK(n->reference_start!=old&&n->reference_start==50000&&!n->error);
    reference_ok();finish();save_log("power-cycle-new-reference");
    for(i=0;i<2;++i)persisted[i]=files[3+i];
    reset();for(i=0;i<2;++i)files[3+i]=persisted[i];remember();
    open_page();CHECK(p0_host_state()->phase==P0_REFERENCE);save_log("power-loss-during-new-reference-old-slot");
    reset();for(i=0;i<2;++i)files[3+i]=persisted[i];remember();
    open_page();menu();save_log("power-restart-menu-invalid");
    printf("OBS power loss before reference confirm writes no new slot; earlier completed slot survives\n");
}
static void cursor_variants(void)
{
    unsigned a,b;uint32_t x,y;
    for(a=1;a<=7;++a)for(b=1;b<=7;++b){
        begin();RV_BYTE(0x2022f725)=a;RV_BYTE(0x2022f726)=b;remember();open_page();menu();
    }
    for(a=0;a<4;++a){static const unsigned values[]={0,8,16,255};
        begin();x=values[a];y=values[3-a];RV_BYTE(0x2022f725)=x;RV_BYTE(0x2022f726)=y;remember();
        open_page();hook(7,0x29,0x202bd890,0);
        printf("OBS cursor input=%u/%u restore=%u/%u clamp_exact=%u\n",x,y,
               RV_BYTE(0x2022f725),RV_BYTE(0x2022f726),
               RV_BYTE(0x2022f725)==x&&RV_BYTE(0x2022f726)==y);
        unchanged();
    }
    printf("PASS native cursor 1..7 x 1..7 exact restore\n");
}
static void tag33_restore(void)
{
    unsigned p,k;P0State *n;RvSession *s;
    for(p=0;p<10;++p){
        RvUiView v={0};RvReply reply;RvRequest q;
        setup_phase(p);n=p0_host_state();s=rv_session(&root);q=n->request;
        v.header=(RvBufferHeader){1,sizeof(v),0};v.part=2;v.tag=33;
        v.state_address=s->context.ui_state_address;v.state_bytes=s->context.ui_state_bytes;
        v.lease_token=s->context.state_lease;v.expected_array=RV_NATIVE_VIEWS;
        v.expected_count=1;v.expected_top_tag=33;v.expected_top_state=0x2022f71c;
        memcpy(n->wire.bytes,&v,sizeof(v));for(k=8;k<14;++k)q.args[k]=0;
        q.args[1]=s->context.state_lease;q.args[10]=p0_host_address(n->wire.bytes);q.args[11]=sizeof(v);
        root.inflight=1;trace_begin(case_number);CHECK(n->api->call(RV_UI_VIEW,1,&q,&reply)==RV_OK);
        trace_end();root.inflight=0;CHECK(RV_WORD(RV_NATIVE_VIEWS+4)==root.ui_block);menu();
    }
    printf("PASS actual UI_VIEW snapshot tag33 state restoration at all ten phases\n");
}
int main(int argc,char **argv)
{
    CHECK(argc==4||argc==5);probe_bytes=read_file(argv[1],probe_raw);full_bytes=read_file(argv[2],full_raw);
    installed_generation=rv_be32(full_raw+28);out_dir=argv[3];trace_config(memory,&next_alloc);
    if(argc==5){begin();trace_begin(case_number);RV_WORD(0x2037f3bc)=0;trace_end();return 0;}
    previous_cases();exit_matrix();admission_limits();power_cycle();cursor_variants();tag33_restore();trace_summary();
    printf("PASS independent installed=%u scenarios=%u callbacks=%u interrupted=%u resumed=%u io_calls=%u assertions=%u\n",
           installed_generation,case_number,counted_callbacks,interrupted_runs,resumed_runs,io_calls,checks);return 0;
}
