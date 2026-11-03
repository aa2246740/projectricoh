OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(p0_module_entry)
/* The module is loaded at an arbitrary heap address with no relocation, so
 * it must be position independent: only code, no data. Any .rodata (string
 * literals, const tables) would be reached through an absolute ld24 of a
 * link-time offset and point at a wild low address on the camera. The proven
 * Stage 2k-p0 module likewise has no .rodata and builds labels on the stack.
 * Constants are instruction immediates; in-module calls are PC-relative bl. */
SECTIONS {
    . = 0;
    .module : ALIGN(4) { KEEP(*(.prefix)) *(.text .text.*) }
    .forbidden : { *(.rodata* .data* .bss* COMMON .sdata* .sbss* .got* .plt* .init* .fini*) }
    /DISCARD/ : { *(.comment .note* .eh_frame* .gnu.attributes) }
    ASSERT(p0_module_entry == 16, "Module entry must remain at offset 16")
    ASSERT(SIZEOF(.forbidden) == 0, "Module must be code only: no rodata/data/GOT (not relocatable)")
    ASSERT(SIZEOF(.module) <= 436, "Module exceeds the 436-byte card payload")
}
