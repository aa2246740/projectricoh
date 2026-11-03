OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(pv_entry)
SECTIONS {
    . = 0;
    .engine : ALIGN(4) { *(.prefix) *(.text .text.*) }
    .forbidden : { *(.rodata* .data* .bss* COMMON .sdata* .sbss* .got* .plt* .init* .fini*) }
    /DISCARD/ : { *(.comment .note* .eh_frame* .gnu.attributes) }
    ASSERT(pv_entry == 0, "engine is linked at zero")
    ASSERT(pv_entry_init == 16 && pv_entry_abort == 144, "fixed entry offsets")
    ASSERT(SIZEOF(.forbidden) == 0, "no globals, absolute tables, GOT or hidden rodata")
    ASSERT(SIZEOF(.engine) <= 32768, "engine exceeds source size limit")
}
