#ifndef RV_ENGINE_SERVICES_H
#define RV_ENGINE_SERVICES_H
#include "../../resident/resident.h"
#include "settings_record.h"
int32_t rv_native_seed(RvPrivateContext *);
int rv_view_owned(RvRoot *,const RvUiList *,unsigned);
int rv_settings_owned(RvRoot *,uint32_t);
void rv_settings_entry(RvRoot *,unsigned);

const RvApi *rv_services_init(const RvPrivateContext *);
int32_t rv_service(RvRoot *,uint32_t,uint32_t,const RvRequest *,RvReply *);
int32_t rv_call(uint32_t,uint32_t,const RvRequest *,RvReply *);
int32_t rv_unit(RvRoot *,GxrceUnit *);
extern const RvApi rv_api __attribute__((visibility("hidden")));
int32_t es_ui_abort(RvRoot *);
int32_t rv_native_create(const char *,uint32_t);
int32_t rv_native_write(int32_t,const void *,uint32_t);
int32_t rv_native_delete(const char *);
int32_t rv_native_rename(const char *,const char *);
int32_t rv_native_context(void);
uint32_t rv_native_unit(uint32_t);
int32_t rv_native_sd_id(void *);
int32_t rv_native_rpc_ready(void);
int32_t rv_native_rpc_limit(void);
int32_t rv_rpc8_native(uint32_t,uint32_t);
int32_t rv_native_preview(uint32_t);
int32_t rv_native_language(void);
int32_t rv_native_ascii(const char *,uint32_t,void *,uint32_t);
int32_t rv_native_layer(uint32_t,uint32_t,uint32_t);
int32_t rv_native_draw(uint32_t,uint32_t,uint32_t);
#endif
