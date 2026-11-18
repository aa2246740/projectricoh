#ifndef PN_PORT_H
#define PN_PORT_H
#include "../../../../../../../resident/abi.h"
#include "../../../../memory.h"
#define pn_zero ig_zero
#define pn_copy ig_copy
#define pn_equal ig_equal

typedef uint32_t (*PnAddress)(void *context, const void *p, uint32_t n);
typedef struct {
    const RvApi *api;
    uint32_t context, io_lease, ui_lease, epochs[6];
    PnAddress address;
    void *address_context;
} PnPort;

uint32_t pn_address(PnPort *, const void *, uint32_t);
int32_t pn_call(PnPort *, uint32_t, uint32_t, const RvRequest *, RvReply *);
void pn_request(PnPort *, RvRequest *, uint32_t lease);
void pn_zero(void *, uint32_t);
void pn_copy(void *, const void *, uint32_t);
int pn_equal(const void *, const void *, uint32_t);
#endif
