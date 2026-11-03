#define main original_host_suite_main
#include TEST_HOST_SOURCE
#undef main

static RfwCache *start_six(const char *bank)
{
    RfwCache *cache;
    reset(); di_reset(); load_pair(bank); di_owner = 1;
    CHECK(rfw_open() >= 1);
    CHECK(rfw_select(6) == RV1_OK);
    cache = allocated_cache;
    CHECK(cache->applied_slot == 6 && cache->deep.active == 5);
    di_check(5);
    return cache;
}

static void fault_sweep(const char *bank)
{
    RfwCache *cache;
    unsigned total, at, mode, cases = 0, clean = 0, sticky = 0;
    unsigned calls, writes, attempts;
    uint8_t before[4096];
    int preview_count;
    cache = start_six(bank); calls = di_calls;
    CHECK(rfw_select(4) == RV1_OK);
    total = di_calls - calls;
    for (mode = 0; mode < 3; ++mode) for (at = 1; at <= total; ++at) {
        cache = start_six(bank);
        calls = di_calls; writes = di_writes; attempts = di_letters[22];
        memcpy(before, settings_a, sizeof(before)); preview_count = previews;
        if (mode == 0) di_fail = calls + at;
        else if (mode == 1) di_lost = calls + at;
        else di_bad = calls + at;
        cursor = 4;
        CHECK(rfw_cursor_commit() == 1);
        CHECK(cache->last_status == RV1_CONFLICT && cache->applied_slot == 6 && cursor == 6);
        CHECK(cache->deep.active == 5 && cache->pending_slot == 0 && !cache->busy);
        CHECK(memcmp(before, settings_a, sizeof(before)) == 0 && previews == preview_count);
        CHECK((cache->deep.uncertain != 0) == (di_letters[22] != attempts));
        if (cache->deep.uncertain) ++sticky;
        else { ++clean; CHECK(di_writes == writes); di_check(5); }
        calls = di_calls;
        CHECK(rfw_apply_action(1) == 1 && di_calls == calls && previews == preview_count);
        di_fail = di_lost = di_bad = 0;
        if (cache->deep.uncertain) {
            CHECK(rfw_select(4) == RV1_CONFLICT && di_calls == calls && cursor == 6);
            CHECK(cache->deep.uncertain && cache->applied_slot == 6);
        } else { CHECK(rfw_select(4) == RV1_OK); di_check(0); }
        ++cases;
    }
    printf("{\"test\":\"all_rpc_faults_06_to04\",\"successful_rpc_count\":%u,\"cases\":%u,\"clean\":%u,\"sticky\":%u}\n",total,cases,clean,sticky);
}

static void compatibility(const char *bank)
{
    RfwCache *cache;
    uint8_t before[4096];
    unsigned calls;
    int preview_count;
    cache = start_six(bank);
    di_fail = di_calls + 1; cursor = 4;
    CHECK(rfw_apply_action(0) == 1 && !rfw_is_open());
    CHECK(cache->applied_slot == 6 && cursor == 6 && !cache->deep.uncertain);
    di_fail = 0; ui_count = 1; cursor = (uint8_t)rfw_open();
    CHECK(cursor == 6 && cache->applied_slot == 6);
    CHECK(rfw_select(4) == RV1_OK); di_check(0);
    cache = start_six(bank);
    cache->bank.slots[0].recipe.name[0] = 'C';
    CHECK(rfw_deep_id(&cache->bank.slots[0].recipe) == 0);
    CHECK(rfw_select(1) == RV1_OK && cache->applied_slot == 1);
    di_check(0);
    cache = start_six(bank);
    cache->bank.slots[0].recipe.name[0] = 'C';
    di_owner = 0; memcpy(before, settings_a, sizeof(before)); preview_count = previews;
    CHECK(rfw_select(1) == RV1_CONFLICT && cache->applied_slot == 6 && cursor == 6);
    CHECK(memcmp(before, settings_a, sizeof(before)) == 0 && previews == preview_count);
    cache = start_six(bank);
    preview_error = 1;
    CHECK(rfw_select(4) == RV1_IO && cache->applied_slot == 4 && cursor == 4);
    CHECK(cache->deep.active == 0 && !cache->deep.uncertain && !cache->busy);
    di_check(0); calls = di_calls; preview_count = previews;
    CHECK(rfw_apply_action(0) == 1 && di_calls == calls && previews == preview_count);
    reset(); di_reset(); load_pair(bank); files[2].exists = files[3].exists = 0;
    CHECK(rfw_open() >= 1); cache = allocated_cache;
    for (unsigned slot = 1; slot <= 8; ++slot) {
        CHECK(rfw_select(slot) == RV1_OK && cache->applied_slot == slot && cache->deep.active == 0);
        CHECK(di_calls == 0 && di_writes == 0);
    }
    printf("{\"test\":\"compatibility\",\"clean_exit_reopen\":true,\"custom_restore\":true,\"custom_restore_refusal\":true,\"preview_io_committed\":true,\"missing_tables_surface_apply\":true}\n");
}

static void reopen_counterexample(const char *bank)
{
    RfwCache *cache = start_six(bank);
    unsigned calls;
    uint8_t before[4096];
    int preview_count;
    memcpy(before, settings_a, sizeof(before)); preview_count = previews;
    di_lost = di_calls + 3;
    CHECK(rfw_select(4) == RV1_CONFLICT && cache->deep.uncertain && cursor == 6 && cache->applied_slot == 6);
    calls = di_calls;
    CHECK(rfw_apply_action(0) == 1 && !rfw_is_open() && di_calls == calls);
    ui_count = 1; di_lost = 0;
    cursor = (uint8_t)rfw_open();
    printf("{\"phase\":\"reopened_after_partial_W\",\"cursor\":%u,\"applied_slot\":%u,\"deep_active\":%u,\"uncertain\":%u}\n",cursor,cache->applied_slot,cache->deep.active,cache->deep.uncertain);
    cursor = 4; CHECK(rfw_cursor_commit() == 1);
    CHECK(cache->last_status == RV1_CONFLICT && di_calls == calls);
    CHECK(memcmp(before, settings_a, sizeof(before)) == 0 && previews == preview_count);
    printf("{\"phase\":\"refused_again_after_reopen\",\"cursor\":%u,\"applied_slot\":%u,\"deep_active\":%u,\"uncertain\":%u,\"additional_rpc\":%u}\n",cursor,cache->applied_slot,cache->deep.active,cache->deep.uncertain,di_calls-calls);
    fflush(stdout);
    CHECK(cursor == 6 && cache->applied_slot == 6);
}

int main(int argc, char **argv)
{
    CHECK(argc == 4); binding = rfw_closed_table;
    load_image(argv[2], table_equal, sizeof(table_equal)); di_file = table_equal;
    if (strcmp(argv[3], "reopen") == 0) reopen_counterexample(argv[1]);
    else { CHECK(strcmp(argv[3], "normal") == 0); fault_sweep(argv[1]); compatibility(argv[1]); }
    reset(); di_reset(); return 0;
}
