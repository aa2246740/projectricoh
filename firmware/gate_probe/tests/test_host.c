#include <stdio.h>
#include <string.h>
#define PROBE_HOST 1
#include "../probe_logic.h"

static int loads;
static int fail_on_load;
static uint32_t expect_tag_addr;
static uint32_t expect_state_addr;
static uint8_t canned_tag;
static uint32_t canned_state;
static int failures;

uint8_t probe_load_u8(uint32_t address)
{
    loads++;
    if (fail_on_load || address != expect_tag_addr) {
        fprintf(stderr, "unexpected u8 load %08x\n", address);
        failures++;
        return 0;
    }
    return canned_tag;
}

uint32_t probe_load_u32(uint32_t address)
{
    loads++;
    if (fail_on_load || address != expect_state_addr) {
        fprintf(stderr, "unexpected u32 load %08x\n", address);
        failures++;
        return 0;
    }
    return canned_state;
}

static void expect_eq(const char *name, int cond)
{
    if (!cond) {
        fprintf(stderr, "FAIL %s\n", name);
        failures++;
    }
}

static ProbeView base_view(void)
{
    ProbeView view;
    memset(&view, 0, sizeof view);
    view.word = 8;
    view.type = 5;
    view.part = 2;
    view.count = 1;
    view.entries = 0x205a279c;
    return view;
}

static void check_no_read(const char *name, ProbeView view)
{
    loads = 0;
    fail_on_load = 1;
    probe_decide(&view);
    expect_eq(name, loads == 0 && view.dereferenced == 0 && view.verdict == 0);
}

static void check_read(const char *name, ProbeView view, uint8_t tag, uint32_t state, int pass)
{
    uint32_t ent = view.entries + (uint32_t)(view.count - 1u) * 8u;
    loads = 0;
    fail_on_load = 0;
    expect_tag_addr = ent;
    expect_state_addr = ent + 4u;
    canned_tag = tag;
    canned_state = state;
    probe_decide(&view);
    expect_eq(name, loads == 2 && view.dereferenced == 1 && view.tag == tag &&
              view.state == state && view.verdict == (pass ? 1u : 0u));
}

static void check_row(unsigned row, const ProbeView *view, const char *want)
{
    char out[16];
    probe_format_row(row, view, out);
    if (strcmp(out, want) != 0) {
        fprintf(stderr, "FAIL row %u got [%s] want [%s]\n", row, out, want);
        failures++;
    }
}

int main(void)
{
    ProbeView view = base_view();
    unsigned row;
    check_read("pass", view, 33, 0x2022f71c, 1);
    view = base_view(); view.word = 7; check_no_read("word", view);
    view = base_view(); view.word = 0x00000108u; check_no_read("word-wide", view);
    view = base_view(); view.part = 0; check_no_read("part0", view);
    view = base_view(); view.part = 4; check_no_read("part4", view);
    view = base_view(); view.part = 1; check_no_read("part1", view);
    view = base_view(); view.count = 0; check_no_read("count0", view);
    view = base_view(); view.count = 3; check_no_read("count3", view);
    view = base_view(); view.count = 255; check_no_read("count255", view);
    view = base_view(); view.type = 4; check_no_read("type", view);
    view = base_view(); view.entries = 0; check_no_read("null", view);
    view = base_view(); view.entries = 0x205a279d; check_no_read("unaligned", view);
    view = base_view(); view.entries = 0x2059fffc; check_no_read("below", view);
    view = base_view(); view.entries = 0x205c0000; check_no_read("at-end", view);
    view = base_view(); view.entries = 0x205c0004; check_no_read("above", view);
    view = base_view(); view.entries = 0x205a0000; check_read("lo-edge", view, 33, 0x2022f71c, 1);
    view = base_view(); view.entries = 0x205bfffc; check_read("hi-edge", view, 1, 0, 0);
    view = base_view(); view.count = 2; view.entries = 0x205a279c;
    check_read("count2", view, 33, 0x2022f71c, 1);
    view = base_view(); check_read("bad-tag", view, 32, 0x2022f71c, 0);
    view = base_view(); check_read("bad-state", view, 33, 0x2022f71d, 0);

    view = base_view();
    view.dereferenced = 1;
    view.tag = 33;
    view.state = 0x2022f71c;
    view.verdict = 1;
    check_row(0, &view, "A=08");
    check_row(1, &view, "T=05");
    check_row(2, &view, "P=02");
    check_row(3, &view, "C=01");
    check_row(4, &view, "G0=21");
    check_row(5, &view, "S=2022F71C");
    check_row(6, &view, "V=01");
    check_row(7, &view, "W=00000008");
    check_row(8, &view, "E=205A279C");
    for (row = 9; row < 16; ++row) check_row(row, &view, "........");
    view.word = 0x00000100;
    check_row(0, &view, "A=00");
    check_row(7, &view, "W=00000100");
    view.dereferenced = 0;
    view.verdict = 0;
    view.entries = 0;
    check_row(4, &view, "G0=--");
    check_row(5, &view, "S=--------");
    check_row(6, &view, "V=00");
    check_row(8, &view, "E=00000000");
    if (failures) {
        fprintf(stderr, "%d failures\n", failures);
        return 1;
    }
    puts("host-ok");
    return 0;
}
