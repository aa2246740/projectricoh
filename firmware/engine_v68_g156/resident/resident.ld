OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(rv_hook_shared)
RV_PLANNING_MARGIN = 24;
SECTIONS {
    . = 0x2005276c;
    __resident_start = .;
    .resident : ALIGN(4) {
        KEEP(*(.text.rv_hook_*))
        *(.text .text.*)
        . = ALIGN(4);
        *(.rodata .rodata.*)
        . = ALIGN(4);
    }
    __resident_code_end = .;
    .root 0x20054700 (NOLOAD) : { . += 244; }
    .root_pins 0x200547f4 : { KEEP(*(.root_pins)) }
    .forbidden : {
        *(.data .data.* .bss .bss.* COMMON .sdata* .sbss* .got* .plt* .init* .fini* .ctors* .dtors* .tdata* .tbss*)
    }
    .relocations : { *(.rel.* .rela.*) }
    /DISCARD/ : { *(.comment .note* .eh_frame* .gnu.attributes) }
    ASSERT(__resident_code_end <= 0x20054700 - RV_PLANNING_MARGIN, "resident planning margin")
    ASSERT(SIZEOF(.root)==244 && SIZEOF(.root_pins)==12, "root must fit 256B")
    ASSERT(ADDR(.root_pins)+SIZEOF(.root_pins)==0x20054800, "window exceeded")
    ASSERT(SIZEOF(.forbidden)==0, "mutable globals forbidden")
    ASSERT(SIZEOF(.relocations)==0, "unresolved relocations")
}
