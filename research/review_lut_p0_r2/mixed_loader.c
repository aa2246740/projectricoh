#define main candidate_original_main
#include "../../firmware/lut_p0_timing/host_checks.c"
#undef main

int main(int argc,char **argv)
{
    static uint8_t prior[65536];
    uint32_t prior_bytes;
    RvSession *s;
    CHECK(argc==4);
    probe_bytes=read_file(argv[1],probe_raw);
    prior_bytes=read_file(argv[2],prior);
    full_bytes=read_file(argv[3],full_raw);
    CHECK(rv_be32(prior+28)==113&&rv_be32(full_raw+28)==114);
    reset();seed_file(0,prior,prior_bytes);files[2].exists=0;rv_reset(&root);
    CHECK(rv_load(&root,&rv_trust)==RV_OK);
    s=rv_session(&root);CHECK(s&&s->selected_source==RV_SOURCE_B&&s->generation==114);
    CHECK(!write_calls&&!rename_calls&&!memcmp(files[0].bytes,prior,prior_bytes)&&!memcmp(files[1].bytes,full_raw,full_bytes));
    printf("PASS mixed IROM A=113/B=114 no DAT: selected B/114, exact files unchanged\n");
    reset();seed_file(1,prior,prior_bytes);files[2].exists=0;rv_reset(&root);
    CHECK(rv_load(&root,&rv_trust)==RV_OK);
    s=rv_session(&root);CHECK(s&&s->selected_source==RV_SOURCE_A&&s->generation==114);
    CHECK(!write_calls&&!rename_calls&&!memcmp(files[1].bytes,prior,prior_bytes)&&!memcmp(files[0].bytes,full_raw,full_bytes));
    printf("PASS mixed IROM A=114/B=113 no DAT: selected A/114, exact files unchanged\n");
    reset();seed_file(0,prior,prior_bytes);rv_reset(&root);
    CHECK(rv_load(&root,&rv_trust)==RV_OK);
    s=rv_session(&root);CHECK(s&&s->selected_source==RV_SOURCE_CARD&&s->generation==1);
    CHECK(!write_calls&&!rename_calls&&!memcmp(files[0].bytes,prior,prior_bytes)&&!memcmp(files[1].bytes,full_raw,full_bytes));
    printf("PASS mixed IROM A=113/B=114 plus P0 DAT: selected card/1, exact IROM unchanged\n");
    return 0;
}
