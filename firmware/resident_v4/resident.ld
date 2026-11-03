OUTPUT_FORMAT("elf32-m32r")
OUTPUT_ARCH(m32r)
ENTRY(rv4_hook_shared)
PROVIDE(W0_DIAGNOSTIC_ONLY = 0);
PROVIDE(W0_PAYLOAD_BEGIN = 0x2005276c);
SECTIONS {
    . = W0_PAYLOAD_BEGIN;
    payload_begin = .;
    .payload : ALIGN(4) {
        KEEP(*(.text.rv4_hook_*))
        KEEP(*(.text.rv4_continuations))
        *envelope.o(.text .text.* .rodata .rodata.*)
        *trust.o(.rodata .rodata.*)
        *loader.o(.text .text.* .rodata .rodata.*)
        *binding.o(.text .text.* .rodata .rodata.*)
        *runtime.o(.text .text.* .rodata .rodata.*)
        *native.o(.text .text.* .rodata .rodata.*)
        *bridges.o(.text .text.*)
        *ui.o(.text .text.* .rodata .rodata.*)
        *dispatch.o(.text .text.* .rodata .rodata.*)
        *hooks.o(.text .text.* .rodata .rodata.*)
        *hook_metadata.o(.rodata .rodata.*)
        *gates.o(.text.rv4_storage_scope)
        KEEP(*(.budget.storage))
        *gates.o(.text.rv4_unavailable_gate)
        KEEP(*(.budget.boot))
        KEEP(*(.budget.capture .budget.render))
        *gates.o(.text .text.* .rodata .rodata.*)
        *(.text .rodata .rodata.*)
        . = ALIGN(4);
    }
    payload_end = .;
    .root 0x20054600 (NOLOAD) : { root_begin = .; . += 480; }
    .root_pins 0x200547e0 : { KEEP(*(.root_pins)) }
    .root_reserved 0x200547ec (NOLOAD) : { . += 20; root_end = .; }
    .forbidden : {
        *(.data .data.* .bss .bss.* COMMON .sdata* .sbss* .got* .plt* .init* .fini* .ctors* .dtors* .tdata* .tbss*)
    }
    .relocations : { *(.rel.* .rela.*) }
    /DISCARD/ : { *(.comment .note* .eh_frame* .gnu.attributes) }
    ASSERT(root_begin == 0x20054600, "root_begin mismatch")
    ASSERT(root_end == 0x20054800, "root_end mismatch")
    ASSERT(SIZEOF(.root)+SIZEOF(.root_pins)+SIZEOF(.root_reserved)==512,"root must be 512B")
    ASSERT(W0_DIAGNOSTIC_ONLY == 1 || payload_end <= 0x20054538,"payload exceeds 7628B; 200B reserve required")
    ASSERT(SIZEOF(.forbidden)==0,"extra writable global")
    ASSERT(SIZEOF(.relocations)==0,"unresolved relocations")
}
