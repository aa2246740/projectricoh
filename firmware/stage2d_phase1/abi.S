/* All ABI boundaries are scalar/pointer-only and at most four arguments.
 * Native function entries preserve r8..r13/lr. Inline hooks additionally
 * preserve r0..r7 and PSW because a C call is not an inline instruction. */
    .section .text,"ax"
    .macro SAVE_CALLEE
    push r8
    push r9
    push r10
    push r11
    push r12
    push r13
    push lr
    .endm
    .macro RESTORE_CALLEE
    pop lr
    pop r13
    pop r12
    pop r11
    pop r10
    pop r9
    pop r8
    .endm
    .macro SAVE_INLINE
    push r0
    push r1
    push r2
    push r3
    push r4
    push r5
    push r6
    push r7
    SAVE_CALLEE
    mvfc r0,psw
    push r0
    .endm
    .macro RESTORE_INLINE
    pop r0
    mvtc r0,psw
    RESTORE_CALLEE
    pop r7
    pop r6
    pop r5
    pop r4
    pop r3
    pop r2
    pop r1
    pop r0
    .endm
    .macro TO_GCC name, target
    .align 2
    .global \name
    .type \name,@function
\name:
    SAVE_CALLEE
    mv r0,r4
    mv r1,r5
    mv r2,r6
    mv r3,r7
    bl.l \target
    RESTORE_CALLEE
    jmp lr
    .size \name,.-\name
    .endm
    .macro TO_NATIVE name, target
    .align 2
    .global \name
    .type \name,@function
\name:
    /* GCC r6 is caller-saved. Keep r0..r3 intact until the shared bridge. */
    seth r6,#(\target >> 16)
    or3 r6,r6,#(\target & 0xffff)
    bra.l .Lto_native
    .size \name,.-\name
    .endm

    TO_GCC ricoh_recipe_open,rfw_open
    TO_GCC ricoh_recipe_apply,rfw_apply_action
    TO_NATIVE gxr_open,0x200a40b4
    TO_NATIVE gxr_read,0x200a449c
    TO_NATIVE gxr_close,0x200a437c
    TO_NATIVE gxr_alloc,0x2005bf5c
    TO_NATIVE gxr_preview,0x202d6f38
    TO_NATIVE gxr_ascii,0x201d73e0
    TO_NATIVE gxr_language,0x201dc180
    TO_NATIVE gxr_layer_action,0x201c092c
    TO_NATIVE gxr_rpc_ready,0x2009359c
    TO_NATIVE gxr_rpc_limit,0x20094e2c
    TO_NATIVE gxr_thread_context,0x2005f228
    TO_NATIVE gxr_unit_info,0x20063f64

    .align 2
.Lto_native:
    SAVE_CALLEE
    mv r4,r0
    mv r5,r1
    mv r7,r3
    mv r0,r6
    mv r6,r2
    jl r0
    RESTORE_CALLEE
    jmp lr

    .align 2
    .global rfw_rpc8_native
    .type rfw_rpc8_native,@function
rfw_rpc8_native:
    SAVE_CALLEE
    /* Native 0x2009005c reads argc/arg0/arg1 at its entry SP. Its native
     * r5/r6 registers are NOT the RPC argument vector. GCC r0/r1 are ours. */
    push r1
    push r0
    ldi r2,#2
    push r2
    seth r0,#0x2009
    or3 r0,r0,#0x005c
    ldi r4,#8
    jl r0
    addi sp,#12
    RESTORE_CALLEE
    jmp lr
    .size rfw_rpc8_native,.-rfw_rpc8_native

    .align 2
    .global rfw_deep_ownership
    .type rfw_deep_ownership,@function
rfw_deep_ownership:
#if RFW_DEEP_ENABLED
    /* Candidate enablement is identity/link/context preflight, not a lock. */
    bra.l rfw_rpc8_preflight
#else
    ldi r0,#0
    jmp lr
#endif
    .size rfw_deep_ownership,.-rfw_deep_ownership

    .align 2
    .global ricoh_recipe_action
    .type ricoh_recipe_action,@function
ricoh_recipe_action:
    SAVE_INLINE
    bl.l rfw_is_active
    beqz r0,.Laction_original
    RESTORE_INLINE
    bra.l ricoh_recipe_apply
.Laction_original:
    RESTORE_INLINE
    /* Replay the original entry word before resuming its body. */
    push lr
    nop
    bra.l native_action_resume
    .size ricoh_recipe_action,.-ricoh_recipe_action

    .align 2
    .global recipe_live_commit
    .type recipe_live_commit,@function
recipe_live_commit:
    SAVE_INLINE
    bl.l rfw_cursor_commit
    beqz r0,.Llive_closed
    /* Generic native commit returns through the existing pop sequence. */
    RESTORE_INLINE
    bra.l native_commit_epilogue
.Llive_closed:
    RESTORE_INLINE
    seth r11,#0x2022
    bra.l native_commit_resume
    .size recipe_live_commit,.-recipe_live_commit

    .align 2
    .global recipe_fn2_guard
    .type recipe_fn2_guard,@function
recipe_fn2_guard:
    SAVE_INLINE
    bl.l rfw_is_active
    beqz r0,.Lfn_original
    ldi r0,#2
    st r0,@(28,sp) /* saved r8; native handled return */
    RESTORE_INLINE
    bra.l native_fn2_epilogue
.Lfn_original:
    RESTORE_INLINE
    seth r0,#0x2026
    bra.l native_fn2_resume
    .size recipe_fn2_guard,.-recipe_fn2_guard

