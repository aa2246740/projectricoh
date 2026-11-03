/* Stage 2j review regressions. Keep these after every Stage 2i case. */
#if RFW_DEEP_ENABLED
static void review_tests(void)
{
    RfwCache *cache;
    unsigned i, fault, calls;
    RfwDeepState state;
    cache = v3_open(table_grain, 2);
    CHECK(rfw_select(3) == RV1_OK);
    shooting_category = 0; settings_a[0x3aa] = 16;
    for (i = 0; i < 256; ++i) {
        settings_a[RV1_SELECTOR_OFFSET] = (uint8_t)i;
        v3_block_reset(); CHECK(v3_grain_once() == (i == 3));
    }
    settings_a[RV1_SELECTOR_OFFSET] = 3;
    passed("F1: every S+0x36e selector except the active recipe base_mode disables grain without packet writes");
    for (i = 0; i < RFW_GRAIN_S_BYTES; ++i) {
        settings_length = i;
        v3_block_reset(); CHECK(v3_grain_once() == 0);
    }
    settings_length = RFW_GRAIN_S_BYTES;
    v3_block_reset(); CHECK(v3_grain_once() == 1);
    settings_length = sizeof(settings_a);
    passed("F1: grain requires the complete S+0xc9d byte; exactly 0xc9e bytes is sufficient");
    for (i = 0; i < 256; ++i) {
        settings_a[0xc9d] = (uint8_t)i;
        v3_block_reset(); CHECK(v3_grain_once() == 1);
        CHECK(v3_block[0x10] == 0 && v3_block[0x32] == 1);
        CHECK(v3_block[0x6f] == (i >= 1 && i <= 3 ? i : 1));
    }
    passed("F2: firing grain sets scene 21, mono 0, style 1 and level 1..3 with invalid levels mapped to 1");
    for (i = 0; i < 256; ++i) {
        uint8_t before[144];
        v3_block_reset();
        v3_block[0x0f] = (uint8_t)i;
        memset(v3_block + 0x33, (int)i, 4);
        memcpy(before, v3_block, sizeof(before));
        CHECK(v3_grain_once() == 1);
        CHECK(v3_block[0x0f] == before[0x0f] && memcmp(v3_block+0x33, before+0x33, 4) == 0);
    }
    passed("F2: WB and the remaining four picture-style bytes stay unchanged");
    {
        const uint8_t *sets[] = {table_new, table_equal, table_matrix, table_t};
        unsigned f, slot;
        for (f = 0; f < 4; ++f) {
            cache = v3_open(sets[f], 2); di_file = sets[f];
            for (slot = 1; slot <= 8; ++slot) {
                CHECK(rfw_select(slot) == RV1_OK);
                shooting_category = 0; settings_a[0x3aa] = 16;
                v3_block_reset(); CHECK(v3_grain_once() == 0);
            }
        }
        di_file = table_equal;
    }
    passed("F1/F2: without the grain bit all 144 packet bytes remain unchanged for every slot");
    for (i = 0; i < 4; ++i) {
        di_reset(); di_owner = 1; di_file = table_t; state = v3_state(table_t);
        if (i == 0) di_t[1] = 0;
        if (i == 1) di_t[1] = 1;
        if (i == 2) di_t[0] = 1;
        if (i == 3) state.t_checked = 0;
        CHECK(rfw_deep_transition(&state, di_key(V3_T08)) == RV1_CONFLICT);
        CHECK(di_writes == 0 && state.active == 0 && !state.uncertain);
    }
    passed("F3: entering control-0 with unchecked T or unexpected T refuses before all row and T writes");
    for (fault = 0; fault < 3; ++fault) for (i = 3; i <= 4; ++i) {
        di_reset(); di_owner = 1; di_file = table_t; state = v3_state(table_t);
        if (fault == 0) di_fail = i;
        if (fault == 1) di_lost = i;
        if (fault == 2) di_bad = i;
        CHECK(rfw_deep_transition(&state, di_key(V3_T08)) == RV1_CONFLICT);
        CHECK(di_writes == 0 && state.active == 0 && !state.uncertain);
        di_fail = di_lost = di_bad = 0;
        CHECK(rfw_deep_transition(&state, di_key(V3_T08)) == RV1_OK);
        di_check(V3_T08);
    }
    passed("F3: either pre-check RPC failing, losing its reply or returning the wrong value refuses with zero writes and can retry");
    for (fault = 0; fault < 2; ++fault) for (i = 1; i <= 2; ++i) {
        reset(); di_reset(); load_pair(test_library); install_tables(table_new, RFW_TABLE_BYTES);
        di_owner = 1;
        if (fault == 0) di_fail = i; else di_lost = i;
        CHECK(rfw_open() >= 1); cache = tt_cache();
        CHECK(!cache->deep.t_checked && !cache->deep.t_warn && di_writes == 0);
        di_fail = di_lost = 0; calls = di_calls;
        rfw_close(); CHECK(rfw_open() >= 1 && di_calls == calls + 2);
        CHECK(cache->deep.t_checked && !cache->deep.t_warn && !cache->deep.uncertain && di_writes == 0);
        calls = di_calls;
        rfw_close(); CHECK(rfw_open() >= 1 && di_calls == calls);
    }
    passed("F3: failed first X or V leaves t_checked clear; a later refresh retries and a valid stock read disarms it");
    reset(); di_reset();
}
#endif
