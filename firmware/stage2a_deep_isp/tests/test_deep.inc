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
        CHECK(bank.slots[i].occupied);
        CHECK(memcmp(&bank.slots[i].recipe,&rfw_defaults[i],sizeof(Rv1Recipe)) == 0);
    }
    files[0].length = 1056; files[0].exists = 1;
    CHECK(rfw_open() == 1);
    di_owner = 1;
    for (i = 1; i <= 16; ++i) {
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
    passed("all 16 packaged Canonical recipes apply exact settings, native BW/TE and stock restoration before preview");
    reset(); di_reset();
    CHECK(rfw_open() == 1);
    CHECK(((RfwCache *)allocated_cache)->load_status == RV1_OK);
    for (i = 0; i < 16; ++i)
        CHECK(memcmp(&((RfwCache *)allocated_cache)->bank.slots[i].recipe,&rfw_defaults[i],sizeof(Rv1Recipe)) == 0);
    passed("compiled initial 16-slot Canonical bank remains available without DAT files");
    reset(); di_reset();
}

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
        for (profile = 1; profile <= 4; ++profile) {
            CHECK(rfw_deep_id(di_key(profile)) == profile);
            for (i = 0; i < sizeof(key); ++i) {
                key = *di_key(profile); ((uint8_t *)&key)[i] ^= 1;
                CHECK(rfw_deep_id(&key) == 0);
            }
        }
        passed("all four deep identities require every canonical name mode raw and WB byte");
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
        for (from = 0; from <= 4; ++from) for (to = 0; to <= 4; ++to) {
            di_reset(); di_owner = 1; state = (RfwDeepState){0};
            CHECK(rfw_deep_transition(&state,di_key(from)) == RV1_OK);
            CHECK(rfw_deep_transition(&state,di_key(to)) == RV1_OK);
            di_check(to); CHECK(state.active == to);
        }
        passed("all 25 stock and four-profile transitions restore or replace all three source rows");
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
        memcpy(before,settings_a,sizeof(before)); preview_count = previews;
        CHECK(rfw_select(1) == RV1_CONFLICT && di_calls == 0);
        CHECK(memcmp(before,settings_a,sizeof(before)) == 0 && previews == preview_count);
        di_owner = 1; di_preview = 1;
        CHECK(rfw_select(1) == RV1_OK); di_check(1);
        rfw_close(); CHECK(rfw_open() == 1);
        CHECK(((RfwCache *)allocated_cache)->deep.active == 1);
        di_preview = 0;
        CHECK(rfw_select(6) == RV1_OK && settings_a[0x36e] == 3); di_check(0);
        di_preview = -1; di_lost = di_calls + 40;
        memcpy(before,settings_a,sizeof(before)); preview_count = previews;
        CHECK(rfw_select(2) == RV1_CONFLICT && ((RfwCache *)allocated_cache)->deep.uncertain);
        CHECK(memcmp(before,settings_a,sizeof(before)) == 0 && previews == preview_count);
        total = di_calls;
        rfw_close(); (void)rfw_open();
        CHECK(rfw_select(4) == RV1_CONFLICT && di_calls == total);
        passed("ADJ denial and uncertain transfer leave all S bytes and preview unchanged across close and reopen");
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
    static const uint8_t contrast[16] = {1,1,9,3,8,7,3,3,3,4,3,3,3,3,3,3};
    static const uint8_t sharpness[16] = {3,3,4,3,3,2,3,3,3,3,3,3,3,3,3,3};
    static const uint8_t mono[16] = {0,0,1,0,0,1,1,1,0,0,0,1,0,0,1,1};
    uint8_t bytes[1056];
    Rv1Bank bank;
    FILE *input = fopen(path,"rb");
    CHECK(input != NULL && fread(bytes,1,1056,input) == 1056);
    CHECK(fgetc(input) == EOF && fclose(input) == 0);
    CHECK(rv1_decode(bytes,sizeof(bytes),&bank,NULL) == RV1_VERSION);
    CHECK(rv1_import_v1(bytes,sizeof(bytes),&bank) == RV1_OK);
    for (unsigned i = 0; i < 16; ++i) {
        Rv1Recipe *r = &bank.slots[i].recipe;
        CHECK(bank.slots[i].occupied && r->base_mode == 4);
        CHECK(r->name_length == rfw_defaults[i].name_length);
        CHECK(memcmp(r->name,rfw_defaults[i].name,32) == 0);
        CHECK(r->raw[0] == contrast[i] && r->raw[1] == sharpness[i]);
        CHECK(r->raw[2] == (mono[i] ? 7 : 3));
        for (unsigned j = 3; j < 13; ++j) CHECK(r->raw[j] == 3);
        CHECK(r->wb[0] == 0 && r->wb[1] == 0);
    }
    passed("v1 companion imports 16 names with explicit color-only degradation and cannot masquerade as v2 BW or TE");
}
