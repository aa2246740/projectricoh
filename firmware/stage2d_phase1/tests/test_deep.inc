/* Drive the real ADJ/apply path with a cursor/readback RPC model. */
static uint8_t di_info[2048], di_ram[RFW_DEEP_ROWS][98];
static int di_ready = 1, di_limit = 9, di_context, di_owner;
static unsigned di_calls, di_writes, di_fail, di_lost, di_crossed, di_bad, di_drop;
static unsigned di_letters[24], di_order[110], di_disconnect;
static uint32_t di_base, di_cursor;
static int di_preview = -1;
int32_t gxr_rpc_ready(void) { return di_ready && (!di_disconnect || di_calls < di_disconnect); }
int32_t gxr_rpc_limit(void) { return di_limit; }
int32_t gxr_thread_context(void) { return di_context; }
const volatile uint8_t *gxr_unit_info(uint32_t which)
{ CHECK(which == 1); return di_info; }
uint32_t rfw_deep_ownership(void)
{ return RFW_DEEP_ENABLED && di_owner && rfw_rpc8_preflight(); }

static uint8_t *di_at(uint32_t address)
{
#if RFW_DEEP_ENABLED
    unsigned i;
    for (i = 0; i < RFW_DEEP_ROWS; ++i) {
        unsigned aligned = (rfw_deep_rows[i].bytes + 1u) & ~1u;
        if (address >= rfw_deep_rows[i].address &&
            address + 2 <= rfw_deep_rows[i].address + aligned)
            return &di_ram[i][1 + address - rfw_deep_rows[i].address];
    }
#else
    (void)address;
#endif
    CHECK(0); return NULL;
}

int32_t rfw_rpc8_native(uint32_t letter, uint32_t value)
{
    uint8_t *p;
    int32_t result;
    CHECK(letter >= 21 && letter <= 23);
    ++di_calls; ++di_letters[letter];
    di_order[(di_calls - 1) % 110] = letter;
    if (di_calls == di_fail) return -9;
    if (letter == 23) { di_base = value << 16; result = (int32_t)value; }
    else if (letter == 21) {
        di_cursor = di_base + (value & 65534);
        p = di_at(di_cursor); result = (p[0] << 8) | p[1];
    } else {
        p = di_at(di_cursor);
        if (di_calls != di_drop) { p[0] = (uint8_t)(value >> 8); p[1] = (uint8_t)value; }
        result = (p[0] << 8) | p[1]; ++di_writes;
        if (di_cursor == 0x2012fffe) ++di_crossed;
        di_cursor += 2;
    }
    if (di_calls == di_bad) result ^= 1;
    return di_calls == di_lost ? -1 : result;
}

static void di_reset(void)
{
    static const uint8_t id[8] = {'j','l','a','u','n','c','h',0};
    memset(di_info, 0, sizeof(di_info));
    memcpy(di_info + 4, id, 8); di_info[0x30] = 1; di_info[0x31] = 0x51;
    memset(di_ram, 0xa7, sizeof(di_ram));
#if RFW_DEEP_ENABLED
    {
        unsigned i;
        for (i = 0; i < RFW_DEEP_ROWS; ++i)
            memcpy(di_ram[i] + 1, rfw_deep_rows[i].data[0], rfw_deep_rows[i].bytes);
        di_ram[1][34] = 0x5c; /* Live neighbor differs from the image's zero. */
    }
#endif
    di_ready = 1; di_limit = 9; di_context = di_owner = 0;
    di_calls = di_writes = di_fail = di_lost = di_crossed = di_bad = di_drop = di_disconnect = 0;
    memset(di_letters, 0, sizeof(di_letters)); memset(di_order, 0, sizeof(di_order));
    di_base = di_cursor = 0; di_preview = -1;
}

#if RFW_DEEP_ENABLED
static const Rv1Recipe *di_key(unsigned profile)
{ return profile ? &rfw_defaults[rfw_deep_slots[profile - 1] - 1] : NULL; }

static void di_check(unsigned profile)
{
    unsigned i;
    for (i = 0; i < RFW_DEEP_ROWS; ++i) {
        const RfwDeepRow *r = &rfw_deep_rows[i];
        CHECK(memcmp(di_ram[i] + 1, r->data[profile], r->bytes) == 0);
        CHECK(di_ram[i][0] == 0xa7 && di_ram[i][((r->bytes + 1u) & ~1u) + 1] == 0xa7);
    }
    CHECK(di_ram[1][34] == 0x5c);
}
#endif

static void deep_before_preview(void)
{
    if (di_preview < 0) return;
#if RFW_DEEP_ENABLED
    di_check((unsigned)di_preview);
#endif
    CHECK(((RfwCache *)allocated_cache)->deep.active == di_preview);
    CHECK(((RfwCache *)allocated_cache)->deep.uncertain == 0);
}

static void canonical_library_tests(const char *path)
{
    Rv1Bank bank;
    unsigned i, profile;
    FILE *input;
    reset(); di_reset();
    input = fopen(path,"rb"); CHECK(input != NULL);
    CHECK(fread(files[0].bytes,1,1056,input) == 1056 && fgetc(input) == EOF);
    CHECK(fclose(input) == 0);
    CHECK(rv1_decode(files[0].bytes,1056,&bank,NULL) == RV1_OK);
    for (i = 0; i < 16; ++i) {
        CHECK(bank.slots[i].occupied == (i < 4));
        if (i < 4)
            CHECK(memcmp(&bank.slots[i].recipe,&rfw_defaults[i],sizeof(Rv1Recipe)) == 0);
    }
    files[0].length = 1056; files[0].exists = 1;
    CHECK(rfw_open() == 1);
    di_owner = 1;
    for (i = 1; i <= 4; ++i) {
        Rv1WritePlan plan;
        uint8_t expected[4096];
        const Rv1Recipe *r = &bank.slots[i - 1].recipe;
        profile = rfw_deep_id(r); di_preview = (int)profile;
        CHECK(rv1_plan(r,&plan) == RV1_OK);
        memcpy(expected,settings_a,sizeof(expected));
        for (unsigned j = 0; j < plan.count; ++j) expected[plan.writes[j].offset] = plan.writes[j].value;
        CHECK(rfw_select(i) == RV1_OK);
        CHECK(memcmp(settings_a,expected,sizeof(expected)) == 0);
        CHECK(settings_a[0x36e] == r->base_mode);
        CHECK(previews == (int)i);
#if RFW_DEEP_ENABLED
        di_check(profile);
#endif
    }
    for (i = 5; i <= 16; ++i) CHECK(rfw_select(i) == RV1_EMPTY);
    passed("four packaged recipes apply exact settings; empty slots 5..16 do not, and 04 restores stock");
    reset(); di_reset();
    CHECK(rfw_open() == 1);
    CHECK(((RfwCache *)allocated_cache)->load_status == RV1_OK);
    for (i = 0; i < 16; ++i) {
        CHECK(((RfwCache *)allocated_cache)->bank.slots[i].occupied == (i < 4));
        if (i < 4)
            CHECK(memcmp(&((RfwCache *)allocated_cache)->bank.slots[i].recipe,&rfw_defaults[i],sizeof(Rv1Recipe)) == 0);
    }
    passed("compiled defaults publish four recipes and leave slots 5..16 empty without DAT files");
    reset(); di_reset();
}

#if RFW_DEEP_ENABLED
static void load_pair(const char *path)
{
    FILE *input = fopen(path, "rb");
    CHECK(input != NULL);
    CHECK(fread(files[0].bytes, 1, 1056, input) == 1056 && fgetc(input) == EOF);
    CHECK(fclose(input) == 0);
    memcpy(files[1].bytes, files[0].bytes, 1056);
    files[0].exists = files[1].exists = 1;
    files[0].length = files[1].length = 1056;
}

static void real_card_bank_tests(const char *path)
{
    static const char *names[4] = {"01 Posi","02 Nega","03 HC BW","04 Std"};
    Rv1Bank bank;
    unsigned slot, deep_slots = 0, surface_slots = 0;
    int preview_at;
    reset(); di_reset();
    load_pair(path);
    CHECK(rv1_decode(files[0].bytes, 1056, &bank, NULL) == RV1_OK);
    CHECK(rv1_decode(files[1].bytes, 1056, &bank, NULL) == RV1_OK);
    for (slot = 0; slot < 16; ++slot) {
        CHECK(bank.slots[slot].occupied == (slot < 4));
        if (slot >= 4) continue;
        CHECK(bank.slots[slot].recipe.name_length == rfw_defaults[slot].name_length);
        CHECK(bank.slots[slot].recipe.name_length <= 8);
        CHECK(memcmp(&bank.slots[slot].recipe, &rfw_defaults[slot], sizeof(Rv1Recipe)) == 0);
        CHECK(memcmp(bank.slots[slot].recipe.name, names[slot], bank.slots[slot].recipe.name_length) == 0);
    }
    CHECK(rfw_open() >= 1);
    CHECK(((RfwCache *)allocated_cache)->load_status == RV1_OK);
    for (slot = 1; slot <= 4; ++slot) {
        Rv1WritePlan plan;
        uint8_t expected[4096];
        const Rv1Recipe *recipe = &bank.slots[slot - 1].recipe;
        unsigned id = rfw_deep_id(recipe);
        unsigned writes = di_writes;
        preview_at = previews;
        CHECK(rv1_plan(recipe, &plan) == RV1_OK);
        memcpy(expected, settings_a, sizeof(expected));
        for (unsigned j = 0; j < plan.count; ++j)
            expected[plan.writes[j].offset] = plan.writes[j].value;
        cursor = (uint8_t)slot;
        CHECK(rfw_cursor_commit() == 1);
        CHECK(((RfwCache *)allocated_cache)->last_status == RV1_OK);
        CHECK(previews == preview_at + 1);
        CHECK(memcmp(settings_a, expected, sizeof(expected)) == 0);
        CHECK(di_writes == writes);
        CHECK(((RfwCache *)allocated_cache)->deep.uncertain == 0);
        if (id != 0) {
            CHECK(((RfwCache *)allocated_cache)->deep.active == 0);
            ++deep_slots;
        } else ++surface_slots;
    }
    CHECK(deep_slots == 3 && surface_slots == 1);
    passed("real identical card banks preview slots 1..4 when deep preflight fails before W");
    di_owner = 1; di_preview = 1;
    cursor = 1; CHECK(rfw_cursor_commit() == 1); di_check(1);
    di_preview = -1;
    preview_at = previews;
    {
        uint8_t before[4096];
        unsigned calls;
        memcpy(before, settings_a, sizeof(before));
        di_lost = di_calls + 40;
        cursor = 2;
        calls = di_calls;
        CHECK(rfw_cursor_commit() == 1);
        CHECK(((RfwCache *)allocated_cache)->deep.uncertain == 1);
        CHECK(previews == preview_at && memcmp(before, settings_a, sizeof(before)) == 0);
        CHECK(di_calls > calls);
        calls = di_calls;
        cursor = 4; CHECK(rfw_cursor_commit() == 1 && di_calls == calls);
        CHECK(previews == preview_at && memcmp(before, settings_a, sizeof(before)) == 0);
    }
    passed("a mid-W failure stays fail-closed, consumes the key and does not retry");
    shooting_category = 1;
    ((RfwCache *)allocated_cache)->deep.uncertain = 0;
    ((RfwCache *)allocated_cache)->deep.active = 0;
    preview_at = previews;
    {
        uint8_t before[4096];
        memcpy(before, settings_a, sizeof(before));
        cursor = 4; CHECK(rfw_select(4) == RV1_CONFLICT && rfw_cursor_commit() == 1);
        CHECK(previews == preview_at && memcmp(before, settings_a, sizeof(before)) == 0);
    }
    shooting_category = 0;
    passed("a non-zero shooting category consumes the key without writing S or previewing");
    reset(); di_reset();
}

static void apply_visible(unsigned slot)
{
    Rv1WritePlan plan;
    uint8_t expected[4096];
    const Rv1Recipe *recipe = &((RfwCache *)allocated_cache)->bank.slots[slot - 1].recipe;
    unsigned j;
    int preview_at = previews;
    CHECK(rfw_is_active());
    CHECK(rv1_plan(recipe, &plan) == RV1_OK);
    memcpy(expected, settings_a, sizeof(expected));
    for (j = 0; j < plan.count; ++j)
        expected[plan.writes[j].offset] = plan.writes[j].value;
    CHECK(rfw_select(slot) == RV1_OK);
    CHECK(((RfwCache *)allocated_cache)->last_status == RV1_OK);
    CHECK(previews == preview_at + 1);
    CHECK(memcmp(settings_a, expected, sizeof(expected)) == 0);
}

static void category_gate_tests(const char *path)
{
    static const uint8_t allowed[] = {0, 4};
    static const uint8_t rejected[] = {1, 2, 3, 7, 255};
    unsigned i, slot, deep_slots = 0, surface_slots = 0;
    int preview_at;
    uint8_t before[4096];
    Rv1Bank bank;
    for (i = 0; i < 2; ++i) {
        unsigned writes;
        reset(); di_reset();
        load_pair(path);
        CHECK(rfw_open() >= 1);
        CHECK(rfw_is_active());
        shooting_category = allowed[i];
        CHECK(rfw_deep_id(&((RfwCache *)allocated_cache)->bank.slots[3].recipe) == 0);
        apply_visible(4);
        CHECK(di_calls == 0 && di_writes == 0);
        CHECK(((RfwCache *)allocated_cache)->deep.active == 0);
        CHECK(((RfwCache *)allocated_cache)->deep.uncertain == 0);
        writes = di_writes;
        CHECK(rfw_deep_id(&((RfwCache *)allocated_cache)->bank.slots[0].recipe) == 1);
        apply_visible(1);
        CHECK(di_calls == 0 && di_writes == writes);
        CHECK(((RfwCache *)allocated_cache)->deep.active == 0);
        CHECK(((RfwCache *)allocated_cache)->deep.uncertain == 0);
    }
    passed("K=0 and K=4 apply a surface slot and a deep slot when preflight fails before W");
    for (i = 0; i < 2; ++i) {
        reset(); di_reset();
        load_pair(path);
        CHECK(rfw_open() >= 1);
        CHECK(rfw_is_active());
        shooting_category = allowed[i];
        di_owner = 1;
        di_preview = 1;
        apply_visible(1);
        di_check(1);
        CHECK(di_calls == 104 && di_writes == 96 && di_crossed == 1);
        CHECK(((RfwCache *)allocated_cache)->deep.active == 1);
        CHECK(((RfwCache *)allocated_cache)->deep.uncertain == 0);
        di_preview = -1;
    }
    passed("K=0 and K=4 deep success writes the profile and requests one preview");
    reset(); di_reset();
    load_pair(path);
    CHECK(rfw_open() >= 1);
    CHECK(rfw_is_active());
    memcpy(before, settings_a, sizeof(before));
    preview_at = previews;
    for (i = 0; i < 5; ++i) {
        shooting_category = rejected[i];
        cursor = 1;
        CHECK(rfw_select(1) == RV1_CONFLICT);
        CHECK(rfw_cursor_commit() == 1);
        cursor = 4;
        CHECK(rfw_select(4) == RV1_CONFLICT && rfw_cursor_commit() == 1);
        cursor = 16;
        CHECK(rfw_select(16) == RV1_EMPTY && rfw_cursor_commit() == 1);
        CHECK(previews == preview_at && memcmp(before, settings_a, sizeof(before)) == 0);
        CHECK(((RfwCache *)allocated_cache)->busy == 0);
    }
    shooting_category = 0;
    passed("K=1, 2, 3, 7 and 255 stay CONFLICT with S unchanged, no preview, and commit returns 1");
    reset(); di_reset();
    load_pair(path);
    CHECK(rv1_decode(files[0].bytes, 1056, &bank, NULL) == RV1_OK);
    for (slot = 0; slot < 16; ++slot) {
        CHECK(bank.slots[slot].occupied == (slot < 4));
        if (slot < 4)
            CHECK(memcmp(&bank.slots[slot].recipe, &rfw_defaults[slot], sizeof(Rv1Recipe)) == 0);
    }
    shooting_category = 4;
    CHECK(rfw_open() >= 1);
    CHECK(rfw_is_active());
    CHECK(((RfwCache *)allocated_cache)->load_status == RV1_OK);
    for (slot = 1; slot <= 4; ++slot) {
        unsigned id = rfw_deep_id(&bank.slots[slot - 1].recipe);
        unsigned writes = di_writes;
        apply_visible(slot);
        CHECK(di_writes == writes);
        CHECK(((RfwCache *)allocated_cache)->deep.uncertain == 0);
        if (id != 0) {
            CHECK(((RfwCache *)allocated_cache)->deep.active == 0);
            ++deep_slots;
        } else ++surface_slots;
    }
    CHECK(deep_slots == 3 && surface_slots == 1);
    CHECK(shooting_category == 4 && di_calls == 0);
    passed("real card bank with K=4 applies and previews slots 1 through 4");
    reset(); di_reset();
}
#endif

#if RFW_DEEP_ENABLED
static void phase1_list_tests(const char *path);
#endif

static void deep_tests(const char *library_path)
{
    unsigned i;
    di_reset();
    CHECK(sizeof(Rv1Recipe) == 49);
    CHECK(rfw_rpc8_call(20,0) == -32768 && rfw_rpc8_call(24,0) == -32768);
    CHECK(rfw_rpc8_call(23,65536) == -32768);
    di_context = 1; CHECK(!rfw_rpc8_preflight()); di_context = 0;
    di_ready = 0; CHECK(!rfw_rpc8_preflight()); di_ready = 1;
    di_limit = 8; CHECK(!rfw_rpc8_preflight()); di_limit = 9;
    for (i = 4; i < 12; ++i) {
        di_info[i] ^= 1; CHECK(!rfw_rpc8_preflight()); di_info[i] ^= 1;
    }
    for (i = 0x30; i < 0x34; ++i) {
        di_info[i] ^= 1; CHECK(!rfw_rpc8_preflight()); di_info[i] ^= 1;
    }
    CHECK(di_calls == 0 && di_writes == 0 && rfw_rpc8_preflight());
    CHECK(rfw_rpc8_call(23,0x2012) == 0x2012 && di_calls == 1);
    passed("RPC8 preflight checks every unit-name and MAIN-version byte plus context link and limit");
#if RFW_DEEP_ENABLED
    {
        RfwDeepState state;
        Rv1Recipe key;
        unsigned profile, from, to, total, write_calls[96], count = 0;
        uint8_t before[4096];
        int preview_count;
        CHECK(rfw_deep_id(NULL) == 0);
        for (profile = 1; profile <= RFW_DEEP_PROFILES; ++profile) {
            CHECK(rfw_deep_id(di_key(profile)) == profile);
            for (i = 0; i < sizeof(key); ++i) {
                key = *di_key(profile); ((uint8_t *)&key)[i] ^= 1;
                CHECK(rfw_deep_id(&key) == 0);
            }
        }
        passed("all three deep identities require every canonical name mode raw and WB byte");
        di_reset(); state = (RfwDeepState){0};
        CHECK(rfw_deep_transition(&state,NULL) == RV1_OK && di_calls == 0);
        CHECK(rfw_deep_transition(&state,di_key(1)) == RV1_CONFLICT && di_calls == 0);
        di_owner = 1;
        CHECK(rfw_deep_transition(&state,di_key(1)) == RV1_OK);
        di_check(1); CHECK(state.active == 1 && !state.uncertain && state.neighbor == 0x5c);
        CHECK(di_calls == 104 && di_writes == 96 && di_crossed == 1);
        CHECK(di_letters[21] == 4 && di_letters[23] == 4);
        for (i = 0; i < 104; ++i) if (di_order[i] == 22) write_calls[count++] = i+1;
        CHECK(count == 96);
        total = di_calls;
        CHECK(rfw_deep_transition(&state,di_key(1)) == RV1_OK && di_calls == total);
        CHECK(rfw_deep_transition(&state,NULL) == RV1_OK);
        di_check(0); CHECK(state.active == 0 && di_calls - total == 102 && di_writes == 192);
        CHECK(di_letters[21] == 7 && di_letters[23] == 7);
        passed("streamed 31+17+48 W readbacks use 104 cold and 102 warm RPCs and preserve the live B6 neighbor");
        for (from = 0; from <= RFW_DEEP_PROFILES; ++from) for (to = 0; to <= RFW_DEEP_PROFILES; ++to) {
            di_reset(); di_owner = 1; state = (RfwDeepState){0};
            CHECK(rfw_deep_transition(&state,di_key(from)) == RV1_OK);
            CHECK(rfw_deep_transition(&state,di_key(to)) == RV1_OK);
            di_check(to); CHECK(state.active == to);
        }
        passed("all 16 stock Posi Nega and HC transitions restore or replace all three source rows");
        di_reset(); di_owner = 1; state = (RfwDeepState){0}; di_ram[0][1] ^= 1;
        CHECK(rfw_deep_transition(&state,di_key(1)) == RV1_CONFLICT && di_writes == 0 && !state.uncertain);
        di_reset(); di_owner = 1; state = (RfwDeepState){0}; di_ram[1][33] ^= 1;
        CHECK(rfw_deep_transition(&state,di_key(1)) == RV1_CONFLICT && di_writes == 0);
        passed("first A5 halfword and B5 tail mismatch reject before the first W");
        for (unsigned fault = 0; fault < 3; ++fault) for (i = 1; i <= 104; ++i) {
            di_reset(); di_owner = 1; state = (RfwDeepState){0};
            if (fault == 0) di_lost = i;
            if (fault == 1) di_fail = i;
            if (fault == 2) di_disconnect = i - 1;
            if (fault == 2 && i == 1) di_ready = 0;
            CHECK(rfw_deep_transition(&state,di_key(1)) == RV1_CONFLICT);
            if (state.uncertain) {
                unsigned calls = di_calls;
                CHECK(rfw_deep_transition(&state,NULL) == RV1_CONFLICT && di_calls == calls);
            } else CHECK(di_writes == 0);
        }
        passed("all 104 cold RPC positions reject lost replies preexecution failures and link loss without replaying W");
        for (i = 0; i < 96; ++i) {
            di_reset(); di_owner = 1; state = (RfwDeepState){0}; di_bad = write_calls[i];
            CHECK(rfw_deep_transition(&state,di_key(1)) == RV1_CONFLICT && state.uncertain);
            CHECK(di_calls == write_calls[i]);
        }
        passed("each of the 96 W responses is checked immediately and a false readback stops the stream");
        di_reset(); di_owner = 1; state = (RfwDeepState){0}; di_drop = 7;
        CHECK(rfw_deep_transition(&state,di_key(1)) == RV1_CONFLICT && state.uncertain && di_writes == 3);
        passed("a failed actual store with native memory readback cannot publish success");
        for (i = 1; i <= 102; ++i) {
            di_reset(); di_owner = 1; state = (RfwDeepState){0};
            CHECK(rfw_deep_transition(&state,di_key(1)) == RV1_OK);
            di_lost = di_calls + i;
            CHECK(rfw_deep_transition(&state,NULL) == RV1_CONFLICT && state.active == 1);
            if (state.uncertain) {
                unsigned calls = di_calls;
                CHECK(rfw_deep_transition(&state,di_key(2)) == RV1_CONFLICT && di_calls == calls);
            }
        }
        passed("all 102 warm restore reply losses fail closed and preserve the previous committed profile identity");
        reset(); di_reset();
        memcpy(files[0].bytes, (const uint8_t[1056]){0},1056);
        {
            FILE *input = fopen(library_path,"rb"); CHECK(input != NULL);
            CHECK(fread(files[0].bytes,1,1056,input) == 1056 && fclose(input) == 0);
        }
        files[0].length = 1056; files[0].exists = 1;
        CHECK(rfw_open() == 1 && rfw_select(4) == RV1_OK);
        preview_count = previews;
        CHECK(rfw_select(1) == RV1_OK && di_calls == 0 && di_writes == 0);
        CHECK(previews == preview_count + 1);
        CHECK(((RfwCache *)allocated_cache)->deep.uncertain == 0);
        CHECK(((RfwCache *)allocated_cache)->deep.active == 0);
        di_owner = 1; di_preview = 1;
        CHECK(rfw_select(1) == RV1_OK); di_check(1);
        rfw_close(); CHECK(rfw_open() == 1);
        CHECK(((RfwCache *)allocated_cache)->deep.active == 1);
        di_preview = 0;
        CHECK(rfw_select(4) == RV1_OK && settings_a[0x36e] == 1); di_check(0);
        di_preview = -1; di_lost = di_calls + 40;
        memcpy(before,settings_a,sizeof(before)); preview_count = previews;
        CHECK(rfw_select(2) == RV1_CONFLICT && ((RfwCache *)allocated_cache)->deep.uncertain);
        CHECK(memcmp(before,settings_a,sizeof(before)) == 0 && previews == preview_count);
        total = di_calls;
        rfw_close(); (void)rfw_open();
        CHECK(rfw_select(4) == RV1_CONFLICT && di_calls == total);
        cursor = 4; CHECK(rfw_cursor_commit() == 1 && di_calls == total && previews == preview_count);
        passed("ADJ denial and uncertain transfer leave all S bytes and preview unchanged across close and reopen");
        real_card_bank_tests(library_path);
        category_gate_tests(library_path);
        phase1_list_tests(library_path);
    }
#else
    {
        RfwDeepState state = {0};
        for (i = 0; i < 16; ++i) {
            CHECK(rfw_deep_id(&rfw_defaults[i]) == 0);
            CHECK(rfw_deep_transition(&state,&rfw_defaults[i]) == RV1_OK);
        }
        CHECK(!rfw_deep_ownership() && di_writes == 0 && di_calls == 1);
        passed("safe build treats all Canonical slots as native surface recipes and emits zero deep writes");
    }
#endif
    canonical_library_tests(library_path);
    di_reset(); reset();
}

static void legacy_canonical_test(const char *path)
{
    /* v1 has no mode 0x01, so 04 Std is absent. HC is stored as color:
     * contrast display 5, sharpness display 6, vividness display 1. */
    uint8_t bytes[1056];
    Rv1Bank bank;
    unsigned i, j;
    FILE *input = fopen(path,"rb");
    CHECK(input != NULL && fread(bytes,1,1056,input) == 1056);
    CHECK(fgetc(input) == EOF && fclose(input) == 0);
    CHECK(rv1_decode(bytes,sizeof(bytes),&bank,NULL) == RV1_VERSION);
    CHECK(rv1_import_v1(bytes,sizeof(bytes),&bank) == RV1_OK);
    for (i = 0; i < 3; ++i) {
        Rv1Recipe *r = &bank.slots[i].recipe;
        CHECK(bank.slots[i].occupied && r->base_mode == 4);
        CHECK(r->name_length == rfw_defaults[i].name_length);
        CHECK(memcmp(r->name,rfw_defaults[i].name,32) == 0);
        CHECK(r->raw[0] == 3 && r->raw[1] == (i == 2 ? 4 : 3));
        CHECK(r->raw[2] == (i == 2 ? 7 : 3));
        for (j = 3; j < 13; ++j) CHECK(r->raw[j] == 3);
        CHECK(r->wb[0] == 0 && r->wb[1] == 0);
    }
    for (i = 3; i < 16; ++i) CHECK(!bank.slots[i].occupied);
    CHECK(bank.slots[2].recipe.base_mode == 4);
    passed("v1 companion imports three color degradations, omits native Standard, and cannot masquerade as v2 BW");
}

#if RFW_DEEP_ENABLED
static int curve_ok(const uint8_t *inputs, const uint8_t *outputs)
{
    unsigned i;
    uint16_t previous = (uint16_t)((inputs[0] << 8) | inputs[1]);
    if (previous < 1 || previous > 4094) return 0;
    for (i = 1; i < 31; ++i) {
        uint16_t value = (uint16_t)((inputs[i * 2] << 8) | inputs[i * 2 + 1]);
        if (value <= previous || value > 4094) return 0;
        previous = value;
    }
    for (i = 1; i < 33; ++i) if (outputs[i] < outputs[i - 1]) return 0;
    return 1;
}

static void phase1_list_tests(const char *path)
{
    static const unsigned order[] = {4, 1, 2, 4, 3, 4};
    static const unsigned profile[] = {0, 1, 2, 0, 3, 0};
    unsigned n, i;
    uint8_t before[4096];
    reset(); di_reset(); di_owner = 1;
    load_pair(path);
    CHECK(rfw_open() == 1);
    for (n = 0; n < 6; ++n) {
        const Rv1Recipe *recipe = &rfw_defaults[order[n] - 1];
        Rv1WritePlan plan;
        uint8_t expected[4096];
        di_preview = (int)profile[n];
        CHECK(rv1_plan(recipe, &plan) == RV1_OK);
        memcpy(expected, settings_a, sizeof(expected));
        for (i = 0; i < plan.count; ++i)
            expected[plan.writes[i].offset] = plan.writes[i].value;
        cursor = (uint8_t)order[n];
        CHECK(rfw_cursor_commit() == 1);
        CHECK(((RfwCache *)allocated_cache)->last_status == RV1_OK);
        CHECK(memcmp(settings_a, expected, sizeof(expected)) == 0);
        CHECK(settings_a[0x36e] == recipe->base_mode);
        di_check(profile[n]);
        rfw_close();
        CHECK(rfw_open() == order[n]);
    }
    passed("cursor 1..4 reopens on the selected row, including native Standard");
    /* Fresh cache, selector 0x01 and WB 0,0. Colour bytes are not part of the plan. */
    reset(); di_reset(); load_pair(path);
    settings_a[0x36e] = 1; settings_a[0x6dd] = 9; settings_a[0x6de] = 9;
    CHECK(rfw_open() == 4);
    passed("reopen highlights 04 when S+0x36E is native Standard and WB is 0,0");
    reset(); di_reset(); di_owner = 1; load_pair(path);
    CHECK(rfw_open() >= 1);
    memcpy(before, settings_a, sizeof(before));
    di_preview = 3;
    CHECK(rfw_select(3) == RV1_OK);
    CHECK(settings_a[0x36e] == 3 && settings_a[0x645] == 3 && settings_a[0x646] == 4);
    CHECK(settings_a[0x6dd] == 9 && settings_a[0x6de] == 9);
    CHECK(settings_a[0x36f] == before[0x36f] && settings_a[0x8ac] == before[0x8ac]);
    di_check(3);
    memcpy(before, settings_a, sizeof(before));
    di_preview = 0;
    CHECK(rfw_select(4) == RV1_OK);
    CHECK(settings_a[0x36e] == 1 && settings_a[0x6dd] == 9 && settings_a[0x6de] == 9);
    CHECK(settings_a[0x36f] == before[0x36f] && settings_a[0x370] == before[0x370]);
    CHECK(settings_a[0x8ac] == before[0x8ac] && settings_a[0x645] == before[0x645]);
    di_check(0);
    passed("HC publishes B&W 0x03 and 04 publishes 0x01 without writing colour fields");
    for (i = 0; i < 4; ++i)
        CHECK(curve_ok(rfw_deep_rows[0].data[i], rfw_deep_rows[1].data[i]));
    passed("stock Posi Nega and HC tone curves are strictly increasing and in range");
    reset(); di_reset();
}
#endif
