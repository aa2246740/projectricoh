#include "eng_internal.h"
/* Pure constant coordination stub. A future service-backed query must use the
 * init-supplied RvApi; never import a native or resident code address. */
__attribute__((weak)) uint32_t rv_unit_pin(uint8_t unit)
{
    static const uint32_t pins[3]={UINT32_C(0xf09fe7b4),UINT32_C(0xfb3fbcb2),UINT32_C(0x95f3dca9)};
    return unit<3?pins[unit]:0;
}
