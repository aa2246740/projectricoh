/* Hypothetical candidate VMA, not an approved camera memory map. */
OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(ricoh_to_gcc_probe)
SECTIONS
{
    . = 0x2005276c;
    __payload_start = .;
    .payload : ALIGN(4) {
        KEEP(*(.entry))
        *(.text .text.*)
        . = ALIGN(4);
        *(.rodata .rodata.*)
    }
    __payload_end = .;
    .forbidden : { *(.data .data.* .bss .bss.* COMMON .sdata* .sbss* .got* .plt* .init* .fini*) }
    /DISCARD/ : { *(.comment .note* .eh_frame*) }
    ASSERT(SIZEOF(.forbidden) == 0, "Mutable globals or runtime sections require a proven RAM owner")
    ASSERT(__payload_end - __payload_start <= 0x2094, "Hypothetical candidate overflow")
}
