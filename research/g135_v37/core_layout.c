/* Target compiler layout for retained state observations. */
#include <stddef.h>
#include "eng_core.c"
#define F(name) offsetof(Engine,name)
const uint32_t core_layout[] __attribute__((used,section(".layout")))={
    sizeof(Engine),F(epoch),F(current),F(confirmed),F(tweak),F(confirmed_tweak),F(list),
    F(stock),F(live),F(staging),F(ready),F(bound),F(busy),F(committed),F(uncertain),
    F(t_checked),F(t_warn),F(t_pending),F(neighbor),F(neighbor_valid),F(stage),
    F(remember_checked),F(confirmed_valid),F(previewing),F(view_lost),
    F(write_started),F(recheck),F(settings_pending)
};
