#ifndef V32_DIAG_H
#define V32_DIAG_H
#include "../resident_v32/resident/resident.h"

enum { DIAG_SIGNATURE=0xD1320101u, DIAG_ROWS=16, DIAG_T_SKIP=1 };
typedef struct {
    uint32_t words[16], relocs[256][2];
    uint8_t header[256], buffer[512], directory[64], map[128], pool[64], descriptor[16];
    char rows[16][13];
    uint8_t sampled;
} DiagState;
_Static_assert(sizeof(DiagState)<=RV_STATE_BYTES,"DIAG uses existing resident state");
int32_t diag_native_ascii(const char *,uint32_t,void *,uint32_t);
int32_t diag_native_language(void);
int32_t diag_native_context(void);
int32_t diag_bootstrap(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t diag_init(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t diag_menu(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t diag_event(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t diag_apply(const RvApi *,uint32_t,const RvRequest *,RvReply *);
int32_t diag_close(const RvApi *,uint32_t,const RvRequest *,RvReply *);
#ifdef RV_HOST
extern const RvTrust diag_trust;
#endif
#endif
