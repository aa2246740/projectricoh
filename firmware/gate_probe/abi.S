/* GCC r0..r3 enter the bridge. Native ROM reads r4..r7.
 * Only the three entries named by the gate-probe design are linked. */
    .section .text.abi,"ax"
    .macro TO_NATIVE name, target
    .align 2
    .global \name
    .type \name,@function
\name:
    seth r6,#(\target >> 16)
    or3 r6,r6,#(\target & 0xffff)
    bra.l .Lto_native
    .size \name,.-\name
    .endm

    TO_NATIVE gxr_ascii,0x201d73e0
    TO_NATIVE gxr_language,0x201dc180
    TO_NATIVE gxr_list_paint,0x201fd360

    .align 2
.Lto_native:
    push r8
    push r9
    push r10
    push r11
    push r12
    push r13
    push lr
    mv r4,r0
    mv r5,r1
    mv r7,r3
    mv r0,r6
    mv r6,r2
    jl r0
    pop lr
    pop r13
    pop r12
    pop r11
    pop r10
    pop r9
    pop r8
    jmp lr
