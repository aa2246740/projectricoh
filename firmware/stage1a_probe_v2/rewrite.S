/* Keep both volatile ISO reads and the original 16-byte producer frame.
   Shared exits save space without moving either public entry. */
    .macro producer name, section, node, iso_fmt, low_fmt, normal
    .section \section,"ax",@progbits
    .align 2
    .global \name
    .type \name,@function
\name:
    addi sp,#-8
    push r8
    mv r8,r4
    push lr
    ldi r5,#0
    ldi r6,#5
    add3 r4,sp,#8
\name\()_memset:
    bl memset_stock
    seth r0,#0x205d
    or3 r0,r0,#0xf074
    ldh r0,@r0
    nop
\name\()_nonpositive:
    blez r0,\name\()_invalid
    seth r0,#0x205d
    or3 r0,r0,#0xf074
    ldh r0,@r0
    nop
    cmpi r0,#10000
\name\()_upper:
    bnc.s \name\()_invalid
    bra.s \name\()_format
\name\()_invalid:
    .if \normal
    bra normal_invalid
    .else
\name\()_hidden:
    beqz r8,producer_return
    seth r4,#0x205e
    ldub r4,@(\node,r4)
    ldi r5,#0
    bra.s producer_display
    .endif
\name\()_format:
    push r0
    nop
    seth r0,#0x2037
    or3 r0,r0,#\iso_fmt
    push r0
    nop
    seth r4,#0x2023
    or3 r4,r4,#0x4bd0
\name\()_probe:
    bl probe_entry
    addi sp,#8
    nop
    seth r0,#0x205e
    or3 r0,r0,#0x42f9
    ldub r0,@r0
    nop
\name\()_low_test:
    beqz r0,\name\()_show
    seth r0,#0x2037
    or3 r0,r0,#\low_fmt
    push r0
    nop
    seth r4,#0x2023
    or3 r4,r4,#0x4bd0
\name\()_low_format:
    bl formatter_stock
    addi sp,#4
    nop
\name\()_show:
    seth r4,#0x205e
    ldub r4,@(\node,r4)
    mv r5,r8
    .if \normal
    bra producer_display
    .else
    bra.s producer_display
    .endif
    .size \name,.-\name
    .global \name\()_end
\name\()_end:
    .endm

    producer producer_alt, .text.alt, 17504, 0xbb6e, 0xbb75, 0
    .align 2
    .global producer_display
    .type producer_display,@function
producer_display:
display_call:
    bl display_stock
    .global producer_return
producer_return:
    pop lr
    pop r8
    addi sp,#8
    jmp lr
    .size producer_display,.-producer_display
normal_invalid:
    beqz r8,producer_return
    seth r4,#0x205e
    ldub r4,@(17502,r4)
    ldi r5,#0
    bra.s producer_display
    .global alt_code_end
alt_code_end:
    .global probe_ok_string
    .global probe_ng_string
probe_ok_string:
    .ascii "OK %d\0NG %d\0"
    .set probe_ng_string,probe_ok_string+6

    producer producer_normal, .text.normal, 17502, 0xbb84, 0xbb8b, 1
    .align 2
    .global probe_entry
    .type probe_entry,@function
probe_entry:
    seth r0,#0x2005
    or3 r0,r0,#0x276c
    ldi r1,#8340
    ldi r2,#0
    nop
probe_loop:
    ldb r3,@r0
    addi r0,#1
    addi r3,#1
    or r2,r3
    addi r1,#-1
probe_again:
    bnez r1,probe_loop
    seth r0,#high(probe_ok_string)
    or3 r0,r0,#low(probe_ok_string)
probe_result:
    beqz r2,probe_format
    addi r0,#6
    nop
probe_format:
    st r0,@sp
    nop
probe_tail:
    bra formatter_stock
    .size probe_entry,.-probe_entry
    .global normal_code_end
normal_code_end:
