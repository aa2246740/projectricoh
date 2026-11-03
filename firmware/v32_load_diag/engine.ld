OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(diag_entry)
SECTIONS {
    . = IMAGE_BASE + 256;
    .engine : {
        KEEP(*(.prefix)) *(.text .text.*) . = ALIGN(4);
        *(.rodata .rodata.*) *(.data.rel.ro .data.rel.ro.*) . = ALIGN(4);
        *(.got.plt) __got_start = .; *(.got) __got_end = .; . = ALIGN(4);
    }
    .forbidden : { *(.data .data.* .bss .bss.* COMMON .sdata* .sbss* .plt* .init* .fini*) }
    .rela.got 0 : { *(.rela.got) }
    /DISCARD/ : { *(.comment .note* .eh_frame* .gnu.attributes) }
    ASSERT(diag_entry == IMAGE_BASE + 256,"fixed bootstrap offset")
    ASSERT(diag_entry_abort == IMAGE_BASE + 400,"fixed entry thunks")
    ASSERT(SIZEOF(.forbidden) == 0,"no mutable globals or BSS")
    ASSERT(SIZEOF(.engine) <= 12288,"small DIAG envelope")
}
