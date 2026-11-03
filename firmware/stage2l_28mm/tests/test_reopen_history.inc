/* A retained UI history is not evidence that a partial ISP write completed. */
#if RFW_DEEP_ENABLED
static const char *const history_names[] = {
    "history-sticky-reopen", "history-normal-reopen", "history-clean-reopen",
    "history-first-failure", "history-stock-reopen", "history-generation",
    "history-bank-other-slot", "history-renamed", "history-raw-changed",
    "history-wb-changed", "history-replaced", "history-moved", "history-empty",
    "history-custom-reopen", "history-custom-renamed", "history-no-card"
};

static void history_replace_bank(const Rv1Bank *bank)
{
    unsigned i;
    for (i = 0; i < 2; ++i) {
        CHECK(rv1_encode(bank, bank->generation + 1, files[i].bytes,
                         sizeof(files[i].bytes)) == RV1_OK);
        files[i].exists = 1;
        files[i].length = RV1_FILE_BYTES;
    }
}

static void history_case(const char *name)
{
    RfwCache *cache;
    Rv1Bank replacement;
    RfwDeepState deep;
    uint8_t before[4096];
    unsigned calls, writes, expected = 6, target, n;
    int preview_count;
    cache = v3_open(table_new, 2);
    di_file = table_new;
    if (strcmp(name, "history-custom-reopen") == 0 || strcmp(name, "history-custom-renamed") == 0)
        cache->bank.slots[5].recipe.name[0] = 'C';
    if (strcmp(name, "history-first-failure") == 0) expected = 0;
    else {
        if (strcmp(name, "history-stock-reopen") == 0) expected = 4;
        CHECK(rfw_select(expected) == RV1_OK);
        CHECK(cache->applied_slot == expected);
    }
    memcpy(before, settings_a, sizeof(before));
    preview_count = previews;
    if (strcmp(name, "history-normal-reopen") != 0) {
        target = expected == 6 ? 4 : 6;
        if (strcmp(name, "history-custom-reopen") == 0 || strcmp(name, "history-custom-renamed") == 0)
            target = 1;
        if (strcmp(name, "history-clean-reopen") == 0) di_fail = di_calls + 1;
        else {
            unsigned want = rfw_deep_id(&cache->bank.slots[target - 1].recipe);
            unsigned have_t = v3_mask(table_new, cache->deep.active) & RFW_EXT_CONTROL;
            unsigned want_t = v3_mask(table_new, want) & RFW_EXT_CONTROL;
            di_lost = di_calls + 3 + (cache->deep.neighbor_valid ? 0u : 2u) +
                      (!have_t && want_t ? 2u : 0u);
        }
        CHECK(rfw_select(target) == RV1_CONFLICT);
        CHECK(cache->applied_slot == expected);
        CHECK(cache->deep.uncertain == (strcmp(name, "history-clean-reopen") != 0));
    }
    deep = cache->deep;
    replacement = cache->bank;
    if (strcmp(name, "history-renamed") == 0) replacement.slots[5].recipe.name[0] = 'C';
    else if (strcmp(name, "history-custom-renamed") == 0) replacement.slots[5].recipe.name[0] = 'D';
    else if (strcmp(name, "history-raw-changed") == 0) {
        replacement.slots[5].recipe.base_mode = RV1_BASE_COLOR;
        memset(replacement.slots[5].recipe.raw, 5, RV1_COLOR_BYTES);
    }
    else if (strcmp(name, "history-wb-changed") == 0) replacement.slots[5].recipe.wb[1] = 1;
    else if (strcmp(name, "history-replaced") == 0) replacement.slots[5] = replacement.slots[3];
    else if (strcmp(name, "history-moved") == 0) {
        replacement.slots[0] = replacement.slots[5];
        replacement.slots[5].occupied = 0;
    } else if (strcmp(name, "history-empty") == 0) replacement.slots[5].occupied = 0;
    else if (strcmp(name, "history-bank-other-slot") == 0) replacement.slots[0].recipe.name[0] = 'C';
    history_replace_bank(&replacement);
    if (strcmp(name, "history-no-card") == 0) {
        for (n = 0; n < RFW_DEFAULT_SLOTS; ++n)
            CHECK(rv1_validate_recipe(&rfw_defaults[n]) == RV1_OK);
        ready = 0;
    }
    if (strcmp(name, "history-renamed") == 0 || strcmp(name, "history-raw-changed") == 0 ||
        strcmp(name, "history-wb-changed") == 0 || strcmp(name, "history-replaced") == 0 ||
        strcmp(name, "history-moved") == 0 || strcmp(name, "history-empty") == 0 ||
        strcmp(name, "history-custom-renamed") == 0) expected = 0;
    calls = di_calls; writes = di_writes;
    di_fail = di_lost = 0;
    for (n = 0; n < 2; ++n) {
        CHECK(rfw_apply_action(0) == 1 && !rfw_is_open());
        ui_count = 1;
        cursor = (uint8_t)rfw_open();
        printf("history_reopened case=%s cycle=%u cursor=%u applied=%u active=%u uncertain=%u rpc=%u\n",
               name, n, cursor, cache->applied_slot, cache->deep.active,
               cache->deep.uncertain, di_calls - calls);
        CHECK(allocated_cache == cache && cache->applied_slot == expected);
        CHECK(cursor == (expected ? expected : 1));
        CHECK(memcmp(&cache->deep, &deep, sizeof(deep)) == 0);
        CHECK(di_calls == calls && di_writes == writes);
        CHECK(previews == preview_count && memcmp(before, settings_a, sizeof(before)) == 0);
        if (cache->deep.uncertain) {
            cursor = 4;
            CHECK(rfw_cursor_commit() == 1 && cache->last_status == RV1_CONFLICT);
            CHECK(cursor == (expected ? expected : 4));
            CHECK(cache->applied_slot == expected && cache->pending_slot == 0 && !cache->busy);
            CHECK(di_calls == calls && di_writes == writes && previews == preview_count);
            CHECK(memcmp(before, settings_a, sizeof(before)) == 0);
        }
    }
    if (!cache->deep.uncertain) {
        CHECK(rfw_select(4) == RV1_OK && cache->applied_slot == 4);
        di_check(0);
    }
    passed(name);
    reset(); di_reset(); di_file = table_equal;
}

static void history_tests(void)
{
    unsigned i;
    for (i = 0; i < sizeof(history_names) / sizeof(history_names[0]); ++i)
        history_case(history_names[i]);
}
#endif
