ENTRY(eng_bootstrap)
__image_base = IMAGE_BASE;
SECTIONS {
  .engine (IMAGE_BASE + 256) : ALIGN(4) {
    *(.text .text.*) *(.rodata .rodata.*) *(.data .data.*)
    . = ALIGN(4); __got_reserved_start = .; *(.got.plt) __got_start = .; *(.got) __got_end = .; . = ALIGN(4);
  }
  __engine_end = .;
  .bss (IMAGE_BASE + BSS_START) (NOLOAD) : ALIGN(4) { *(.bss .bss.*) *(COMMON) . = ALIGN(4); }
  .rela.got 0 : { *(.rela.got) }
  /DISCARD/ : { *(.comment) *(.note.GNU-stack) }
  ASSERT(SIZEOF(.engine) <= 32768, "combined engine exceeds 32 KiB")
  ASSERT(BSS_START <= 49152, "container exceeds 48 KiB")
  ASSERT(SIZEOF(.bss) <= 4096, "engine BSS exceeds container ABI")
  ASSERT(__engine_end <= IMAGE_BASE + BSS_START, "engine overlaps BSS")
}
