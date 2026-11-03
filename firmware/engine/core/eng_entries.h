#ifndef ENG_ENTRIES_H
#define ENG_ENTRIES_H
#include "eng_internal.h"
/* Caller must validate every pointer/length against its live leases first.
 * grain_address=0 disables publication. WB fields remain zero for GXTM v2;
 * no physical axis binding exists in its frozen base schema. */
typedef struct {
    RvBufferHeader header;
    uint32_t image_address,image_bytes,grain_address,grain_bytes;
    uint32_t gate_view_address,gate_view_bytes;
    EngWbBinding wb[3];
} EngInitWire;
_Static_assert(sizeof(EngInitWire)==44,"engine init payload");
int32_t eng_bootstrap(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t eng_entry_init(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t eng_entry_menu(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t eng_entry_event(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t eng_entry_apply(const RvApi *,uint32_t,const RvRequest *,RvReply *);
#endif
