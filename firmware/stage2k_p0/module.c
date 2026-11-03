#include <stddef.h>
#include <stdint.h>
#include "../stage2j/recipe_fw.h"

/* This entry runs only AFTER the resident A/B test. It is a measurement
 * helper, not the first test of execution from the heap. All mutable state
 * belongs to this call or to the existing, resident-owned UI glyph buffer. */
extern uint32_t p0_tick_loop(uint32_t count);
typedef uint32_t (*Language)(void);
typedef void (*Ascii)(const char *, uint32_t, uint8_t *, uint32_t);

static void row(RfwCache *cache, unsigned index, uint32_t ticks)
{
    volatile char text[16];
    unsigned i;
    text[0]='0'; text[1]=(char)('1'+index); text[2]=' ';
    /* Eight decimal digits deliberately reject overflow rather than hide it. */
    for (i=11; i>3; --i) {
        text[i]=(char)('0'+ticks%10u);
        ticks/=10u;
    }
    text[3]=ticks ? '!' : 'T';
    text[12]=0;
    ((Ascii)(uintptr_t)0x20052800)((const char *)text,12,cache->glyphs[index],
        ((Language)(uintptr_t)0x2005280c)());
    cache->labels[index]=cache->glyphs[index];
}

__attribute__((visibility("hidden")))
uint32_t p0_measure(RfwCache *cache)
{
    volatile char text[10];
    uint32_t short_ticks, long_ticks;
    /* The same emitted loop has two trip counts. Neither interrupts nor
     * the scheduler is disabled. These are raw ticks, not a CPU clock claim. */
    short_ticks=p0_tick_loop(1u<<22);
    long_ticks=p0_tick_loop(1u<<24);
    row(cache,5,short_ticks);
    row(cache,6,long_ticks);
    text[0]='0'; text[1]='8'; text[2]=' ';
    text[3]='A'; text[4]='B'; text[5]=' '; text[6]='?'; text[7]='M'; text[8]=0;
    ((Ascii)(uintptr_t)0x20052800)((const char *)text,8,cache->glyphs[7],
        ((Language)(uintptr_t)0x2005280c)());
    cache->labels[7]=cache->glyphs[7];
    return 0;
}
