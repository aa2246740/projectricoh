#include "recipe_fw.h"
/* Read from this object on the host; this object is not linked into payload. */
const uint32_t rfw_layout[] = {
    sizeof(RfwCache), sizeof(Rv1Bank), sizeof(Rv1Recipe),
    offsetof(RfwCache, bank), offsetof(RfwCache, scratch),
    offsetof(RfwCache, busy), offsetof(RfwCache, applied_slot)
};
