#ifndef PN_GXTS_H
#define PN_GXTS_H
#include "panel_store.h"
#include "../../card_container_v2/gxts.h"
typedef struct {
    PsStore *store;
    GxtsBinding binding;
    EngRecipeRef recipe;
    GxtsIO io;
    GxtsSelection selection;
    uint8_t param_index[6], loaded, used_defaults;
    uint8_t valid_mask, active_copy, eof, read_failed;
    uint32_t generation[2], preserve, token, captured;
    uint8_t capture[257];
} PnGxts;
/* Compile upstream gxts.c with gxr2_sha256=pn_gxts_crc_field. The unchanged
 * 240 B GXTS serializer stores CRC32 + 28 zero bytes in digest-shaped fields. */
void pn_gxts_crc_field(const uint8_t *,size_t,uint8_t [32]);
int32_t pn_gxts_bind(PnGxts *,PsStore *,const Gxr2View *,const EngRecipeRef *,const uint8_t[6]);
int32_t pn_gxts_attach(PnGxts *,PsStore *,const GxtsBinding *,const EngRecipeRef *,const uint8_t[6]);
/* Missing invokes gxts_defaults, returns OK and sets used_defaults. */
int32_t pn_gxts_load(PnGxts *,EngTweak *);
int32_t pn_gxts_save(void *,const EngRecipeRef *,const EngTweak *);
#endif
