#define main original_host_suite_main
#include TEST_HOST_SOURCE
#undef main

int main(int argc, char **argv)
{
    static const unsigned sweep[] = {4, 5, 6, 7, 8, 4};
    unsigned from, to, step, pairs = 0;
    RfwCache *cache;
    CHECK(argc == 4);
    binding = rfw_closed_table;
    load_image(argv[2], table_equal, sizeof(table_equal));
    di_file = table_equal;
    for (from = 1; from <= 8; ++from) {
        for (to = 1; to <= 8; ++to) {
            reset(); di_reset(); load_pair(argv[1]); di_owner = 1;
            CHECK(rfw_open() >= 1);
            cursor = (uint8_t)from;
            CHECK(rfw_cursor_commit() == 1);
            cache = (RfwCache *)allocated_cache;
            CHECK(cache->last_status == RV1_OK && cache->applied_slot == from);
            cursor = (uint8_t)to;
            CHECK(rfw_apply_action(1) == 1);
            CHECK(cache->last_status == RV1_OK && cache->applied_slot == to);
            CHECK(!cache->deep.uncertain);
            di_check(rfw_deep_id(&rfw_defaults[to - 1]));
            ++pairs;
        }
    }
    reset(); di_reset(); load_pair(argv[1]); di_owner = 1;
    CHECK(rfw_open() >= 1);
    cache = (RfwCache *)allocated_cache;
    for (step = 0; step < sizeof(sweep) / sizeof(sweep[0]); ++step) {
        cursor = (uint8_t)sweep[step];
        CHECK(rfw_cursor_commit() == 1);
        CHECK(cache->last_status == RV1_OK && cache->applied_slot == sweep[step]);
        di_check(rfw_deep_id(&rfw_defaults[sweep[step] - 1]));
    }
    CHECK(rfw_apply_action(0) == 1);
    ui_count = 1; /* Native UI reconstructs its entry before reopening. */
    CHECK(rfw_open() == 4 && cache->deep.active == 0 && !cache->deep.uncertain);
    di_check(0);
    printf("{\"case\":\"daily_sweep\",\"ordered_pairs\":%u,\"sweep_steps\":%u,"
           "\"all_stock_rows_restored\":true,\"reopened_slot\":4}\n", pairs, step);
    reset(); di_reset();
    return 0;
}
