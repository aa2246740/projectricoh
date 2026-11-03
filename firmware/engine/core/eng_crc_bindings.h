#ifndef ENG_CRC_BINDINGS_H
#define ENG_CRC_BINDINGS_H
/* Force-include for upstream semantic.c or panel-owned gxts.c. Never compile
 * upstream sha256.c under this alias: the runtime implementation is CRC32. */
#define gxr2_sha256 eng_crc_binding
#include "../../card_container_v2/gxrce.h"
#endif
