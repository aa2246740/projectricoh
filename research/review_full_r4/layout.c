/* Compile-only target layout probe; no linked engine or firmware is produced. */
#include "../../firmware/engine_fix_r2/containers/product/adapter.c"
#include "../../firmware/resident_v32/resident/loader.c"
const uint32_t review_target_sizes[] = {
    sizeof(SessionWork),sizeof(PnGxts),sizeof(RvSession),RV_BLOCK_OVERHEAD,
    sizeof(RvLoadWork),sizeof(RvUiSnapshot),sizeof(Integrated),RV_STATE_BYTES,RV_UI_CAPACITY
};
