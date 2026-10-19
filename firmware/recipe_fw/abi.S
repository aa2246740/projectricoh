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
    SAVE_CALLEE
    mv r4,r0
    mv r5,r1
    mv r6,r2
    mv r7,r3
    seth r0,#(\target >> 16)
    or3 r0,r0,#(\target & 0xffff)
    jl r0
    RESTORE_CALLEE
    jmp lr
    .size \name,.-\name
    .endm

    TO_GCC ricoh_recipe_open,rfw_open
    TO_GCC ricoh_recipe_apply,rfw_apply_action
    TO_NATIVE gxr_open,0x200a40b4
    TO_NATIVE gxr_create,0x200a544c
    TO_NATIVE gxr_read,0x200a449c
    TO_NATIVE gxr_write,0x200a45e8
    TO_NATIVE gxr_close,0x200a437c
    TO_NATIVE gxr_delete,0x200a4910
    TO_NATIVE gxr_mkdir,0x200a4958
    TO_NATIVE gxr_alloc,0x2005bf5c
    TO_NATIVE gxr_preview,0x202d6f38
    TO_NATIVE gxr_draw_text,0x201d7170
    TO_NATIVE gxr_ascii,0x201d73e0
    TO_NATIVE gxr_language,0x201dc180
    TO_NATIVE gxr_layer_action,0x201c092c

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
    .global recipe_force_dispatch
    .type recipe_force_dispatch,@function
recipe_force_dispatch:
    /* The displaced seth and following dispatch own r1/r2 here. */
    seth r2,#0x205e
    ldi r1,#8
    st r1,@(-25608,r2)
    bra.l native_image_branch
    .size recipe_force_dispatch,.-recipe_force_dispatch

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

