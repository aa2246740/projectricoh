#ifndef RFW_DEEP_ISP_H
#define RFW_DEEP_ISP_H
#include "recipe_v1/recipe_v1.h"

#ifndef RFW_DEEP_ENABLED
#define RFW_DEEP_ENABLED 1
#endif

typedef struct { uint8_t active, uncertain, neighbor, neighbor_valid; } RfwDeepState;
typedef struct {
    uint32_t address;
    uint16_t bytes;
    const uint8_t *data[5]; /* stock, Positive, Negative, HC, Bleach */
} RfwDeepRow;

enum { RFW_DEEP_ROWS = 3, RFW_DEEP_PROFILES = 4 };
extern const Rv1Recipe rfw_defaults[RV1_SLOT_COUNT];
extern const uint8_t rfw_deep_slots[RFW_DEEP_PROFILES];
extern const RfwDeepRow rfw_deep_rows[RFW_DEEP_ROWS];

/* Full canonical recipe identity, including its parameters, binds the input
 * tables. A slot number or a partial name never enables a deep profile. */
unsigned rfw_deep_id(const Rv1Recipe *recipe);
Rv1Status rfw_deep_transition(RfwDeepState *, const Rv1Recipe *);

/* GCC ABI; the native variadic frame exists only in abi.S. */
int32_t rfw_rpc8_call(uint32_t letter_idx, uint32_t u16_value);
int32_t rfw_rpc8_native(uint32_t letter_idx, uint32_t u16_value);
uint32_t rfw_rpc8_preflight(void);
int32_t gxr_rpc_ready(void);
int32_t gxr_rpc_limit(void);
int32_t gxr_thread_context(void);
const volatile uint8_t *gxr_unit_info(uint32_t);

/* Safe build returns zero. Deep candidate tail-calls runtime preflight.
 * Preflight proves identity/link/context only, not cursor or ISP exclusion.
 * The experimental deep candidate has no camera acceptance for those gates. */
uint32_t rfw_deep_ownership(void);
#endif
