OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(bv4_boot_native)
SECTIONS {
    . = 0x2005276c;
    payload_begin = .;
    .payload : ALIGN(4) {
        KEEP(*(.text.bv4_hook_*))
        KEEP(*(.text.bv4_continuations))
        *(.text .text.* .rodata .rodata.*)
        . = ALIGN(4);
    }
    payload_end = .;
    .root 0x20054600 (NOLOAD) : { root_begin = .; . += 512; root_end = .; }
    .forbidden : { *(.data .data.* .bss .bss.* COMMON .sdata* .sbss* .got* .plt* .init* .fini* .ctors* .dtors* .tdata* .tbss*) }
    .relocations : { *(.rel.* .rela.*) }
    /DISCARD/ : { *(.comment .note* .eh_frame* .gnu.attributes) }
    ASSERT(root_begin == 0x20054600,"root_begin mismatch")
    ASSERT(root_end == 0x20054800,"root_end mismatch")
    ASSERT(SIZEOF(.root)==512,"bootstrap root must be 512B")
    ASSERT(payload_end <= 0x20054538,"window exceeds 7628B; 200B reserve required")
    ASSERT(SIZEOF(.forbidden)==0,"extra writable global")
    ASSERT(SIZEOF(.relocations)==0,"unresolved relocations")
}
