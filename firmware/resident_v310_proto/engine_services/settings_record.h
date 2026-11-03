#ifndef RV_SETTINGS_RECORD_H
#define RV_SETTINGS_RECORD_H
/* DAT-internal wire layout for RV_SETTINGS op 4 (read) / op 5 (replace) of
 * the 40-byte record at S+0xFD4. Kept out of the resident's abi.h so the
 * engine tree's resident/ stays byte-identical to firmware/resident_v38. */
#include "../../resident/abi.h"
typedef struct {
    RvBufferHeader header;
    uint32_t settings_token,settings_epoch,reserved[2];
    uint8_t record[40];
} RvSettingsRecord;
_Static_assert(sizeof(RvSettingsRecord)==64, "S record layout");
#endif
