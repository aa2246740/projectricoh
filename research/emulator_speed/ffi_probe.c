#include <stdint.h>

typedef int (*bus_fn)(void *, uint32_t, uint32_t, unsigned, void *, int);

uint64_t read_value(void *context, int index) {
    return (uintptr_t)context + (unsigned)index;
}

int one_step(void *context) {
    return context != 0;
}

void clear_cache(void *context) {
    __asm__ volatile("" : : "r"(context) : "memory");
}

int call_bus(bus_fn bus, void *context, int enabled) {
    unsigned char word[4] = {0};
    if (enabled)
        return bus(context, 0x20000000u, 0x20000000u, 4, word, 0);
    return 4;
}
