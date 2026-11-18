#ifndef ENG_CORE_H
#define ENG_CORE_H
#include <stdint.h>
#define ENG_PARAMS 8
#include "../../../../kv2/kv_data.h"
typedef struct { uint8_t unit; uint8_t slot; uint8_t identity[49]; uint16_t effect; uint8_t effect_crc[4]; } EngRecipeRef;
typedef struct {EngRecipeRef ref;UvLevels levels;uint8_t user;} EngSavedSelection;
typedef enum { ENG_OK = 0, ENG_REJECTED, ENG_UNCERTAIN, ENG_STALE, ENG_IO, ENG_FAULT } EngStatus;
EngStatus eng_apply(const EngRecipeRef *r, const UvLevels *t);
EngStatus eng_preview_saved(uint8_t slot,const UvLevels *t);
EngStatus eng_confirm_live(EngRecipeRef *r, UvLevels *t);
EngStatus eng_current(EngRecipeRef *r, UvLevels *t);
EngStatus eng_metadata(uint8_t slot, int8_t min[ENG_PARAMS], int8_t max[ENG_PARAMS], int8_t def[ENG_PARAMS]);
EngStatus eng_preview_effect(unsigned effect,const UvLevels *);
int eng_uncertain(void);
int eng_write_started(void);
int eng_snapshot_failed(void);
void eng_require_recheck(void);
EngStatus eng_retry_live(void);
EngStatus eng_check_settings(void);
int eng_settings_owned(void);
volatile uint32_t *eng_colour_guard(void);
void eng_restore_cursor(void);
EngStatus eng_display_current(EngRecipeRef *r,UvLevels *t);
void eng_view_lost(unsigned);
void eng_apply_witness(uint32_t *t,uint32_t *w);
void eng_memory_user(unsigned user);
int eng_memory_pending(void);
unsigned eng_baseline(void);
void eng_boot_source(unsigned my);
int eng_boot_check(void);
EngStatus eng_boot_run(volatile uint32_t *,unsigned *);
unsigned eng_current_user(void);
const EngSavedSelection *eng_saved_selection(void);
unsigned eng_active_code(void);
void eng_read_saved(void);
unsigned eng_memory_result(void);
unsigned eng_memory_error(void);
unsigned eng_saved_code(void);
unsigned eng_t_warn(void);
void eng_key_begin(void);
#endif
