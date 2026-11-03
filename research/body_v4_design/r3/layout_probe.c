#include "resident.h"

/* This object measures proposed layouts only. It is never linked into firmware. */
typedef struct { uint32_t x,y,w,h; } R3Rect;
typedef struct {
    uint32_t sequence,format;
    R3Rect rect[4];
    uint32_t buffer,geometry;
} R3Rects;
typedef struct {
    uint32_t k,sequence,valid,save[7],encoder_status,epoch;
} R3EncodeSave;
typedef struct {
    uint8_t existing[244];
    uint32_t parent[2],extension[4],er[6];
    R3Rects rectangles;
    R3EncodeSave encode_save;
    uint32_t commit[10];
    uint32_t crop_commit[8];
    uint8_t reserved[8];
    uint32_t pins[3];
} R3Root;
typedef struct {
    uint32_t epochs[6];
    uint32_t source_id,sequence,k,k_life;
    uint32_t buffer,width,height,stride;
    uint32_t operation,y0,y1,phase;
    uint32_t er_generation,record_crc,deadline,version;
    uint32_t pin,status;
} R3Shot;
typedef struct {
    uint32_t identity[16];
    uint16_t rectangles[16][6];
} R3Osd;
typedef struct {
    uint8_t read_control[65536];
    R3Osd osd[4][5];
    uint8_t slots[2][32][64];
    uint8_t images[4][128];
    uint8_t timing[16][48];
    uint8_t keys[4][32];
    uint8_t summary_and_work[1664];
} R3Diag;
_Static_assert(offsetof(RvRoot,pins)==244,"existing root prefix changed");
_Static_assert(sizeof(R3Rects)==80,"rectangle layout");
_Static_assert(sizeof(R3EncodeSave)==48,"independent encoder save");
_Static_assert(sizeof(R3Root)==512 && offsetof(R3Root,pins)==500,"root layout");
_Static_assert(offsetof(R3Root,crop_commit)==460,"independent crop record");
_Static_assert(sizeof(R3Shot)==96,"shot layout");
_Static_assert(sizeof(R3Osd)==256,"OSD record layout");
_Static_assert(sizeof(R3Diag)==77824,"diagnostic BSS layout");
R3Root r3_root_layout;
R3Diag r3_diag_layout;
R3Shot r3_shot_ring_layout[18];
R3EncodeSave r3_encode_save_layout;
uint8_t r3_existing_session_layout[sizeof(RvSession)];
uint8_t r3_existing_overhead_layout[RV_BLOCK_OVERHEAD];
uint8_t r3_existing_ui_layout[sizeof(RvUiSnapshot)];
