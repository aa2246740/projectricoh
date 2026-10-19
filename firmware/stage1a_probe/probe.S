/* The caller's format pointer and ISO are already on the Ricoh vararg stack.
   Tail entry into the stock formatter avoids shifting that stack or lr. */
    .section .text.probe,"ax",@progbits
    .align 2
    .global probe_entry
    .global probe_loop
    .global probe_ng
    .global probe_format
    .global __probe_code_end
    .type probe_entry,@function
probe_entry:
    seth r0,#0x2005
    or3 r0,r0,#0x276c
    seth r1,#shigh(probe_entry)
    or3 r1,r1,#low(probe_entry)
    ldi r2,#-1
    nop
probe_loop:
    ldb r3,@r0
    addi r0,#1
    bne r3,r2,probe_ng
    cmpu r0,r1
    bc.s probe_loop
    seth r0,#shigh(probe_ok_string)
    or3 r0,r0,#low(probe_ok_string)
    bra.s probe_format
probe_ng:
    seth r0,#shigh(probe_ng_string)
    or3 r0,r0,#low(probe_ng_string)
probe_format:
    st r0,@sp
    nop
    seth r0,#0x200b
    or3 r0,r0,#0xbc7c
    jmp r0
    nop
__probe_code_end:
    .size probe_entry,.-probe_entry

    .section .rodata.probe,"a",@progbits
    .global probe_ok_string
    .global probe_ng_string
probe_ok_string:
    .asciz "OK %d"
probe_ng_string:
    .asciz "NG %d"
