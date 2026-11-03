/* Emits the RfwCache field offsets the assembly modules use, computed by the
 * M32R cross-compiler from the real Stage 2j headers (no hand-computed
 * layout). Compiled with -S only; build.py extracts the PK_OFFSET lines into
 * local/build/offsets.inc, which pk_core.S and the module .S files include.
 * Nothing from this file is linked into a module. */
#include <stddef.h>
#include "../stage2j/recipe_fw.h"

#define EMIT(name, value) \
    __asm__ volatile ("PK_OFFSET " #name ", %0" :: "i"(value))

void pk_offsets(void)
{
    EMIT(PK_C_LABELS, offsetof(RfwCache, labels));
    EMIT(PK_C_GLYPHS, offsetof(RfwCache, glyphs));
    EMIT(PK_C_UNCERTAIN, offsetof(RfwCache, deep.uncertain));
    EMIT(PK_C_GLYPH_BYTES, RFW_GLYPH_BYTES);
    EMIT(PK_C_SIZE, sizeof(RfwCache));
}
