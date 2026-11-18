#ifndef IG_ENGINE_H
#define IG_ENGINE_H
#include "../../engine_services/engine_services.h"
#include "src/firmware/engine/core/eng_internal.h"
#include "src/firmware/engine/panel/panel.h"
#include "src/firmware/engine/panel/panel_gxts.h"
int32_t ig_bootstrap(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t ig_init(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t ig_menu(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t ig_event(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t ig_panel_open(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t ig_panel_event(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t ig_panel_abort(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t ig_apply(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t ig_stop(const RvApi *,uint32_t,const RvRequest *,RvReply *);
Gxr2Status gxr2_gate_relocated_validate(const uint8_t *,size_t,const Gxr2Trust *,const Gxr2Unit *,uint32_t,Gxr2View *);
#ifdef ENG_HOST
void ig_host_reset(void);
void eng_host_reset(void);
const PnPanel *ig_host_panel(void);
int32_t ig_host_install_status(void);
int32_t ig_host_last_store(void);
uint32_t ig_host_workspace_bytes(void);
#endif
#endif
