OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(rv_services_init)
SECTIONS {
    . = IMAGE_BASE + 256;
    .image_data : { *(.text .text.*) . = ALIGN(4); *(.rodata .rodata.*) *(.data.rel.ro .data.rel.ro.*)
        . = ALIGN(4); *(.got.plt) __got_start = .; *(.got) __got_end = .; . = ALIGN(4); }
    .forbidden : { *(.data .data.* .bss .bss.* COMMON .sdata* .sbss* .plt* .init* .fini*) }
    .rela.got 0 : { *(.rela.got) }
    /DISCARD/ : { *(.comment .note* .eh_frame* .gnu.attributes) }
    ASSERT(SIZEOF(.image_data)<=65536,"service library exceeds engine code limit")
    ASSERT(SIZEOF(.forbidden)==0,"service library has mutable globals")
}
