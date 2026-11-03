ENTRY(ig_bootstrap)
__image_base = IMAGE_BASE;
SECTIONS {
  .engine (IMAGE_BASE + 256) : ALIGN(4) {
    *(.text .text.*) *(.rodata .rodata.*) *(.data .data.*)
    . = ALIGN(4); *(.got.plt) __got_start = .; *(.got) __got_end = .; . = ALIGN(4);
  }
  __engine_end = .;
  .bss (IMAGE_BASE + BSS_START) (NOLOAD) : ALIGN(4) {
    *(.bss .bss.*) *(COMMON) . = ALIGN(4);
  }
  .rela.got 0 : { *(.rela.got) }
  /DISCARD/ : { *(.comment) *(.note.GNU-stack) }
  ASSERT(SIZEOF(.engine) <= 49152, "engine exceeds 48 KiB")
  ASSERT(BSS_START <= 65536, "container exceeds 64 KiB")
  ASSERT(BSS_START + SIZEOF(.bss) <= 81920, "image+BSS exceeds 80 KiB")
  ASSERT(__engine_end <= IMAGE_BASE + BSS_START, "engine overlaps BSS")
}
