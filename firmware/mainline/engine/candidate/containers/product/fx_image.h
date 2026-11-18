#ifndef BODY_R5_FX_IMAGE_H
#define BODY_R5_FX_IMAGE_H
#include "../../../resident/resident.h"
typedef struct {
    uint32_t frames,done,unsupported,partial,h40,h41,drawn,draw_rejected;
    uint32_t k,base,rows,status,epoch[12];
} FxImage;
extern FxImage fx_image;
void fx_frame_key(uint32_t);
void xpan_status_redraw(void);
void fx_mask_hw_restore(void);
void fx_mask_suspend(void);
int32_t fx_image_entry(const RvRequest *,RvReply *);
#ifdef HF1
int fx_session_ok(void);
int fx_aspect_169(void);
int fx_sw_layer1_ok(int);
int fx_hw_scan_ok(void);
#if defined(HF1_DIAG) || defined(HF4)
uint8_t fx_aspect_byte(void);
#endif
#ifdef HF5
uint32_t fx_hf_hw_hold(void);
void fx_hf_hw_release(void);
#ifdef HF6
int fx_hf_hw_clean(void);
#endif
#ifdef MERGED_R1
int fx_halfpress_hold_view(uint32_t v);
#endif
#endif
#ifdef L2N_FOLD_A
void l2n_fold_apply_once(void);
#endif
#endif
#endif
