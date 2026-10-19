OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(probe_entry)
PHDRS { probe PT_LOAD FLAGS(5); }
SECTIONS
{
    . = 0x200547b0;
    __payload_start = .;
    .text : { KEEP(*(.text.probe)) } :probe
    .rodata : { KEEP(*(.rodata.probe)) } :probe
    __payload_end = .;
    .forbidden : { *(.data* .bss* COMMON .sdata* .sbss* .got* .plt* .init* .fini*) }
    /DISCARD/ : { *(.comment .note* .eh_frame*) }
    ASSERT(SIZEOF(.forbidden) == 0, "Probe has no mutable globals or runtime initializer")
    ASSERT(SIZEOF(.text) == 68, "Review code size and scan boundary before changing probe")
    ASSERT(SIZEOF(.rodata) == 12, "Two NUL-terminated six-byte formats required")
    ASSERT(__payload_start == probe_entry, "Probe must be first in payload")
    ASSERT(__payload_end == 0x20054800, "Probe must end exactly at candidate boundary")
}
