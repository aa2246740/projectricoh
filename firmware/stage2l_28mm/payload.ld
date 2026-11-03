OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(ricoh_recipe_open)
PROVIDE(RECIPE_BASE = 0x2005276c);
PROVIDE(RECIPE_CAPACITY = 8340);
PROVIDE(PROBE_RESERVE = 256);
/* ui.o rodata (rfw_no_details, rfw_empty_table, rfw_closed_table) stays at
 * its stage 2e address 0x20053e6c, so adj_name_table and adj_empty_details
 * keep their stage 2e bytes. Code in .text.late follows that rodata. */
PROVIDE(UI_RODATA_PIN = 0x1700);
native_commit_epilogue = 0x202bcf58;
native_commit_resume = 0x202bb96c;
native_fn2_epilogue = 0x202be6a8;
native_fn2_resume = 0x202be250;
native_action_resume = 0x202871dc;
native_2f02_resume = 0x20170990;
SECTIONS {
    . = RECIPE_BASE;
    __payload_start = .;
    .payload : ALIGN(4) {
        *(.text)
        . = ALIGN(4);
        __early_text_end = .;
        . = UI_RODATA_PIN; /* section-relative: RECIPE_BASE + UI_RODATA_PIN */
        *ui.o(.rodata .rodata.*)
        . = ALIGN(4);
        __late_text_start = .;
        *(.text.late)
        . = ALIGN(4);
        __late_text_end = .;
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
    ASSERT(__early_text_end <= RECIPE_BASE + UI_RODATA_PIN, "Early text overruns the pinned ui.o rodata")
}
