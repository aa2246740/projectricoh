#include "integrated.h"
int32_t ig_native_seed(RvPrivateContext *c)
{
    uint32_t table=RV_WORD(0x2022f720);uint8_t *out;
    if(!c||c->ui_state_capacity<212||RV_BYTE(0x2022f71c)!=5||
       table<0x20000000u||table>0x20704800u-72)return RV_UNAVAILABLE;
    out=eng_wire_pointer(c->ui_state_address);
    pn_copy(out,RV_PTR(0x2022f71c),32);pn_copy(out+32,RV_PTR(table),72);
    /* Stage2l's established no-detail records are twelve zero bytes per row. */
    pn_zero(out+104,108);c->ui_state_bytes=212;return RV_OK;
}
