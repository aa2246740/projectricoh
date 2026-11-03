/* Target-compiler offsets for inspecting the actual adapter state. */
#include <stddef.h>
#include "adapter.c"
#define A(field) offsetof(Integrated,field)
#define U(field) offsetof(UvState,field)
const uint32_t g131_adapter_layout[] __attribute__((used,section(".layout")))={
    sizeof(Integrated),A(ui),A(values),A(failed),A(context),U(levels),U(saved),U(text),U(nav),U(frame),
    U(screen),U(cur),U(top),U(physical),U(count),U(slot),U(param),U(group),U(armed),U(applied_user),
    U(origin),U(l1_cur),U(card_cur),U(item_cur),U(entry_cur),U(confirmed_user),A(list),A(failed_text)
};
