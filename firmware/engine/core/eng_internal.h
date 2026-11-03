#ifndef ENG_INTERNAL_H
#define ENG_INTERNAL_H
#include "eng_core.h"
#include "../../resident_v2/abi.h"
#include "../../card_container_v2/gxrce.h"
#include <stddef.h>
enum { ENG_SLOTS=16, ENG_ROWS=7, ENG_ENTRY=448, ENG_META=28,
       ENG_MATRIX=1, ENG_AUX=2, ENG_CONTROL=4, ENG_GRAIN=8, ENG_ROW20=16 };
enum { ENG_STAGE_IDLE, ENG_STAGE_T, ENG_STAGE_ROWS, ENG_STAGE_SETTINGS,
       ENG_STAGE_PREVIEW, ENG_STAGE_COMMITTED };
typedef struct { uint32_t boot,heap,link,unit,view,settings,mode; } EngEpoch;
/* An explicit resident-owned publication address is required. No fixed root
 * address or reserved-word ownership is assumed by this engine. */
typedef struct {
    uint32_t armed,boot,heap,link,unit,settings,mode,recipe;
} EngGrain;
_Static_assert(sizeof(EngGrain)==32,"grain publication");
/* The container v2 base format has no WB binding fields. A future validator
 * may supply this only after validating its metadata extension. valid=0 is
 * mandatory until the lane and signs have independent evidence. */
typedef struct { uint8_t valid,lane; int8_t ab_sign,gm_sign; } EngWbBinding;
typedef int32_t (*EngService)(void *,uint32_t,uint32_t,uint32_t,uint32_t,
                            void *,uint32_t,uint32_t,RvReply *);
typedef struct { EngService call; void *user; volatile EngGrain *grain; EngWbBinding wb[3]; const Gxr2View *gated; } EngPort;
typedef struct {
    const uint8_t *image; uint32_t length;
    const uint8_t *map,*bank,*pool,*meta,*ids;
    uint8_t unit,count; Gxr2View view; uint32_t pin;
} EngData;
typedef struct {
    uint8_t occupied,canonical_stock; char ascii[33];
} EngListRow;
typedef struct { EngListRow row[16]; uint8_t cursor,applied,opened,warning; } EngList;
/* image must be the private immutable, resident-envelope/pin-validated copy.
 * This adapter validates all three banks, table pools, metadata, and maps.
 * It deliberately never rechecks relocated engine words as disk CRC bytes. */
EngStatus eng_data_accept(const Gxr2View *);
uint32_t rv_unit_pin(uint8_t);
void eng_crc_binding(const uint8_t *,size_t,uint8_t [32]);
EngStatus eng_data_validate(const uint8_t *,uint32_t,const RvUnitInfo *,EngData *);
uint32_t eng_crc(const uint8_t *,size_t);
void eng_identity(const uint8_t *,uint8_t [49]);
const uint8_t *eng_record(const EngData *,unsigned);
const uint8_t *eng_meta_record(const EngData *,unsigned);
const uint8_t *eng_entry(const EngData *,unsigned);
EngStatus eng_init(const uint8_t *,uint32_t,const EngPort *);
EngStatus eng_menu_open(void);
EngStatus eng_select(uint8_t);
EngStatus eng_restore_stock(void);
void eng_menu_close(void);
const EngList *eng_list(void);
void eng_invalidate(void);
EngStatus eng_rebind(void);
unsigned eng_stage(void);
int eng_parameter_index(uint32_t);
int eng_grain_gate(const volatile EngGrain *,const EngEpoch *,unsigned,
                   const uint8_t *,size_t,uint8_t *,size_t);
/* Native pointer transport is isolated here so host tests can use an address
 * dictionary without changing the production transaction implementation. */
uint32_t eng_wire_address(const void *);
void *eng_wire_pointer(uint32_t);
#endif
