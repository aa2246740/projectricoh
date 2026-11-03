ENTRY(ig_bootstrap)
__image_base = IMAGE_BASE;
SECTIONS {
 .engine (IMAGE_BASE + 256) : ALIGN(4) {
  *(.text .text.*) *(.rodata .rodata.*) *(.data .data.*) KEEP(*(.engine_version))
  . = ALIGN(4); *(.got.plt) __got_start = .; *(.got) __got_end = .; . = ALIGN(4);
 }
 __engine_end = .;
 .bss (IMAGE_BASE + BSS_START) (NOLOAD) : ALIGN(4) { *(.bss .bss.*) *(COMMON) . = ALIGN(4); }
 .rela.got 0 : { *(.rela.got) }
 /DISCARD/ : { *(.comment) *(.note.GNU-stack) }
 ASSERT(SIZEOF(.engine) <= 65536, "code limit")
 ASSERT(BSS_START <= 98304, "file limit")
 ASSERT(BSS_START + SIZEOF(.bss) + 7628 <= 107612, "main request limit")
 ASSERT(__engine_end <= IMAGE_BASE + BSS_START, "section overlap")
}
