OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(producer_normal)
PHDRS { alt PT_LOAD FLAGS(5); normal PT_LOAD FLAGS(5); }
memset_stock = 0x20062750;
formatter_stock = 0x200bbc7c;
display_stock = 0x203189b4;
SECTIONS
{
    .text.alt 0x203183e8 : { KEEP(*(.text.alt)) . = 212; } :alt =0xf000
    .text.normal 0x20319c00 : { KEEP(*(.text.normal)) . = 212; } :normal =0xf000
    .forbidden : { *(.data* .bss* COMMON .sdata* .sbss* .got* .plt* .init* .fini* .text) }
    /DISCARD/ : { *(.comment .note* .eh_frame*) }
    ASSERT(SIZEOF(.forbidden) == 0, "No orphan code, mutable state or runtime initializer")
    ASSERT(SIZEOF(.text.alt) <= 212, "Alternate producer slot overflow")
    ASSERT(SIZEOF(.text.normal) <= 212, "Normal producer slot overflow")
}
