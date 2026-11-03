/* Exercise production selection code with the existing native-service model. */
#define main original_host_suite_main
#include TEST_HOST_SOURCE
#undef main

static int rows_match(unsigned profile)
{
    unsigned row;
    for (row = 0; row < RFW_DEEP_ROWS; ++row)
        if (memcmp(di_row(row), di_expect(row, profile), di_bytes[row]) != 0)
            return 0;
    return di_t[0] == 0 && di_t[1] == di_expect_control(profile);
}

int main(int argc, char **argv)
{
    RfwCache *cache;
    Rv1Status result;
    unsigned active, writes, preview_count;
    uint8_t before[4096];
    int success, unchanged, restored, blocked;
    CHECK(argc == 4);
    binding = rfw_closed_table;
    load_image(argv[2], table_equal, sizeof(table_equal));
    di_file = table_equal;
    reset(); di_reset(); load_pair(argv[1]); di_owner = 1;
    CHECK(rfw_open() >= 1);
    CHECK(rfw_select(6) == RV1_OK);
    cache = (RfwCache *)allocated_cache;
    active = rfw_deep_id(&rfw_defaults[5]);
    CHECK(active != 0 && cache->deep.active == active && rows_match(active));
    memcpy(before, settings_a, sizeof(before));
    writes = di_writes; preview_count = (unsigned)previews;

    success = strcmp(argv[3], "success") == 0;
    if (strcmp(argv[3], "first_rpc_failed") == 0) di_fail = di_calls + 1;
    else if (strcmp(argv[3], "first_reply_lost") == 0) di_lost = di_calls + 1;
    else if (strcmp(argv[3], "control_already_stock") == 0) di_t[1] = 2;
    else if (strcmp(argv[3], "ownership_lost") == 0) di_owner = 0;
    else if (strcmp(argv[3], "control_write_reply_lost") == 0) di_lost = di_calls + 3;
    else CHECK(success);

    result = rfw_select(4);
    unchanged = memcmp(before, settings_a, sizeof(before)) == 0;
    restored = rows_match(0) && cache->deep.active == 0;
    blocked = result != RV1_OK && result != RV1_IO && unchanged &&
        cache->applied_slot == 6 && (unsigned)previews == preview_count;
    printf("{\"case\":\"%s\",\"return_status\":%u,\"applied_slot\":%u,"
           "\"highlighted_slot\":%u,\"deep_active\":%u,\"uncertain\":%u,"
           "\"t_control\":%u,\"additional_writes\":%u,\"additional_previews\":%u,"
           "\"settings_unchanged\":%s,\"all_stock_rows_restored\":%s,"
           "\"failed_switch_not_published\":%s}\n",
           argv[3], (unsigned)result, cache->applied_slot, cursor,
           cache->deep.active, cache->deep.uncertain,
           ((unsigned)di_t[0] << 8) | di_t[1], di_writes - writes,
           (unsigned)previews - preview_count, unchanged ? "true" : "false",
           restored ? "true" : "false", blocked ? "true" : "false");
    fflush(stdout);
    if (success) CHECK(result == RV1_OK && cache->applied_slot == 4 && restored);
    else CHECK(blocked);
    reset(); di_reset();
    return 0;
}
