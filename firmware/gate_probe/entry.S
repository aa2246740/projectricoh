/* Native jl at 0x202871CC enters here. Save r8..r13/lr, then the C body.
 * The caller pops its own r8/lr at 0x202871D0 and does not read our r0. */
    .section .text.entry,"ax"
    .align 2
    .global gate_probe_render
    .type gate_probe_render,@function
gate_probe_render:
    push r8
    push r9
    push r10
    push r11
    push r12
    push r13
    push lr
    bl.l gate_probe_render_body
    pop lr
    pop r13
    pop r12
    pop r11
    pop r10
    pop r9
    pop r8
    ldi r0,#0
    jmp lr
    .size gate_probe_render,.-gate_probe_render
