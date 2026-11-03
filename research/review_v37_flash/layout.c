#include <stdio.h>
#include "../../firmware/engine_v52_redisplay/resident/resident.h"
#define F(T,x) printf("%s.%s %zu\n",#T,#x,offsetof(T,x))
int main(void) {
F(RvRoot,ui_restore);F(RvRoot,flags);F(RvRoot,block);F(RvRoot,lease);F(RvRoot,unit);F(RvRoot,ui_block);F(RvRoot,entry_serial);F(RvRoot,lease_inverse);F(RvRoot,epoch);F(RvRoot,heap_begin);F(RvRoot,block_bytes);F(RvRoot,alloc_bytes);F(RvRoot,code_address);
F(RvSession,entries);F(RvSession,context);F(RvSession,leases);F(RvSession,image_address);F(RvSession,code_begin);F(RvSession,unit);F(RvSession,view_state);F(RvSession,view_source);F(RvSession,settings);F(RvSession,bindings);F(RvSession,capabilities);
F(RvUiList,lease_token);F(RvUiList,view_token);F(RvUiList,state_address);F(RvUiList,rows);F(RvUiView,expected_array);
printf("session_bytes %u\nblock_overhead %u\nmin_block %u\n",RV_SESSION_BYTES,RV_BLOCK_OVERHEAD,RV_MIN_BLOCK_BYTES);
return 0;
}
