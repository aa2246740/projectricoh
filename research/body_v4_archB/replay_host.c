/* Reuse actual bootstrap sources and their fixture harness, then probe gaps. */
#define main w0_fixture_suite_main
#include "../../firmware/resident_v4/arch_b/host_test.c"
#undef main

static void before_root_initialization(void)
{
    uint32_t frame[17], original[17], h, i, before = checks;
    const uint32_t ids[] = {1, 2, 5, 6, 7, 8};
    for (h = 0; h < sizeof(ids) / sizeof(ids[0]); ++h) {
        fixture();
        unknown_scope = 1;
        CHECK(bv4_boot(root) == RV4_UNKNOWN);
        for (i = 0; i < 17; ++i) frame[i] = original[i] = 0x4000 + i;
        bv4_hook_observe(root, ids[h], frame);
        CHECK(memcmp(frame, original, sizeof(frame)) != 0);
        CHECK(!opens && !allocs && !inits && !hooks);
    }
    report("COUNTEREXAMPLE_uninitialized_root_uses_emergency_instead_of_factory_replay", before);
}

static void loading_and_clean_failure(void)
{
    uint32_t frame[17], original[17], i, before = checks;
    fixture();
    memset(root, 0, sizeof(*root));
    root->magic = BV4_MAGIC;
    root->state = BV4_LOADING;
    root->flags = BV4_FACTORY;
    for (i = 0; i < 17; ++i) frame[i] = original[i] = 0x5000 + i;
    bv4_hook_observe(root, 6, frame);
    CHECK(!memcmp(frame, original, sizeof(frame)) && !hooks);
    fixture();
    file[400] ^= 1;
    CHECK(bv4_boot(root) == RV4_IDENTITY);
    bv4_hook_observe(root, 6, frame);
    CHECK(!memcmp(frame, original, sizeof(frame)) && !hooks && !inits);
    report("valid_factory_root_loading_and_clean_hash_failure_preserve_frame", before);
}

static void uncertain_failure_is_not_factory(void)
{
    uint32_t frame[17] = {0}, before = checks;
    fixture(); close_fault = 1;
    CHECK(bv4_boot(root) == RV4_IO);
    CHECK(!(root->flags & BV4_FACTORY));
    bv4_hook_observe(root, 6, frame);
    CHECK(frame[1] == 0x20011006 && !inits && !hooks);
    report("uncertain_handle_failure_has_no_full_factory_recovery_claim", before);
}

int main(void)
{
    w0_fixture_suite_main();
    before_root_initialization();
    loading_and_clean_failure();
    uncertain_failure_is_not_factory();
    printf("{\"case\":\"archB_r1_host_total\",\"checks\":%u,\"status\":\"PASS\"}\n", checks);
    return 0;
}
