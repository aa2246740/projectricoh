/* Uses test_host.c's real firmware adapters and cursor/RPC memory model. */
#if RFW_DEEP_ENABLED
static RfwCache *switch_from_six(const uint8_t *table)
{
    RfwCache *cache = v3_open(table, 2);
    di_file = table;
    cursor = 6;
    CHECK(rfw_cursor_commit() == 1);
    CHECK(cache->last_status == RV1_OK && cache->applied_slot == 6);
    CHECK(cache->deep.active == 5 && !cache->deep.uncertain);
    di_check(5);
    return cache;
}

static void switch_refused(RfwCache *cache, const uint8_t *before,
                           int preview_count, unsigned previous)
{
    CHECK(cache->last_status == RV1_CONFLICT);
    CHECK(memcmp(settings_a, before, sizeof(settings_a)) == 0);
    CHECK(previews == preview_count && cache->applied_slot == previous);
    CHECK(cursor == previous && cache->pending_slot == 0 && !cache->busy);
}

static void switch_residue_case(const char *name)
{
    RfwCache *cache;
    uint8_t before[4096];
    unsigned calls, writes;
    int preview_count;
    if (strcmp(name, "rpc-first") == 0 || strcmp(name, "ownership") == 0 ||
        strcmp(name, "sticky") == 0) {
        cache = switch_from_six(table_new);
        memcpy(before, settings_a, sizeof(before));
        preview_count = previews; calls = di_calls; writes = di_writes;
        if (strcmp(name, "rpc-first") == 0) di_fail = calls + 1;
        else if (strcmp(name, "ownership") == 0) di_owner = 0;
        else di_lost = calls + 3; /* First row W executes, reply is lost. */
        cursor = 4;
        CHECK(rfw_cursor_commit() == 1);
        switch_refused(cache, before, preview_count, 6);
        CHECK(cache->deep.active == 5);
        CHECK(cache->deep.uncertain == (strcmp(name, "sticky") == 0));
        if (!cache->deep.uncertain) {
            CHECK(di_writes == writes);
            CHECK(di_calls == calls + (di_owner ? 1u : 0u));
            di_check(5);
        } else CHECK(di_writes == writes + 1);
        calls = di_calls;
        CHECK(rfw_apply_action(1) == 1 && di_calls == calls);
        CHECK(cache->last_status == RV1_CONFLICT && cursor == 6);
        if (cache->deep.uncertain) {
            di_lost = 0;
            CHECK(rfw_select(4) == RV1_CONFLICT && di_calls == calls);
            CHECK(cache->deep.uncertain && cache->deep.active == 5);
            switch_refused(cache, before, preview_count, 6);
        }
    } else if (strcmp(name, "t-mismatch") == 0) {
        cache = v3_open(table_t, 2); di_file = table_t;
        cursor = 8; CHECK(rfw_cursor_commit() == 1);
        CHECK(cache->applied_slot == 8 && cache->deep.active == V3_T08);
        CHECK(di_t[1] == 0); di_check(V3_T08);
        memcpy(before, settings_a, sizeof(before));
        preview_count = previews; calls = di_calls; writes = di_writes;
        di_bad = calls + 2; /* V2444 returns 1 instead of live 0. */
        cursor = 4; CHECK(rfw_cursor_commit() == 1);
        switch_refused(cache, before, preview_count, 8);
        CHECK(cache->deep.active == V3_T08 && !cache->deep.uncertain);
        CHECK(di_calls == calls + 2 && di_writes == writes);
        di_check(V3_T08);
        calls = di_calls;
        CHECK(rfw_apply_action(1) == 1 && di_calls == calls);
    } else if (strcmp(name, "t-entry") == 0) {
        cache = switch_from_six(table_t);
        memcpy(before, settings_a, sizeof(before));
        preview_count = previews; calls = di_calls; writes = di_writes;
        di_t[1] = 0; /* Entry to control-0 requires freshly read stock 2. */
        cursor = 8; CHECK(rfw_cursor_commit() == 1);
        switch_refused(cache, before, preview_count, 6);
        CHECK(cache->deep.active == 5 && !cache->deep.uncertain);
        CHECK(di_calls == calls + 2 && di_writes == writes && di_t[1] == 0);
    } else if (strcmp(name, "success") == 0 || strcmp(name, "slot08") == 0) {
        unsigned slot = strcmp(name, "success") == 0 ? 4u : 8u;
        unsigned profile = slot == 4 ? 0u : 7u;
        int file_opens;
        cache = switch_from_six(table_new);
        preview_count = previews; calls = di_calls; writes = di_writes; file_opens = opens;
        di_preview = (int)profile;
        cursor = (uint8_t)slot; CHECK(rfw_cursor_commit() == 1);
        CHECK(cache->last_status == RV1_OK && cache->applied_slot == slot && cursor == slot);
        CHECK(cache->deep.active == profile && !cache->deep.uncertain);
        CHECK(cache->pending_slot == 0 && !cache->busy && previews == preview_count + 1);
        CHECK(di_calls > calls && di_writes == writes + 96 && opens == file_opens);
        CHECK(settings_a[RV1_SELECTOR_OFFSET] == RV1_BASE_STANDARD);
        CHECK(settings_a[RV1_WB0_OFFSET] == 9 && settings_a[RV1_WB1_OFFSET] == 9);
        di_check(profile);
        calls = di_calls;
        CHECK(rfw_apply_action(1) == 1 && di_calls == calls && previews == preview_count + 1);
        if (slot == 8) {
            /* A second ordinary switch must restore all rows after 08. */
            di_preview = 0; cursor = 4; CHECK(rfw_cursor_commit() == 1);
            CHECK(cache->last_status == RV1_OK && cache->applied_slot == 4);
            di_check(0);
        }
    } else if (strcmp(name, "no-applied") == 0) {
        cache = v3_open(table_new, 2);
        CHECK(cache->applied_slot == 0);
        memcpy(before, settings_a, sizeof(before)); preview_count = previews; calls = di_calls;
        di_owner = 0; cursor = 6; CHECK(rfw_cursor_commit() == 1);
        CHECK(cache->last_status == RV1_CONFLICT && cache->applied_slot == 0);
        CHECK(cache->deep.active == 0 && !cache->deep.uncertain && cursor == 6);
        CHECK(di_calls == calls && previews == preview_count && memcmp(before, settings_a, sizeof(before)) == 0);
    } else if (strcmp(name, "compat") == 0) {
        reset(); di_reset(); load_pair(test_library);
        files[2].exists = files[3].exists = 0;
        CHECK(rfw_open() >= 1); cache = tt_cache();
        CHECK(!cache->deep.tables_ok);
        cursor = 6; CHECK(rfw_cursor_commit() == 1);
        CHECK(cache->last_status == RV1_OK && cache->applied_slot == 6 && !cache->deep.active);
        CHECK(di_calls == 0 && previews == 1 && cursor == 6);
        cache = v3_open(table_new, 2);
        /* A card recipe with another name is a surface-only custom recipe. */
        cache->bank.slots[5].recipe.name[0] = 'C';
        CHECK(rfw_deep_id(&cache->bank.slots[5].recipe) == 0);
        di_owner = 0; calls = di_calls; cursor = 6;
        CHECK(rfw_cursor_commit() == 1 && cache->last_status == RV1_OK);
        CHECK(cache->applied_slot == 6 && !cache->deep.active && di_calls == calls);
        CHECK(previews == 1 && cursor == 6);
    } else {
        CHECK(strcmp(name, "invalid") == 0);
        cache = v3_open(table_new, 2);
        CHECK(rfw_select(4) == RV1_OK);
        memcpy(before, settings_a, sizeof(before)); preview_count = previews; calls = di_calls;
        CHECK(rfw_select(0) == RV1_RANGE && cursor == 4);
        CHECK(rfw_select(17) == RV1_RANGE && cursor == 4);
        CHECK(rfw_select(16) == RV1_EMPTY && cursor == 16 && cache->applied_slot == 4);
        CHECK(previews == preview_count && di_calls == calls && memcmp(before, settings_a, sizeof(before)) == 0);
    }
    passed(name);
    reset(); di_reset(); di_file = table_equal;
}

static void switch_residue_tests(void)
{
    static const char *const names[] = {"rpc-first", "ownership", "sticky", "t-mismatch", "t-entry",
                                      "success", "slot08", "no-applied", "compat", "invalid"};
    unsigned i;
    for (i = 0; i < sizeof(names) / sizeof(names[0]); ++i) switch_residue_case(names[i]);
}
#endif
