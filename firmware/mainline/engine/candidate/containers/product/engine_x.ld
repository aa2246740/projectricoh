ENTRY(ig_bootstrap)
__image_base = IMAGE_BASE;
SECTIONS {
  .engine (IMAGE_BASE + 256) : ALIGN(4) {
    *(.text .text.*) *(.data .data.*) KEEP(*(.engine_version))
    . = ALIGN(4); *(.got.plt) __got_start = .; *(.got) __got_end = .; . = ALIGN(4);
  }
  __engine_end = .;
  .xdata (IMAGE_BASE + XDATA_START) : ALIGN(4) {
    *(.rodata .rodata.*) . = ALIGN(4);
  }
  __xdata_end = .;
  .bss (IMAGE_BASE + BSS_START) (NOLOAD) : ALIGN(4) {
    *(.bss .bss.*) *(COMMON) . = ALIGN(4);
  }
  .rela.got 0 : { *(.rela.got) }
  /DISCARD/ : { *(.comment) *(.note.GNU-stack) }
  ASSERT(SIZEOF(.engine) <= 98304, "engine exceeds 96 KiB")
  ASSERT(BSS_START <= 98304, "container exceeds 96 KiB")
  ASSERT(BSS_START + SIZEOF(.bss) <= 114688, "image+BSS exceeds 112 KiB")
  ASSERT(__engine_end <= IMAGE_BASE + XDATA_START, "engine overlaps xdata")
  ASSERT(__xdata_end <= IMAGE_BASE + BSS_START, "xdata overlaps BSS")
}
