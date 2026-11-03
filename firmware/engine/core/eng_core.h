#ifndef ENG_CORE_H
#define ENG_CORE_H
#include <stdint.h>
#define ENG_PARAMS 8
typedef struct { int8_t v[ENG_PARAMS]; } EngTweak;
typedef struct { uint8_t unit; uint8_t slot; uint8_t identity[49]; } EngRecipeRef;
typedef enum { ENG_OK = 0, ENG_REJECTED, ENG_UNCERTAIN, ENG_STALE, ENG_IO, ENG_FAULT } EngStatus;
EngStatus eng_apply(const EngRecipeRef *r, const EngTweak *t);
EngStatus eng_current(EngRecipeRef *r, EngTweak *t);
EngStatus eng_metadata(uint8_t slot, int8_t min[ENG_PARAMS], int8_t max[ENG_PARAMS], int8_t def[ENG_PARAMS]);
int eng_uncertain(void);
#endif
