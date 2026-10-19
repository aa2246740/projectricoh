#include "probe_logic.h"

extern uint8_t probe_glyphs[16][96];

void gxr_ascii(const char *text, uint32_t length, uint8_t *cell, uint32_t language);
uint32_t gxr_language(void);
void gxr_list_paint(uint32_t layer, uint32_t state, uint32_t flags);

static uint32_t text_length(const char *text)
{
    uint32_t n = 0;
    while (text[n] != 0 && n < 15u) n++;
    return n;
}

/* Sample the five gate inputs, format 16 rows into probe_glyphs, then redraw.
 * Writes are the glyph cells and the reentry byte. The painter runs only
 * after the text is already in the cells. */
uint32_t gate_probe_render_body(void)
{
    ProbeView view;
    char text[16];
    volatile uint8_t *cell = &probe_glyphs[0][0];
    uint32_t language;
    unsigned row;

    if (probe_load_u8(PROBE_ADDR_REENTRY) != 0) return 0;
    probe_store_u8(PROBE_ADDR_REENTRY, 1);

    view.word = probe_load_u32(PROBE_ADDR_WORD);
    view.type = probe_load_u8(PROBE_ADDR_TYPE);
    view.part = probe_load_u8(PROBE_ADDR_PART);
    view.count = probe_load_u8(PROBE_ADDR_COUNT);
    view.entries = probe_load_u32(PROBE_ADDR_ENTRIES);
    view.state = 0;
    view.verdict = 0;
    view.tag = 0;
    view.dereferenced = 0;
    probe_decide(&view);

    language = gxr_language();
    for (row = 0; row < PROBE_ROWS; ++row) {
        uint32_t k;
        uint32_t length;
        probe_format_row(row, &view, text);
        for (k = 0; k < PROBE_GLYPH_BYTES; ++k) cell[k] = 0;
        length = text_length(text);
        cell[0] = 0;
        gxr_ascii(text, length, (uint8_t *)cell, language);
        if (cell[0] == 0) {
            for (k = 0; k <= length && k < PROBE_GLYPH_BYTES; ++k)
                cell[k] = (uint8_t)text[k];
        }
        cell += PROBE_GLYPH_BYTES;
    }
    gxr_list_paint(2, PROBE_ADDR_TYPE, 0);
    probe_store_u8(PROBE_ADDR_REENTRY, 0);
    return 0;
}
