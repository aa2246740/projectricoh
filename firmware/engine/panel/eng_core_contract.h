#ifndef PN_ENG_CORE_CONTRACT_H
#define PN_ENG_CORE_CONTRACT_H
#include <stdint.h>
/* Define PN_CORE_HEADER='"../core/eng_core.h"' when integrating the real core. */
#ifdef PN_CORE_HEADER
#include PN_CORE_HEADER
#else
#define ENG_PARAMS 8
typedef struct { int8_t v[ENG_PARAMS]; } EngTweak;
/* Core uses unit 0..2 and slot 1..16. Storage uses module=unit+1, slot=slot-1. */
typedef struct { uint8_t unit; uint8_t slot; uint8_t identity[49]; } EngRecipeRef;
typedef enum { ENG_OK=0, ENG_REJECTED, ENG_UNCERTAIN, ENG_STALE,
               ENG_IO, ENG_FAULT } EngStatus;
EngStatus eng_apply(const EngRecipeRef *, const EngTweak *);
EngStatus eng_current(EngRecipeRef *, EngTweak *);
EngStatus eng_metadata(uint8_t, int8_t[ENG_PARAMS], int8_t[ENG_PARAMS],
                       int8_t[ENG_PARAMS]);
int eng_uncertain(void);
#endif
#endif
