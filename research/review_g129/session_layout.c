#include <stddef.h>
#include "adapter.c"
#include "src/firmware/engine/core/eng_core.c"

__attribute__((used,section(".layout")))
const unsigned review_session_fields[]={
    offsetof(Integrated,initialized),offsetof(Integrated,active),
    offsetof(Integrated,context),offsetof(Integrated,request),
    offsetof(Engine,work),sizeof(KvWork)
};
