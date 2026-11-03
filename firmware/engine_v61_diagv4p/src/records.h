#ifndef DIAG_V4P_RECORDS_H
#define DIAG_V4P_RECORDS_H
#include "../engine_services/engine_services.h"
enum { DG_GENERATION=160, DG_SCHEMA=7, DG_SCENES=11, DG_LAYERS=5, DG_PIECES=4,
       DG_READY=1, DG_FROZEN=2, DG_INVALID=4, DG_OVERFLOW=8, DG_CHANGED=16, DG_MISSING=32 };
typedef struct {
    RvBufferHeader header;
    uint32_t s_address,s_bytes,state;
    uint8_t my,pending,linked,reserved;
    uint32_t lock_count,lock_id;
    GxrceUnit unit;
    uint8_t values[28],tail[40];
    uint32_t s_after,length_after,spare[2];
} DgNative;
typedef struct {uint32_t meta[32];uint8_t rows[512];DgNative native;} DgCurrent;
typedef struct {uint32_t set,sequence,start,end;uint16_t scene,config,valid,flags;} DgScene;
typedef struct {uint32_t sequence,tick,state,view;uint8_t code,cursor,cache,kind;uint32_t set;} DgKey;
typedef struct {uint16_t x,y,w,h;uint8_t color,flags;} DgRect;
typedef struct {uint32_t start,end,result;} DgPiece;
typedef struct {
    uint32_t front,back;uint16_t width,height;uint32_t setting,flags;
    uint16_t count,pieces;
    uint32_t source;
    DgRect rect[16];DgPiece piece[4];
} DgLayer;
typedef struct {uint32_t id,stride,count,base,address[18];} DgCategory;
typedef struct {
    uint32_t raw[16],covered[4],nonzero[4],sequence,tick,flags,stored;
    uint32_t stride[99],base[99];uint8_t count[100];
} DgSlots;
typedef struct {
    uint32_t sequence,tick,state,k,life,source,base,width,height,stride;
    uint32_t quality,aspect,flags,set;
    uint8_t raw[16];
} DgImage;
typedef struct {uint32_t sequence,source,k,life,h09,h40,h41,status,flags,set,config,raw,h40_sequence,h41_sequence;uint8_t h41_key[24];} DgTime;
typedef struct {uint32_t sequence,tick,state,base,end,step,flags,set,values[16];} DgMem;
typedef struct {uint32_t start,end,result;uint32_t bytes,source;uint16_t repeats,flags;} DgBw;
typedef struct {uint32_t sequence,scene,tick,source,bytes;uint8_t data[144];} DgSource;
_Static_assert(sizeof(DgSource)==164,"raw source record");
typedef struct {DgCurrent current;DgSlots slots[2];DgMem mem[2];uint8_t er_pattern[32][16];uint32_t heap[12],stacks[3][8];uint8_t osd_config[4][72];uint32_t palette_count,palette[16][3];} DgAux;
_Static_assert(sizeof(DgAux)<=RV_STATE_BYTES-sizeof(RvUiSnapshot),"owned state regions");
typedef struct {
    uint32_t magic,version,generation,bytes,crc,flags,boot,unit_epoch,link_epoch,s_epoch,set,ready_tick;
    GxrceUnit unit;
    uint8_t dat_header[256];uint32_t allocation[8];DgSource requests[6],k_sources[6];
    DgScene scene[DG_SCENES];
    DgKey keys[4];
    DgLayer osd[4][5];
    DgImage images[3];DgTime times[6];
    DgBw bw[3][32];
    uint32_t counts[4];
} DgRecord;
_Static_assert(sizeof(DgNative)==128,"native current record");
_Static_assert(sizeof(DgCurrent)==768,"current record budget");
_Static_assert(sizeof(DgLayer)==236,"OSD layer budget");
_Static_assert(sizeof(DgTime)==80,"time record budget");
int32_t rv_diag_supported(RvRoot *);
int32_t rv_diag_current(RvRoot *,const RvRequest *,DgNative *);
int32_t rv_diag_row(RvRoot *,const RvRequest *,unsigned,uint8_t *,unsigned);
uint32_t dg_tick(void);
uint32_t dg_irq_enabled(void);
uint32_t dg_read32(uint32_t,unsigned,unsigned);
extern uint8_t dg_control[65536];
#endif
