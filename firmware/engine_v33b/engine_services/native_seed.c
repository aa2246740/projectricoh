#include "engine_services.h"
int32_t rv_native_seed(RvPrivateContext *c)
{
    uint32_t table=RV_WORD(0x2022f720);uint8_t *out;
    if(!c||c->ui_state_capacity<236||RV_BYTE(0x2022f71c)!=5||
       table<0x20000000u||table>0x20704800u-72)return RV_UNAVAILABLE;
    out=RV_PTR(c->ui_state_address);
    memcpy(out,RV_PTR(0x2022f71c),32);memcpy(out+32,RV_PTR(table),72);
    rv_clear(out+104,132);c->ui_state_bytes=236;return RV_OK;
}
