#ifndef GXTS2_H
#define GXTS2_H
#include "gxrce.h"
enum { GXTS_BYTES=240, GXTS_MAX_BYTES=256, GXTS_PARAMS=6,
       GXTS_A=0, GXTS_B=1, GXTS_TEMP=2 };
typedef enum {
    GXTS_OK, GXTS_ARGUMENT, GXTS_LENGTH, GXTS_VERSION, GXTS_CRC,
    GXTS_IDENTITY, GXTS_RANGE, GXTS_CONFLICT, GXTS_MISSING,
    GXTS_GENERATION, GXTS_IO, GXTS_UNCERTAIN
} GxtsStatus;
typedef struct {
    uint8_t identity[160];
    int32_t lo[6],hi[6],def[6];
    uint8_t module,slot; /* slot=1..16; storage adapter uses slot-1 for 00..15. */
} GxtsBinding;
typedef struct { uint32_t generation; int32_t values[6]; } GxtsState;
typedef struct { GxtsState state; unsigned selected,invalid_mask,io_error_mask; } GxtsSelection;

GxtsStatus gxts_bind(const Gxr2View *,unsigned module,unsigned slot,GxtsBinding *);
GxtsStatus gxts_encode(const GxtsBinding *,const GxtsState *,uint8_t out[GXTS_BYTES]);
GxtsStatus gxts_decode(const uint8_t *,size_t,const GxtsBinding *,GxtsState *);
/* Missing/invalid copies do not hide the other valid copy. Equal generation
 * with different raw bytes is a conflict. Errors never modify out. */
GxtsStatus gxts_select(const uint8_t *a,size_t an,const uint8_t *b,size_t bn,
                     const GxtsBinding *,GxtsSelection *out);
void gxts_defaults(const GxtsBinding *,GxtsState *);

/* Logical objects only, never arbitrary paths. These are adapters to the
 * resident's restricted storage service, not native IROM implementations.
 * Each callback returns 0 on success, 1 for proven missing, negative on error.
 * read/write report 0..requested in actual. close revokes the handle once even
 * on failure. open(write=1) only creates TEMP; rename only TEMP -> A/B without
 * replacement. Caller proves menu ownership, leases and stable IROM epochs.
 * No fsync/power durability guarantee follows from successful close/readback. */
typedef struct {
    void *context;
    int (*open)(void *,unsigned module,unsigned slot0,unsigned copy,int write,uint32_t *handle);
    int (*read)(void *,uint32_t,uint8_t *,uint32_t requested,uint32_t *actual);
    int (*write)(void *,uint32_t,const uint8_t *,uint32_t requested,uint32_t *actual);
    int (*close)(void *,uint32_t);
    int (*remove)(void *,unsigned module,unsigned slot0,unsigned copy);
    int (*rename_temp)(void *,unsigned module,unsigned slot0,unsigned target);
} GxtsIO;
GxtsStatus gxts_load(const GxtsIO *,const GxtsBinding *,GxtsSelection *);
GxtsStatus gxts_save(const GxtsIO *,const GxtsBinding *,const int32_t values[6],GxtsSelection *);
const char *gxts_status_name(GxtsStatus);
#endif
