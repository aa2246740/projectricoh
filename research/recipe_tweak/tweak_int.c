#include "tweak_int.h"

static int32_t round_div(int32_t n, int32_t d)
{
    return n >= 0 ? (n + d / 2) / d : -((-n + d / 2) / d);
}

static uint8_t warp(uint8_t value, int lo, int hi, int k)
{
    int32_t length = hi - lo, t = value - lo;
    if (!length) return value;
    return (uint8_t)(value + round_div(k * t * (length - t), 64 * length));
}

int rt_tone(const uint8_t a[62], const uint8_t b[33], int pivot,
            int contrast, int highlight, int shadow, uint8_t out[33])
{
    int xs[33], i, left, right = 1, high_end;
    int low_k, high_k;
    if (!a || !b || !out || pivot <= 0 || pivot >= 4095 ||
        contrast < -2 || contrast > 2 || highlight < -2 || highlight > 2 ||
        shadow < -2 || shadow > 2) return -1;
    low_k = -12 * contrast + 16 * shadow;
    high_k = 12 * contrast + 16 * highlight;
    xs[0] = 0; xs[32] = 4095;
    for (i = 1; i <= 31; ++i) {
        xs[i] = ((int)a[(i - 1) * 2] << 8) | a[(i - 1) * 2 + 1];
        if (xs[i] <= xs[i - 1] || xs[i] > 4095) return -1;
    }
    for (i = 1; i < 33; ++i) if (b[i] < b[i - 1]) return -1;
    while (xs[right] < pivot) ++right;
    left = xs[right] == pivot ? right : right - 1;
    high_end = xs[31] == 4095 ? 31 : 32;
    for (i = 0; i < 33; ++i) out[i] = b[i];
    for (i = 1; i < left; ++i) out[i] = warp(b[i], b[0], b[left], low_k);
    for (i = right + 1; i < high_end; ++i)
        out[i] = warp(b[i], b[right], b[32], high_k);
    return 0;
}

int rt_colour(const uint8_t in[96], int level, uint8_t out[96])
{
    int i, clamped = 0;
    if (!in || !out || level < -2 || level > 2) return -1;
    for (i = 0; i < 96; ++i) {
        int magnitude = round_div((in[i] & 127) * (8 + level), 8);
        if (magnitude > 127) { magnitude = 127; ++clamped; }
        out[i] = (uint8_t)((in[i] & 128) | magnitude);
    }
    return clamped;
}
