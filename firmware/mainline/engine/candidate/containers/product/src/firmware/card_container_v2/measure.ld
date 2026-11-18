SECTIONS
{
    . = 0x100000;
    .text : { *(.text .text.*) }
    .rodata : { *(.rodata .rodata.*) }
    .data : { *(.data .data.*) }
    .bss (NOLOAD) : { *(.bss .bss.* COMMON) }
    /DISCARD/ : { *(.comment .note* .eh_frame* .debug* .mdebug* .gnu.attributes) }
}
