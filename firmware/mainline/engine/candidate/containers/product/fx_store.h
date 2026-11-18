#ifndef BODY_R5_FX_STORE_H
#define BODY_R5_FX_STORE_H
#include <stdint.h>
typedef struct {
    uint32_t epochs[12], lease, descriptor, raw_size, rounded_size;
    uint32_t region, capacity, view, rpc, activity, pending;
    uint8_t descriptor2, descriptor3, cid[16];
} FxStamp;
typedef struct {
    uint32_t published,pending,actual,total,payload_bytes,max_request,opens,closes;
    int32_t status;
    FxStamp stamp;
    uint8_t header[64];
} FxStore;
extern FxStore fx_store;
uint32_t fx_store_catalog_bytes(void);
int fx_store_live(void);
int32_t fx_store_read(void);
int32_t fx_store_publish(void);
void fx_store_discard(int32_t);
const uint8_t *fx_store_data(void);
uint8_t *fx_store_candidate(void);
int32_t fx_io_stamp(FxStamp *);
int32_t fx_io_open(const char *);
int32_t fx_io_read(int32_t,void *,uint32_t);
int32_t fx_io_close(int32_t);
uint8_t *fx_io_target(uint32_t);
void fx_io_cache_prepare(void);
#endif
