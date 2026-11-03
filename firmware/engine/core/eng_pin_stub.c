#include "eng_internal.h"
/* Pure constant coordination stub. A future service-backed query must use the
 * init-supplied RvApi; never import a native or resident code address. */
__attribute__((weak)) uint32_t rv_unit_pin(uint8_t unit)
{
    static const uint32_t pins[3]={UINT32_C(0xdf2bcaf5),UINT32_C(0x6700e6ff),UINT32_C(0x1b3c7000)};
    return unit<3?pins[unit]:0;
}
