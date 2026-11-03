#include "resident.h"
/* W0 does not invent a current-task probe or assert native writer coverage.
 * The zero proof mask is a deliberate UNKNOWN profile, not a capability grant. */
const Rv4NativeProfile rv4_native_profile={0,0,0,0};
uint32_t rv4_native_context(void)
{
    if(!(rv4_native_profile.proof_flags&RV4_CONTEXT_PROVEN)||!rv4_native_profile.context_probe)return 0;
    return ((uint32_t (*)(void))(uintptr_t)rv4_native_profile.context_probe)();
}
void rv4_native_unit(uint32_t out[3])
{
    /* These fixed unit-info words are aligned; M32R is big endian. */
    out[0]=RV4_WORD(0x2040f81c);out[1]=RV4_WORD(0x2040f820);out[2]=RV4_WORD(0x2040f848);
}
