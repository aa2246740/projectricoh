    .section .text,"ax"
    .macro CALLEE_SAVE
    push r8
    push r9
    push r10
    push r11
    push r12
    push r13
    push lr
    .endm
    .macro CALLEE_RESTORE
    pop lr
    pop r13
    pop r12
    pop r11
    pop r10
    pop r9
    pop r8
    .endm
    .macro NATIVE name, target
    .balign 4
    .global \name
\name:
    seth r6,#(\target >> 16)
    or3 r6,r6,#(\target & 0xffff)
    bra.l .Lnative
    .endm
    NATIVE rv_native_open,0x200a40b4
    NATIVE rv_native_read,0x200a449c
    NATIVE rv_native_close,0x200a437c
    NATIVE rv_native_create,0x200a544c
    NATIVE rv_native_write,0x200a45e8
    NATIVE rv_native_rename,0x200a49d8
    NATIVE rv_native_delete,0x200a4910
    NATIVE rv_native_alloc,0x2005bf5c
    NATIVE rv_native_free,0x2005c038
    NATIVE rv_native_preview,0x202d6f38
    NATIVE rv_native_ascii,0x201d73e0
    NATIVE rv_native_language,0x201dc180
    NATIVE rv_native_layer,0x201c092c
    NATIVE rv_native_draw,0x201fd360
    NATIVE fx_native_rect,0x201d709c
    NATIVE rv_native_unit,0x20063f64
    NATIVE rv_native_sd_id,0x200a3240
    NATIVE rv_native_context,0x2005f228
    NATIVE rv_native_rpc_ready,0x2009359c
    NATIVE rv_native_rpc_limit,0x20094e2c
    .balign 4
.Lnative:
    CALLEE_SAVE
    mv r4,r0
    mv r5,r1
    mv r7,r3
    mv r0,r6
    mv r6,r2
    jl r0
    CALLEE_RESTORE
    jmp lr

    .balign 4
    .global rv_rpc8_native
rv_rpc8_native:
    CALLEE_SAVE
    push r1
    push r0
    ldi r2,#2
    push r2
    seth r0,#0x2009
    or3 r0,r0,#0x005c
    ldi r4,#8
    jl r0
    addi sp,#12
    CALLEE_RESTORE
    jmp lr

    .balign 4
    .global rv_cache_sync
rv_cache_sync:
    ldi r0,#-4
    ld r1,@r0
    and3 r2,r1,#1
    beqz r2,.Lsync_done
    or3 r1,r1,#0x101
    st r1,@r0
.Lsync_done:
    jmp lr

    .balign 4
    .global rv_irq_save
rv_irq_save:
    mvfc r0,psw
    and3 r1,r0,#0xffbf
    mvtc r1,psw
    jmp lr
    .balign 4
    .global rv_irq_restore
rv_irq_restore:
    mvtc r0,psw
    jmp lr
