#include "containers/product/adapter.c"
#include "../resident/loader.c"
const uint32_t review_target_sizes[]={
    sizeof(SessionWork),sizeof(PnGxts),sizeof(PsStore),sizeof(RvLoadWork),
    sizeof(RvUiSnapshot),sizeof(Integrated),sizeof(RvSession),RV_BLOCK_OVERHEAD
};
