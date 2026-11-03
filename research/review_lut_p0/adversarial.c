#define main candidate_original_main
#define rv_native_alloc candidate_host_alloc
#include "../../firmware/lut_p0_timing/host_checks.c"
#undef rv_native_alloc
#undef main

static unsigned fail_ui_once;
uint32_t rv_native_alloc(uint32_t bytes)
{
    if(fail_ui_once && bytes==sizeof(RvUiSnapshot)) {
        fail_ui_once=0;
        return 0;
    }
    return candidate_host_alloc(bytes);
}

static void finish_and_save(const char *path)
{
    unsigned i;
    CHECK(hook(1,0,0,0)==(uint32_t)(uintptr_t)rv_skip_01);
    native_finish_constructor(1);
    for(i=0;i<P0_SAMPLES;++i) {
        RV_BYTE(0x2022f726)=(i&15)+1;
        hook(8,0,0,1);
    }
    CHECK(p0_host_state()->phase==P0_DONE&&!p0_host_state()->error);
    for(i=3;i<5;++i)if(files[i].exists&&files[i].n==4096&&rv_be32(files[i].bytes+2432+20)==72) {
        FILE *f=fopen(path,"wb");CHECK(f);
        CHECK(fwrite(files[i].bytes,1,4096,f)==4096&&!fclose(f));
        break;
    }
    CHECK(i<5);
}

int main(int argc,char **argv)
{
    uint32_t start,retained,i,used;
    uint8_t state[32],descriptors[72];
    P0State *n;
    CHECK(argc==5);
    probe_bytes=read_file(argv[1],probe_raw);
    full_bytes=read_file(argv[2],full_raw);
    installed_generation=rv_be32(full_raw+28);

    reset();
    memcpy(state,RV_PTR(0x2022f71c),sizeof(state));
    memcpy(descriptors,RV_PTR(0x2022f56c),sizeof(descriptors));
    CHECK(hook(1,0,0,0)==(uint32_t)(uintptr_t)rv_skip_01);
    CHECK(memcmp(descriptors,RV_PTR(0x2022f56c),sizeof(descriptors)));
    printf("native_writes_after_H01:");
    for(i=0;i<32;++i)if(state[i]!=RV_BYTE(0x2022f71c+i))printf(" %08x",0x2022f71c+i);
    for(i=0;i<72;++i)if(descriptors[i]!=RV_BYTE(0x2022f56c+i))printf(" %08x",0x2022f56c+i);
    printf("\n");

    reset();enter();n=p0_host_state();start=n->reference_start;
    CHECK(hook(7,0x29,0x202bd890,0)==(uint32_t)(uintptr_t)rv_close_07);
    tick_value=start+60000;
    enter();
    CHECK(n->phase==P0_REFERENCE&&n->reference_start==start);
    tick_value=start+70000;
    hook(7,0x23,0x202c2d84,0);
    CHECK(n->phase==P0_BENCH&&!n->error&&n->reference_delta==70000);
    printf("reference_reopen: outside_page_ticks=60000 user_visible_interval=10000 accepted_delta=%u error=%u\n",n->reference_delta,n->error);
    finish_and_save(argv[3]);

    reset();fail_ui_once=1;
    CHECK(hook(1,0,0,0)==0);
    n=p0_host_state();
    CHECK(root.state==RV_READY&&n->phase==P0_REFERENCE&&n->reference_start==0);
    native_finish_constructor(1);
    tick_value=100000;
    CHECK(hook(1,0,0,0)==(uint32_t)(uintptr_t)rv_skip_01);
    native_finish_constructor(1);
    CHECK(n->reference_start==0);
    tick_value=110000;
    hook(7,0x23,0x202c2d84,0);
    CHECK(n->phase==P0_BENCH&&!n->error&&n->reference_delta==110000);
    printf("first_publish_retry: first_UI_alloc_failed=1 visible_start_tick=100000 visible_end_tick=110000 accepted_start=%u accepted_delta=%u error=%u\n",n->reference_start,n->reference_delta,n->error);
    finish_and_save(argv[4]);

    reset();enter();calibrate();n=p0_host_state();
    retained=next_alloc;used=n->used;
    for(i=0;i<1000;++i) {
        CHECK(hook(7,0x29,0x202bd890,0)==(uint32_t)(uintptr_t)rv_close_07);
        enter();
        CHECK(next_alloc==retained&&n->used==used);
    }
    unchanged();
    printf("menu_reopen_1000: extra_allocation_bytes=%u phase=%u unchanged_files=1\n",next_alloc-retained,n->phase);
    return 0;
}
