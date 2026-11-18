#ifndef G157_MEMORY_CODEC_H
#define G157_MEMORY_CODEC_H
#include "containers/product/src/firmware/card_container_v2/gxrce.h"
enum { MEMORY_BYTES=40, MEMORY_VERSION=3, MEMORY_FX_FIRST=0x100,
       MEMORY_USER_FIRST=0x80, MEMORY_USERS=32 };
/* Own-tail recognition is deliberately independent of the current DAT CRC.
 * Current-image decoding additionally validates both bindings and semantics. */
int memory_owned(const uint8_t p[MEMORY_BYTES],uint32_t crc);
#endif
