OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(ricoh_recipe_open)
PROVIDE(RECIPE_BASE = 0x2005276c);
PROVIDE(RECIPE_CAPACITY = 8340);
PROVIDE(PROBE_RESERVE = 256);
native_image_branch = 0x202ba764;
native_commit_epilogue = 0x202bcf58;
native_commit_resume = 0x202bb96c;
native_fn2_epilogue = 0x202be6a8;
native_fn2_resume = 0x202be250;
native_action_resume = 0x202871dc;
SECTIONS {
    . = RECIPE_BASE;
    __payload_start = .;
    .payload : ALIGN(4) {
        *(.text .text.*)
        . = ALIGN(4);
        *(.rodata .rodata.*)
        . = ALIGN(4);
    }
    __payload_end = .;
    __probe_start = RECIPE_BASE + RECIPE_CAPACITY - PROBE_RESERVE;
    __probe_end = RECIPE_BASE + RECIPE_CAPACITY;
    .forbidden : {
        *(.data .data.* .bss .bss.* COMMON .sdata* .sbss* .got* .plt* .init* .fini* .ctors* .dtors* .tdata* .tbss*)
    }
    .relocations : { *(.rel.* .rela.*) }
    /DISCARD/ : { *(.comment .note* .eh_frame* .gnu.attributes) }
    ASSERT(SIZEOF(.forbidden) == 0, "Mutable globals and runtime sections are forbidden")
    ASSERT((RECIPE_BASE & 3) == 0, "Payload base must be four-byte aligned")
    ASSERT(PROBE_RESERVE >= 256, "Reserve at least 256 bytes for the probe worker")
    ASSERT(__payload_end <= __probe_start, "Payload overlaps the reserved probe tail")
}
