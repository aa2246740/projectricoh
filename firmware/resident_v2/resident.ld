OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(rv_call)
/* No binary image is emitted. MEASURE_LIMIT is overridden only for the
 * separately labelled oversize ELF used to count an overflowing full core. */
PROVIDE(MEASURE_LIMIT = 0x20054600);
PROVIDE(ROOT_ADDR = 0x20054600);
SECTIONS {
    . = 0x2005276c;
    __resident_start = .;
    .payload : ALIGN(4) {
        *(.text .text.*)
        . = ALIGN(4);
        *(.rodata .rodata.*)
        . = ALIGN(4);
    }
    __resident_code_end = .;
    .root ROOT_ADDR (NOLOAD) : { . += 512; }
    .forbidden : {
        *(.data .data.* .bss .bss.* COMMON .sdata* .sbss* .got* .plt* .init* .fini* .ctors* .dtors* .tdata* .tbss*)
    }
    .relocations : { *(.rel.* .rela.*) }
    /DISCARD/ : { *(.comment .note* .eh_frame* .gnu.attributes) }
    ASSERT(SIZEOF(.forbidden)==0, "mutable globals forbidden; use resident root or lease")
    ASSERT(__resident_code_end<=MEASURE_LIMIT, "resident code exceeds 7828B before 512B root")
    ASSERT(SIZEOF(.relocations)==0, "unresolved relocations")
}
