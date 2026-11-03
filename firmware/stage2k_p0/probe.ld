OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(p0_select)
/* Frozen Stage 2j symbols are supplied by the audited build script. */
p0_native_bridge = 0x20052854;
/* Proven vacancies (not used by normal 2j function):
 *   early [0x20053E64,0x20053E6C)   8 B -> switch-file name only (data)
 *   late  [0x200546EC,0x20054700)  20 B \ contiguous, 276 B together
 *   tail  [0x20054700,0x20054800) 256 B / -> p0_free, p0_select, p0_sync
 * .probe starts right after .late; the asserts keep every byte inside the
 * union of the late and tail vacancies. */
SECTIONS {
    .early 0x20053e64 : { *(.early) }
    .late 0x200546ec : { *(.late) }
    .probe ALIGN(ADDR(.late) + SIZEOF(.late), 4) : { *(.probe) }
    .forbidden : { *(.text* .data* .bss* COMMON .sdata* .sbss* .got* .plt*) }
    .relocations : { *(.rel.* .rela.*) }
    /DISCARD/ : { *(.comment .note* .eh_frame* .gnu.attributes) }
    ASSERT(SIZEOF(.early) <= 8, "Early vacancy exceeds 8 bytes")
    ASSERT(ADDR(.late) == 0x200546ec, "Late vacancy moved")
    ASSERT(ADDR(.probe) >= 0x200546ec + SIZEOF(.late), "Probe overlaps late")
    ASSERT(ADDR(.probe) + SIZEOF(.probe) <= 0x20054800, "Resident exceeds late+tail vacancies")
    ASSERT(SIZEOF(.forbidden) == 0, "Resident has forbidden state")
}
