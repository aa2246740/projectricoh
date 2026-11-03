#ifndef PN_PANEL_H
#define PN_PANEL_H
#include "panel_store.h"

enum { PN_ROWS=9, PN_COLUMNS=8, PN_GLYPH_BYTES=18, PN_NATIVE_BYTES=32 };
typedef enum { PN_PRESS, PN_RELEASE, PN_REPEAT } PnKeyPhase;
typedef enum {
    PN_HALF_SHUTTER, PN_MENU_CLOSE, PN_MY_RECALL, PN_SLEEP, PN_POWER_OFF,
    PN_UNIT_CHANGE, PN_LINK_CHANGE, PN_VIEW_REBUILT, PN_STORAGE_INVALIDATED
} PnNotice;
typedef struct {
    uint32_t native_state, activity, array, count, top_tag, top_state;
    uint32_t opener;
} PnOpenView;

typedef struct {
    uint8_t state[PN_NATIVE_BYTES];
    uint8_t type_descriptors[6][12], details[PN_ROWS][12];
    uint32_t labels[PN_ROWS], glyph_refs[PN_ROWS];
} PnNativeList;
/* Native descriptor/state bytes are NOT specified by abi.h. A reviewed native
 * builder must construct the type-5 object from the nine glyph addresses.
 * No firmware template or guessed native layout is embedded in this module. */
typedef int32_t (*PnBuildNative)(void *, PnPort *, PnNativeList *,
                                const uint32_t glyphs[PN_ROWS], uint8_t cursor);
typedef struct {
    const uint8_t *state, *type_descriptors, *details;
    uint32_t state_bytes, descriptor_bytes, detail_bytes;
} PnNativeSeed;
/* Source templates are supplied by a reviewed resident adapter, held in an
 * owned stable lease. The nine detail records must also be independently valid.
 * Raw firmware bytes are never embedded here. Unknown template fields survive. */
int32_t pn_native_from_seed(void *, PnPort *, PnNativeList *,
                            const uint32_t glyphs[PN_ROWS], uint8_t cursor);
typedef int32_t (*PnSaveTweak)(void *, const EngRecipeRef *, const EngTweak *);
typedef struct {
    PnBuildNative build;
    void *build_context;
    PnSaveTweak save;
    void *save_context;
    const uint8_t *param_index; /* Six metadata-vector indices for IDs 1..6. */
} PnPanelOps;

typedef struct {
    PnPort *port;
    PnPanelOps ops;
    EngRecipeRef recipe;
    EngTweak committed, draft;
    uint8_t param_index[6];
    int8_t min[ENG_PARAMS], max[ENG_PARAMS], def[ENG_PARAMS];
    uint8_t open, input_enabled, armed, cursor, unknown, commit_uncertain;
    uint8_t preview_attempted, dirty, bound, view_owned, ui_pinned, busy;
    uint8_t stop_requested, stop_after_invalid;
    uint32_t opener, view_token;
    int32_t last_io, last_store;
    EngStatus last_engine;
    char text[PN_ROWS][PN_COLUMNS+1];
    _Alignas(4) uint8_t glyph[PN_ROWS][20];
    PnNativeList native;
    RvUiList list;
    RvUiView view;
    RvUiText text_request;
} PnPanel;

void pn_panel_init(PnPanel *, PnPort *, const PnPanelOps *);
int32_t pn_panel_open(PnPanel *, const PnOpenView *);
int32_t pn_panel_event(PnPanel *, uint32_t logical_event, PnKeyPhase);
/* Safe notices must precede MY/S/unit/view/heap invalidation. after_invalid=1
 * forbids applying an old snapshot and leaves UNKNOWN if a draft was active. */
int32_t pn_panel_notify(PnPanel *, PnNotice, int after_invalid);
int32_t pn_panel_cancel(PnPanel *);
int pn_panel_native_result(int32_t result); /* PASS requires native replay. */

int32_t pn_ui_render(PnPanel *, int initial);
int32_t pn_ui_detach(PnPanel *);
#endif
