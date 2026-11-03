#include <stdint.h>
#include <stddef.h>

void *memcpy(void *destination, const void *source, size_t length)
{
    uint8_t *d=destination;
    const uint8_t *s=source;
    size_t i;
    for (i=0;i<length;++i) d[i]=s[i];
    return destination;
}
/* The existing freestanding cross compiler has no installed libgcc.a.
 * gxrce SHA finalization emits this logical 64-bit shift helper. */
uint64_t __lshrdi3(uint64_t value, int count)
{
    union {
        uint64_t value;
#if __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
        struct { uint32_t hi,lo; } word;
#else
        struct { uint32_t lo,hi; } word;
#endif
    } v;
    v.value=value;
    if (count<=0) return value;
    if (count<32) {
        v.word.lo=(v.word.lo>>count)|(v.word.hi<<(32-count));
        v.word.hi>>=count;
    } else {
        v.word.lo=count<64 ? v.word.hi>>(count-32) : 0;
        v.word.hi=0;
    }
    return v.value;
}
