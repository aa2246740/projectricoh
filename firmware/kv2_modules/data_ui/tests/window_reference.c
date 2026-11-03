#include "ui_v2_data.h"

void kv_reference_window(unsigned count, unsigned current, unsigned previous,
                          unsigned *top, unsigned *cursor)
{
    UvWindow result;
    uv_window(count, current, previous, &result);
    *top = result.top; *cursor = result.cursor;
}
unsigned kv_reference_legacy_params(void)
{ return UV_PARAMS; }
