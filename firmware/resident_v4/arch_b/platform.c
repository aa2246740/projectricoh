#include "abi.h"
/* No boot barrier or permanent heap ownership has been established on target.
 * Separate translation unit, no LTO: the complete gated loader stays counted. */
const Bv4Platform bv4_platform={0,0,0,0};
const Bv4Api bv4_api={1,16,RV4_ROOT_ADDRESS,BV4_REQUIRED_PROOFS};
