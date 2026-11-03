#define main candidate_original_main
#define hook untraced_hook
#define rv_native_alloc candidate_host_alloc
#define rv_native_ascii candidate_ascii
#define p0_tick candidate_tick
#include "host_checks.c"
#undef main
#undef hook
#undef rv_native_alloc
#undef rv_native_ascii
#undef p0_tick

void p0_trace_configure(void *,uint32_t *,unsigned,unsigned,unsigned);
void p0_trace_begin(const char *);
void p0_trace_end(void);
void p0_trace_summary(void);
void p0_actual_kernel(uint32_t *,uint32_t,const uint16_t *,const uint32_t *);
static const char *test_case;
static unsigned fail_ui_once,fail_text_once,kernel_calls,kernel_pairs,tick_step=7;
static uint32_t native_fields[6],admission_counts[4],admission_calls;

uint32_t rv_native_alloc(uint32_t bytes)
{if(fail_ui_once&&bytes==sizeof(RvUiSnapshot)){fail_ui_once=0;return 0;}return candidate_host_alloc(bytes);}
int32_t rv_native_ascii(const char *p,uint32_t n,void *out,uint32_t language)
{if(fail_text_once){fail_text_once=0;memset(out,0x7f,70);return -1;}return candidate_ascii(p,n,out,language);}
uint32_t p0_tick(void){uint32_t t=tick_value;tick_value+=tick_step;return t;}
void p0_kernel(uint32_t *p,uint32_t count,const uint16_t *table,const uint32_t *coord)
{
    P0State *n=p0_host_state();++kernel_calls;kernel_pairs+=count;
    if(n->phase==P0_BENCH&&n->admitted<4){CHECK(admission_calls<4);admission_counts[admission_calls++]=count;}
    p0_actual_kernel(p,count,table,coord);
}

static uint32_t hook(unsigned which,uint32_t key,uint32_t caller,uint32_t keep)
{
    uint32_t result;kernel_calls=kernel_pairs=0;
    p0_trace_begin(test_case);result=untraced_hook(which,key,caller,keep);p0_trace_end();
    CHECK(kernel_calls<=2&&kernel_pairs<=8192);return result;
}
static void begin(const char *name)
{
    test_case=name;reset();fail_ui_once=fail_text_once=admission_calls=0;tick_step=7;
    RV_BYTE(0x2022f725)=2;RV_BYTE(0x2022f726)=6;
    native_fields[0]=RV_BYTE(0x2022f725);native_fields[1]=RV_BYTE(0x2022f726);
    native_fields[2]=RV_WORD(0x2022f5a8);native_fields[3]=RV_BYTE(0x2022f5ac);
    native_fields[4]=RV_WORD(RV_NATIVE_VIEWS+4);native_fields[5]=RV_WORD(RV_NATIVE_VIEWS+12);
}
static void restored(void)
{
    if(RV_BYTE(0x2022f725)!=native_fields[0]||RV_BYTE(0x2022f726)!=native_fields[1])
        fprintf(stderr,"restore mismatch case=%s phase=%u actual=%u/%u expected=%u/%u\n",test_case,
                p0_host_state()->phase,RV_BYTE(0x2022f725),RV_BYTE(0x2022f726),native_fields[0],native_fields[1]);
    CHECK(RV_BYTE(0x2022f725)==native_fields[0]&&RV_BYTE(0x2022f726)==native_fields[1]);
    CHECK(RV_WORD(0x2022f5a8)==native_fields[2]&&RV_BYTE(0x2022f5ac)==native_fields[3]);
    CHECK(RV_WORD(RV_NATIVE_VIEWS+4)==native_fields[4]&&RV_WORD(RV_NATIVE_VIEWS+12)==native_fields[5]);
    CHECK(!root.ui_restore[0]);unchanged();
}
static void open_page(void)
{
    /* A failed H01 may be followed by the official constructor before retry.
     * Capture the native values at this publication, not before that writer. */
    CHECK(root.magic!=RV_ROOT_MAGIC||!root.ui_restore[0]);
    native_fields[0]=RV_BYTE(0x2022f725);native_fields[1]=RV_BYTE(0x2022f726);
    native_fields[2]=RV_WORD(0x2022f5a8);native_fields[3]=RV_BYTE(0x2022f5ac);
    CHECK(hook(1,0,0,0)==(uint32_t)(uintptr_t)rv_skip_01);
    CHECK(hook(2,0,0,0)==(uint32_t)(uintptr_t)rv_skip_02);
    /* The official native continuation is not a P0 write. */
    native_finish_constructor(rv_session(&root)->cursor+1);
    native_fields[4]=RV_WORD(RV_NATIVE_VIEWS+4);native_fields[5]=RV_WORD(RV_NATIVE_VIEWS+12);
}
static void menu_exit(void)
{CHECK(hook(7,0x29,0x202bd890,0)==(uint32_t)(uintptr_t)rv_close_07);restored();}
static void reference_ok(void)
{
    tick_value=p0_host_state()->reference_start+10000;
    CHECK(hook(7,0x23,0x202c2d84,0)==(uint32_t)(uintptr_t)rv_close_07);
    CHECK(p0_host_state()->phase==P0_BENCH&&p0_host_state()->reference_delta==10000);restored();
}
static void admission(void)
{
    unsigned i;P0State *n=p0_host_state();
    for(i=0;i<4;++i){hook(8,0,0,1);CHECK(n->admitted==i+1&&!n->used&&!n->error);}
    CHECK(admission_calls==4&&admission_counts[0]==4&&admission_counts[1]==64&&admission_counts[2]==512&&admission_counts[3]==4096);
}
static void finish(void)
{
    unsigned i;P0State *n=p0_host_state();open_page();admission();
    for(i=0;i<72;++i){hook(8,0,0,1);CHECK(n->used==i+1&&!n->error);}
    CHECK(n->phase==P0_DONE&&n->flush_ok);menu_exit();
}
static void save_log(const char *directory,const char *name)
{
    char path[2048];unsigned i,latest=5;uint32_t generation=0;
    for(i=3;i<5;++i)if(files[i].exists&&files[i].n==4096&&rv_be32(files[i].bytes+16)>generation){latest=i;generation=rv_be32(files[i].bytes+16);}
    CHECK(latest<5);CHECK(snprintf(path,sizeof(path),"%s/%s.BIN",directory,name)>0);
    {FILE *f=fopen(path,"wb");CHECK(f);CHECK(fwrite(files[latest].bytes,1,4096,f)==4096&&!fclose(f));}
}

static void adversarial(const char *out)
{
    P0State *n;uint32_t old;unsigned i;
    begin("first-publish-retry");fail_ui_once=1;
    CHECK(!hook(1,0,0,0));n=p0_host_state();
    CHECK(root.state==RV_READY&&n->phase==P0_NEW&&!n->reference_start&&!n->reference_flags);restored();
    hook(7,0x23,0x202c2d84,0);CHECK(n->phase==P0_NEW&&!n->reference_start);
    hook(7,0x29,0x202bd890,0);restored();
    native_finish_constructor(1);tick_value=100000;open_page();
    CHECK(n->phase==P0_REFERENCE&&n->reference_start==100000);
    reference_ok();finish();save_log(out,test_case);
    printf("PASS first-publish-retry start=100000 end=110000 delta=10000 valid_reference=1\n");

    begin("reference-reopen");open_page();n=p0_host_state();old=n->reference_start;menu_exit();
    CHECK(n->phase==P0_NEW&&!n->reference_start&&!n->reference_delta&&n->reference_flags==P0_REF_INTERRUPTED);
    save_log(out,"reference-interrupted");tick_value=old+60000;open_page();
    CHECK(n->reference_start==old+60000&&!strncmp(n->rows[0],"P0 REF RESTART",14));
    tick_value=old+70000;hook(7,0x23,0x202c2d84,0);restored();
    CHECK(n->phase==P0_ERROR&&n->error==7&&n->reference_delta==10000);
    open_page();for(i=0;i<4;++i)hook(8,0,0,1);CHECK(!n->used&&!kernel_pairs);
    menu_exit();save_log(out,test_case);
    printf("PASS reference-reopen fresh_delta=10000 interrupted=1 error=7 samples=0\n");
}

static void exits_and_failures(const char *out)
{
    unsigned i,j;P0State *n;RvSession *s;
    begin("MENU-reference");open_page();menu_exit();
    for(i=0;i<=4;++i){
        begin("MENU-admission");open_page();reference_ok();open_page();
        for(j=0;j<i;++j)hook(8,0,0,1);menu_exit();
    }
    begin("MENU-kernel-batch");open_page();reference_ok();open_page();admission();hook(8,0,0,1);menu_exit();
    begin("OK-partial-kernel-batch");open_page();reference_ok();open_page();admission();hook(8,0,0,1);
    hook(7,0x23,0x202c2d74,1);restored();save_log(out,"partial-bench");
    begin("OK-bench-keep1");open_page();reference_ok();open_page();hook(7,0x23,0x202c2d74,1);restored();
    begin("OK-DONE");open_page();reference_ok();finish();open_page();hook(7,0x23,0x202c2d84,0);restored();
    begin("H06-reference-close");open_page();hook(6,0,0,1);restored();
    CHECK(p0_host_state()->reference_flags==P0_REF_INTERRUPTED);
    begin("H01-reference-reentry");open_page();n=p0_host_state();tick_value=n->reference_start+60000;
    hook(1,0,0,0);CHECK(n->error==7&&n->phase==P0_REFERENCE&&n->reference_flags==5);
    CHECK(n->reference_start==61000);hook(7,0x23,0x202c2d84,0);restored();
    begin("zero-reference-start");tick_value=0;CHECK(!hook(1,0,0,0));restored();
    CHECK(p0_host_state()->phase==P0_ERROR&&!p0_host_state()->reference_start);
    for(i=0;i<4;++i){
        begin("admission-over-budget");open_page();reference_ok();open_page();n=p0_host_state();
        for(j=0;j<i;++j)hook(8,0,0,1);
        tick_step=n->admission_budget+1;hook(8,0,0,1);
        CHECK(n->phase==P0_ERROR&&n->error==9&&n->admitted==i&&!n->used&&admission_calls==i+1);
        hook(8,0,0,1);CHECK(!kernel_calls&&admission_calls==i+1);menu_exit();
        if(!i)save_log(out,"admission-over-budget");
    }
    for(i=0;i<3;++i){
        begin("publish-failure");open_page();n=p0_host_state();
        if(i){reference_ok();open_page();if(i==2){admission();hook(8,0,0,1);}}
        fail_text_once=1;hook(8,0,0,1);restored();
        CHECK(n->error==(i?8u:7u));
        if(!i){tick_value=100000;open_page();CHECK(n->reference_start==100000&&n->error==7);menu_exit();}
        else {open_page();CHECK(n->phase==P0_ERROR);menu_exit();}
    }
    begin("first-text-publish-failure");fail_text_once=1;CHECK(!hook(1,0,0,0));restored();
    CHECK(p0_host_state()->phase==P0_NEW&&!p0_host_state()->reference_start);
    open_page();reference_ok();
    begin("tag33-snapshot-restore");open_page();n=p0_host_state();s=rv_session(&root);
    {RvUiView v={0};RvReply r;RvRequest q=n->request;unsigned k;
     v.header=(RvBufferHeader){1,sizeof(v),0};v.part=2;v.tag=33;
     v.state_address=s->context.ui_state_address;v.state_bytes=s->context.ui_state_bytes;v.lease_token=s->context.state_lease;
     v.expected_array=RV_NATIVE_VIEWS;v.expected_count=1;v.expected_top_tag=33;v.expected_top_state=0x2022f71c;
     memcpy(n->wire.bytes,&v,sizeof(v));for(k=8;k<14;++k)q.args[k]=0;
     q.args[1]=s->context.state_lease;q.args[10]=p0_host_address(n->wire.bytes);q.args[11]=sizeof(v);
     root.inflight=1;p0_trace_begin(test_case);CHECK(n->api->call(RV_UI_VIEW,1,&q,&r)==RV_OK);p0_trace_end();root.inflight=0;
     CHECK(RV_WORD(RV_NATIVE_VIEWS+4)==root.ui_block);}
    menu_exit();
    begin("retry-1000");open_page();reference_ok();open_page();s=rv_session(&root);
    {uint32_t retained=next_alloc;for(i=0;i<1000;++i){menu_exit();open_page();CHECK(next_alloc==retained&&!n->used);}menu_exit();}
    printf("PASS exits MENU=REF/admission0..4/kernel/DONE/ERROR OK=REF/bench/DONE H06=REF publish_failures=first/text/REF/admission/kernel retries=1000 all_native_fields_exact=1\n");
}

int main(int argc,char **argv)
{
    CHECK(argc==8);probe_bytes=read_file(argv[1],probe_raw);full_bytes=read_file(argv[2],full_raw);
    installed_generation=rv_be32(full_raw+28);
    p0_trace_configure(memory,&next_alloc,(unsigned)strtoul(argv[4],0,10),(unsigned)strtoul(argv[5],0,10),(unsigned)strtoul(argv[6],0,10));
    if(!strcmp(argv[7],"negative")){
        begin("negative-unchanged-overlay-store");p0_trace_begin(test_case);RV_WORD(0x2037f3bc)=0;p0_trace_end();return 0;
    }
    adversarial(argv[3]);exits_and_failures(argv[3]);p0_trace_summary();
    printf("PASS r3 installed=%u assertions=%u\n",installed_generation,checks);return 0;
}
