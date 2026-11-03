#include <stdint.h>

typedef struct {
    uint32_t boot_session, flags, origin_serial, unit_epoch;
    uint32_t link_epoch, settings_epoch, tick_first5, tick_gate;
    uint32_t lock_value, lock_id, uid_hi, uid_lo;
    uint32_t settings_address, settings_bytes, reserved[2];
} AutoWitness;

typedef struct { uint16_t offset; uint8_t old_value, new_value; } AutoSetting;
typedef struct {
    AutoSetting settings[16];
    uint32_t leases[8];
    uint32_t phase, reason, dirty, steps_left;
    uint32_t origin_serial, tick_begin, tick_end, unit_writes;
} AutoTxn;

typedef struct { uint8_t bytes[40]; } AutoRecord;
_Static_assert(sizeof(AutoWitness) == 64, "witness is 64 bytes");
_Static_assert(sizeof(AutoTxn) == 128, "transaction is 128 bytes");
_Static_assert(sizeof(AutoRecord) == 40, "record remains 40 bytes");

/* Layout symbols are measured in the target object. No camera calls. */
AutoWitness aa_witness;
AutoTxn aa_transaction;
AutoRecord aa_record_layout;

/* This prototype covers only ten level bytes, not record qualification. */
int aa_encode_levels(const int16_t in[10], uint8_t out[10])
{
    unsigned i;
    for (i = 0; i < 10; ++i)
        if (in[i] < -9 || in[i] > 150) return -1;
    for (i = 0; i < 10; ++i) out[i] = (uint8_t)(in[i] + 9);
    return 0;
}

int aa_decode_levels(const uint8_t in[10], int16_t out[10])
{
    unsigned i;
    for (i = 0; i < 10; ++i) if (in[i] > 159) return -1;
    for (i = 0; i < 10; ++i) out[i] = (int16_t)in[i] - 9;
    return 0;
}

/* Both complete readbacks must include all owned fields and preview. */
unsigned aa_ready_result(unsigned complete_recipe, unsigned complete04)
{
    if (complete_recipe == 1) return 1;
    if (complete04 == 1) return 2;
    return 0;
}
