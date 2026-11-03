OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(p0_module_entry)
SECTIONS {
    . = 0;
    .module : ALIGN(4) { *(.prefix) *(.text .text.*) *(.rodata .rodata.*) }
    .forbidden : { *(.data* .bss* COMMON .sdata* .sbss* .got* .plt* .init* .fini*) }
    /DISCARD/ : { *(.comment .note* .eh_frame* .gnu.attributes) }
    ASSERT(p0_module_entry == 16, "Module entry must remain at offset 16")
    ASSERT(SIZEOF(.forbidden) == 0, "Module must not need writable globals or a GOT")
    ASSERT(SIZEOF(.module) <= 4096, "Self-test helper is too large")
}
