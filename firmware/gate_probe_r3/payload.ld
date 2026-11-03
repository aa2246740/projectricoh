OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(gate_probe_render)

PROBE_GLYPHS = 0x2005276c;
PROBE_LABELS = 0x20052d6c;
PROBE_TABLE = 0x20052dac;
PROBE_NO_DETAILS = 0x20052dec;
PROBE_CODE = 0x20052eac;
PROBE_REENTRY = 0x200546ff;
PROBE_TAIL = 0x20054700;

SECTIONS {
    . = PROBE_GLYPHS;
    .probe_glyphs : { *(.probe_glyphs) }
    . = PROBE_LABELS;
    .probe_labels : { *(.probe_labels) }
    . = PROBE_TABLE;
    .probe_table : { *(.probe_table) }
    . = PROBE_NO_DETAILS;
    .probe_no_details : { *(.probe_no_details) }
    . = PROBE_CODE;
    .text : {
        *(.text.entry)
        *(.text.abi)
        *(.text .text.*)
        *(.rodata .rodata.* .rodata.str*)
    }
    __code_end = .;
    /* The reentry byte and the 256-byte tail are not linker output. */
    probe_reentry_abs = PROBE_REENTRY;
    .forbidden : {
        *(.data .data.* .bss .bss.* COMMON .sdata* .sbss* .got* .plt* .init* .fini* .ctors* .dtors* .tdata* .tbss*)
    }
    .relocations : { *(.rel.* .rela.*) }
    /DISCARD/ : { *(.comment .note* .eh_frame* .gnu.attributes) }
    ASSERT(SIZEOF(.forbidden) == 0, "Mutable globals and runtime sections are forbidden")
    ASSERT(ADDR(.probe_glyphs) == PROBE_GLYPHS, "probe_glyphs address")
    ASSERT(ADDR(.probe_labels) == PROBE_LABELS, "probe_labels address")
    ASSERT(ADDR(.probe_table) == PROBE_TABLE, "probe_table address")
    ASSERT(ADDR(.probe_no_details) == PROBE_NO_DETAILS, "probe_no_details address")
    ASSERT(SIZEOF(.probe_glyphs) == 0x600, "probe_glyphs size")
    ASSERT(SIZEOF(.probe_labels) == 0x40, "probe_labels size")
    ASSERT(SIZEOF(.probe_table) == 0x40, "probe_table size")
    ASSERT(SIZEOF(.probe_no_details) == 0xc0, "probe_no_details size")
    ASSERT(ADDR(.text) == PROBE_CODE, "gate_probe_render must be pinned at 0x20052EAC")
    ASSERT(__code_end <= PROBE_REENTRY, "code overlaps the reentry byte")
    ASSERT(__code_end < PROBE_TAIL, "code must end before the FF tail")
    ASSERT(__code_end > PROBE_CODE, "empty code")
}
