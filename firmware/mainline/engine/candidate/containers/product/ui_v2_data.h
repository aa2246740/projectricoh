#ifndef UI_V2_DATA_H
#define UI_V2_DATA_H
#include "src/firmware/engine/core/eng_internal.h"
enum { UV_PARAMS=11, UV_USERS=8, UV_PHYSICAL=8,
       UV_LEGACY=1408, UV_USER_OFFSET=64, UV_EXT_BYTES=256 };
#include "kv2/kv_ui.h"
typedef struct { uint16_t top,cursor; } UvWindow;
void uv_window(unsigned count,unsigned current,unsigned previous,UvWindow *);
const uint8_t *uv_extension(const Gxr2View *);
const uint8_t *uv_user(const Gxr2View *,unsigned index);
int uv_validate(const Gxr2View *);
unsigned uv_users(const Gxr2View *);
const KvDataView *eng_knobs_view(void);
EngStatus eng_project_compute(unsigned slot,const UvLevels *,uint8_t out[552]);
EngStatus eng_project_preview(unsigned slot,const UvLevels *);
#endif
