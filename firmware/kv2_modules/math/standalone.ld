ENTRY(kv_apply_work)
SECTIONS
{
    . = 0x00100000;
    .text : { *(.text*) }
    .rodata : { *(.rodata*) }
    .data : { *(.data*) }
    .bss : { *(.bss*) *(.sbss*) *(COMMON) }
    /DISCARD/ : { *(.comment) *(.note*) }
}
