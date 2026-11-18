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
    /* Each stub is one 16-bit ldi plus a short branch (4 B); targets come
     * from one table. Same register moves and callee-saved set as before. */
    .macro NATIVE name, index
    .global \name
\name:
    ldi r6,#\index
    bra .Lnative_index
    .endm
    .balign 4
    NATIVE rv_native_open,0
    NATIVE rv_native_read,1
    NATIVE rv_native_close,2
    NATIVE rv_native_alloc,3
    NATIVE rv_native_free,4
    NATIVE rv_native_sd_id,5
    NATIVE rv_native_layer,6
    NATIVE rv_native_sleep,7
    .balign 4
    /* 0x2005de00: dly_tsk wrapper. Sleeps (yields) only in task context with
     * IE set; otherwise returns -25 / -28 at once without sleeping. */
.Lnative_targets:
    .long 0x200a40b4,0x200a449c,0x200a437c,0x2005bf5c,0x2005c038,0x200a3240,0x201c092c,0x2005de00
.Lnative_index:
    slli r6,#2
    seth r7,#shigh(.Lnative_targets)
    add3 r7,r7,#low(.Lnative_targets)
    add r6,r7
    ld r6,@r6
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
