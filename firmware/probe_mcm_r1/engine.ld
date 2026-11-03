OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(p0_entry)
__image_base = IMAGE_BASE;
SECTIONS {
  .engine (IMAGE_BASE + 256) : ALIGN(4) {
    KEEP(*(.prefix)) *(.text .text.*) *(.rodata .rodata.*) *(.data .data.*)
    . = ALIGN(4); *(.got.plt) __got_start = .; *(.got) __got_end = .; . = ALIGN(4);
  }
  __engine_end = .;
  .bss (IMAGE_BASE + BSS_START) (NOLOAD) : ALIGN(4) {
    *(.bss .bss.*) *(COMMON) . = ALIGN(4);
  }
  .rela.got 0 : { *(.rela.got) }
  /DISCARD/ : { *(.comment .note* .eh_frame* .gnu.attributes) }
  ASSERT(p0_entry == IMAGE_BASE + 256, "fixed bootstrap")
  ASSERT(SIZEOF(.engine) <= 65536, "64 KiB code cap")
  ASSERT(BSS_START <= 65536, "current 64 KiB storage cap")
  ASSERT(BSS_START + SIZEOF(.bss) <= 114688, "112 KiB image+BSS cap")
  ASSERT(__engine_end <= IMAGE_BASE + BSS_START, "BSS overlap")
}
