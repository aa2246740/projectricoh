#include "engine_services.h"
int32_t rv_native_seed(RvPrivateContext *c)
{
    uint32_t table=RV_WORD(0x2022f720);uint8_t *out;
    /* H01 precedes the constructor's type=5 store at 0x2028712c.
     * A different current kind is safe only with the proven native table.
     * Build kind 5 in our private allocation; leave native state untouched. */
    if(!c||c->ui_state_capacity<236||
       table<0x20000000u||table>0x20704800u-72||
       (RV_BYTE(0x2022f71c)!=5&&table!=0x2022f56c))return RV_UNAVAILABLE;
    out=RV_PTR(c->ui_state_address);
    memcpy(out,RV_PTR(0x2022f71c),32);memcpy(out+32,RV_PTR(table),72);
    out[0]=5;
    rv_clear(out+104,132);c->ui_state_bytes=236;return RV_OK;
}
