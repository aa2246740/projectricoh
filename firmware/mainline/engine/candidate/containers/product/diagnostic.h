#ifndef G175_DIAGNOSTIC_H
#define G175_DIAGNOSTIC_H
#include "integrated.h"
enum { DIAG_ENGINE_BYTES=5120, DIAG_BYTES=1024 };
#if defined(HF9_DIAG)
#if !defined(HF9_DIAG_TRIM) || !defined(HF5_DIAG_TRIM)
#error "HF9_DIAG needs HF9_DIAG_TRIM and HF5_DIAG_TRIM from the profile"
#endif
/* 247: A a h k v H R P Q always; Z z below trim 1, y below trim 3, X with HF5_DIAG_TRIM 0 */
#define DIAG_ROWS (9u+(HF9_DIAG_TRIM<1?2u:0u)+(HF9_DIAG_TRIM<3?1u:0u)+(HF5_DIAG_TRIM<1?1u:0u))
#elif defined(HF1_DIAG) && defined(HF8_DIAG) && defined(XPAN_ZOOM_R2)
#define DIAG_ROWS 13 /* 245: Z z A a h k x y, then H R P Q X */
#elif defined(HF1_DIAG) && defined(HF8_DIAG)
#define DIAG_ROWS 11 /* 245 without zoom: A a h k x y, then H R P Q X */
#elif defined(HF1_DIAG) && defined(XPAN_ZOOM_R1) && defined(HF7_H43)
#define DIAG_ROWS 14 /* 242: Z z A a h k, then the 8 HF rows */
#else
#define DIAG_ROWS 8
#endif
enum { BF_DISPATCH=1u, BF_ACTIVITY=2u, BF_MODE=4u, BF_MY=8u,
       BF_PENDING=16u, BF_SETTINGS=32u, BF_STATE=64u, BF_NATIVE=128u,
       BF_RECORD=256u, BF_ROWS=512u, BF_LOCK=1024u, BF_EPOCH=2048u,
       BF_COLOUR=4096u, BF_POLICY=8192u };
typedef struct {
    uint32_t magic,failed,activity,state,selection,settings,length,boot_word;
    uint32_t root_flags,first_failure,settings_epoch;
    uint8_t mode,submode,my,pending,selector,wb[2],source;
    uint8_t seen,entry,reason,stage,resident,shown,record,phase;
} BootDiagnostic;
_Static_assert(sizeof(BootDiagnostic)<=DIAG_BYTES,"diagnostic arena bound");
int ig_control_off(void);
void diag_init(const RvPrivateContext *);
void diag_capture(unsigned);
void diag_reason(unsigned,uint32_t);
void diag_engine(unsigned);
unsigned diag_page(void);
void diag_text(unsigned,char [14]);
unsigned diag_code(void);
#endif
