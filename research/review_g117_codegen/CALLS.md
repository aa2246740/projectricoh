调用点均为未平移 ELF 地址。实际执行地址等于装载基址加该值。本轮装载基址为 0x21000000。

a4_move

ig_apply，bl，0x8064。
```text
0x8034 bl 6fb0 <ingress>
0x8038 beqz r0,80d0 <ig_apply+0xb8>
0x803c seth r4,#0x1
0x8040 add3 r4,r4,#-4352
0x8044 add r4,r12
0x8048 ldub r5,@(2072,r4)
0x804c beqz r5,80d0 <ig_apply+0xb8>
0x8050 ldi r5,#1
0x8054 stb r5,@(2082,r4)
0x8058 ldub r4,@(550,r4)
0x805c beqz r4,8080 <ig_apply+0x68>
0x8060 ld r0,@(40,r9)
0x8064 bl 42c8 <a4_move>
0x8068 mv r1,r0
0x806c mv r0,r8
```

ig_panel_event，bl，0x8634。
```text
0x8608 mv r9,r2
0x860a mv r8,r3
0x860c bl 6fb0 <ingress>
0x8610 beqz r0,8650 <ig_panel_event+0x60>
0x8614 seth r4,#0x1
0x8618 add3 r4,r4,#-4352
0x861c add r4,r12
0x8620 ldub r5,@(2072,r4)
0x8624 beqz r5,8650 <ig_panel_event+0x60>
0x8628 ldi r5,#1
0x862c stb r5,@(2082,r4)
0x8630 ld r0,@(40,r9)
0x8634 bl 42c8 <a4_move>
0x8638 mv r1,r0
0x863c mv r0,r8
```


binding

ig_bootstrap，bl，0xab14。
```text
0xaae4 bl 13c <ig_copy>
0xaae8 ldi r1,#4096
0xaaec add3 r0,r9,#2060
0xaaf0 ldi r5,#0
0xaaf4 stb r5,@(8,r8)
0xaaf8 stb r5,@(10,r8)
0xaafc ldi r7,#2
0xab00 stb r7,@(9,r8)
0xab04 ldi r5,#-128
0xab08 stb r5,@(11,r8)
0xab0c bl 184 <p32>
0xab10 add3 r0,r9,#2068
0xab14 bl 1a4 <binding>
0xab18 ld r1,@(64,r11)
0xab1c add3 r0,r9,#2084
```

ig_bootstrap，bl，0xabcc。
```text
0xab9c bl 13c <ig_copy>
0xaba0 add3 r0,r9,#12
0xaba4 ldi r7,#0
0xaba8 stb r7,@(8,r9)
0xabac stb r7,@(10,r9)
0xabb0 ldi r2,#1
0xabb4 stb r2,@(9,r9)
0xabb8 ldi r7,#-128
0xabbc stb r7,@(11,r9)
0xabc0 ld r1,@(148,r11)
0xabc4 bl 184 <p32>
0xabc8 add3 r0,r9,#56
0xabcc bl 1a4 <binding>
0xabd0 ld r1,@(64,sp)
0xabd4 add3 r0,r9,#72
```


card

ig_bootstrap，bl，0xaa84。
```text
0xaa5c push lr
0xaa5e bl aa60 <ig_bootstrap+0x10>
0xaa60 seth r12,#0xffff
0xaa64 add3 r12,r12,#22176
0xaa68 add r12,lr
0xaa6a addi sp,#-72
0xaa6c ld lr,@(72,sp)
0xaa70 st r3,@(60,sp)
0xaa74 bl 6fb0 <ingress>
0xaa78 beqz r0,ae90 <ig_bootstrap+0x440>
0xaa7c add3 fp,sp,#40
0xaa80 mv r0,fp
0xaa84 bl 6c3c <card>
0xaa88 bnez r0,ad68 <ig_bootstrap+0x318>
0xaa8c seth r4,#0x1
```

ig_bootstrap，bl，0xaddc。
```text
0xadb0 add3 r1,sp,#56
0xadb4 ldi r2,#1
0xadb6 mv r0,r8
0xadb8 bl aebc <rv_native_read>
0xadbc mv r9,r0
0xadc0 mv r0,r8
0xadc4 bl aec8 <rv_native_close>
0xadc8 beqz r10,aa8c <ig_bootstrap+0x3c>
0xadcc or r9,r0
0xadd0 bnez r9,aa8c <ig_bootstrap+0x3c>
0xadd4 add3 r8,sp,#24
0xadd8 mv r0,r8
0xaddc bl 6c3c <card>
0xade0 beqz r0,aa8c <ig_bootstrap+0x3c>
0xade4 ldi r2,#16
```


close_once

remove_owned，bl，0x162c。
```text
0x1608 ld lr,@(4,sp)
0x160c and r4,r5
0x160e mv fp,r0
0x1610 mv r8,r1
0x1612 mv r10,r2
0x1614 mv r9,r3
0x1618 beqz r4,16a0 <remove_owned+0xc0>
0x161c mv r3,sp
0x1620 bl 1380 <open_read>
0x1624 bnez r0,168c <remove_owned+0xac>
0x1628 ld r1,@sp
0x162a mv r0,fp
0x162c bl 1454 <close_once>
0x1630 bnez r0,168c <remove_owned+0xac>
0x1634 seth r11,#0x1
```

io_close，bl，0x3650。
```text
0x3620 bl 3624 <io_close+0x18>
0x3624 seth r12,#0x0
0x3628 add3 r12,r12,#-13604
0x362c add r12,lr
0x3630 ldub r8,@(370,r0)
0x3634 addi sp,#-44
0x3638 ld lr,@(44,sp)
0x363c mv r10,r0
0x3640 bne r6,r1,3890 <io_close+0x284>
0x3644 ldi r5,#0
0x3648 st r5,@(388,r0)
0x364c ld r0,@r0
0x3650 bl 1454 <close_once>
0x3654 st r0,@(28,sp)
0x3658 add3 r5,r8,#-2
```


core_call

ig_menu，bl，0x7d4c。
```text
0x7d20 st r4,@(2092,r8)
0x7d24 seth r4,#0x1
0x7d28 add3 r4,r4,#-8744
0x7d2c st r11,@(12,sp)
0x7d30 add r4,r12
0x7d34 st r4,@(16,sp)
0x7d38 ldi r4,#32
0x7d3c st r4,@(8,sp)
0x7d40 add3 r4,r8,#2092
0x7d44 st r4,@(4,sp)
0x7d48 ldi r4,#4
0x7d4a st r4,@sp
0x7d4c bl 2f8 <core_call>
0x7d50 mv r11,r0
0x7d54 bnez r0,7ed8 <ig_menu+0x354>
```

地址引用：{"pc": "0x7540", "kind": "encoded GOTOFF function address", "target": "core_call", "owner": "ig_init"}

current.constprop.0

rv_call，bl，0x94c8。
```text
0x94a4 ldi r4,#-5
0x94a6 and r4,r7
0x94a8 addi r4,#-9
0x94ac beqz r4,947c <rv_call+0xc3c>
0x94b0 add3 r4,r11,#-1
0x94b4 bnez r4,94c4 <rv_call+0xc84>
0x94b8 mv r4,r7
0x94ba addi r4,#-6
0x94bc ldi r5,#2
0x94be cmpu r5,r4
0x94c0 bnc 947c <rv_call+0xc3c>
0x94c4 mv r0,fp
0x94c8 bl 87d8 <current.constprop.0>
0x94cc cmpui r0,#1
0x94d0 mvfc r4,cbr
```

rv_call，bl，0x979c。
```text
0x976c ld r6,@(16,sp)
0x9770 mv r8,r11
0x9774 add3 r5,r6,#180
0x9778 ld r6,@r5
0x977c bnez r6,97a8 <rv_call+0xf68>
0x9780 bl 33dc <token.constprop.0>
0x9784 mv r11,r0
0x9788 beqz r0,a8f8 <rv_call+0x20b8>
0x978c ld r0,@(28,sp)
0x9790 bl af04 <rv_native_alloc>
0x9794 mv r10,r0
0x9798 mv r0,fp
0x979c bl 87d8 <current.constprop.0>
0x97a0 bnez r0,97f4 <rv_call+0xfb4>
0x97a4 ldi r10,#-5
```

rv_call，bl，0x9bac。
```text
0x9b80 ldi r5,#4
0x9b82 or r5,r6
0x9b84 st r5,@(212,r4)
0x9b88 ldi r4,#1
0x9b8c st r4,@(388,r3)
0x9b90 ldi r0,#22
0x9b94 ld r1,@(28,sp)
0x9b98 bl afc0 <rv_rpc8_native>
0x9b9c ld r4,@(24,sp)
0x9ba0 mv r8,r0
0x9ba4 st r0,@(8,r4)
0x9ba8 mv r0,fp
0x9bac bl 87d8 <current.constprop.0>
0x9bb0 beqz r0,97a4 <rv_call+0xf64>
0x9bb4 ld24 r4,ffff <n+0xfff>
```

rv_call，bl，0xa6e8。
```text
0xa6c0 mv r5,r11
0xa6c2 sub r5,r4
0xa6c4 cmpu r5,r6
0xa6c8 mvfc r5,cbr
0xa6cc bnez r5,9e5c <rv_call+0x161c>
0xa6d0 ld r3,@(32,r9)
0xa6d4 mv r0,r11
0xa6d6 mv r2,r4
0xa6d8 bl af28 <rv_native_ascii>
0xa6dc ld r11,@(24,sp)
0xa6e0 st r0,@(8,r11)
0xa6e4 mv r0,fp
0xa6e8 bl 87d8 <current.constprop.0>
0xa6ec beqz r0,97a4 <rv_call+0xf64>
0xa6f0 ld r6,@(24,r9)
```

rv_call，bl，0xa900。
```text
0xa8d4 add3 r5,r11,#-1
0xa8d8 bnez r5,97bc <rv_call+0xf7c>
0xa8dc ld r2,@(20,sp)
0xa8e0 mv r1,r9
0xa8e2 ldi r0,#-1
0xa8e4 bl 2320 <gxr2_crc_add>
0xa8e8 ld r4,@(24,sp)
0xa8ec not r0,r0
0xa8f0 st r0,@(28,r4)
0xa8f4 bra 99d8 <rv_call+0x1198>
0xa8f8 ldi r10,#-11
0xa8fc bra 97bc <rv_call+0xf7c>
0xa900 bl 87d8 <current.constprop.0>
0xa904 bra 97e0 <rv_call+0xfa0>
0xa908 bnez r4,93e0 <rv_call+0xba0>
```


descriptor.lto_priv.0

slot_descriptor，bl，0xd0a。
```text
0xcea bl afc <metadata.lto_priv.0>
0xcec lduh r5,@(76,r8)
0xcf0 sll3 r4,r5,#1
0xcf4 add r4,r5
0xcf6 add r0,r4
0xcf8 ldub r5,@(1,r0)
0xcfc ldi r4,#1
0xcfe and r4,r5
0xd00 beqz r4,d1c <slot_descriptor+0x6c>
0xd04 ldub r2,@r0
0xd06 mv r1,r9
0xd08 mv r0,r8
0xd0a bl b48 <descriptor.lto_priv.0>
0xd0c mv r8,r0
0xd10 pop lr
```

gxr2_semantic_validate，bl，0x2414。
```text
0x23f0 st r6,@(72,sp)
0x23f4 add r4,r6
0x23f6 add r4,r9
0x23f8 st r4,@(64,sp)
0x23fc mv r0,r4
0x23fe addi r0,#12
0x2400 bl 104 <be32.lto_priv.0>
0x2404 ld r1,@(80,sp)
0x2408 mv r8,r9
0x240a add r8,r0
0x240c ld r0,@(52,sp)
0x2410 ldi r2,#0
0x2414 bl b48 <descriptor.lto_priv.0>
0x2418 seth r1,#0x1
0x241c add3 r1,r1,#-20668
```

gxr2_semantic_validate，bl，0x2ff8。
```text
0x2fd0 ld r6,@(68,sp)
0x2fd4 cmpu r8,r6
0x2fd6 bnc 3050 <gxr2_semantic_validate+0xcc8>
0x2fd8 add3 r4,r11,#-4
0x2fdc bnez r4,2fec <gxr2_semantic_validate+0xc64>
0x2fe0 bnez r8,3050 <gxr2_semantic_validate+0xcc8>
0x2fe4 add3 r4,r5,#-3
0x2fe8 bnez r4,3050 <gxr2_semantic_validate+0xcc8>
0x2fec ld r0,@(52,sp)
0x2ff0 st r5,@(128,sp)
0x2ff4 mv r2,r8
0x2ff6 mv r1,r10
0x2ff8 bl b48 <descriptor.lto_priv.0>
0x2ffc ld r5,@(128,sp)
0x3000 ldi r4,#2
```

gxr2_semantic_validate，bl，0x31c4。
```text
0x319c beqz r8,3050 <gxr2_semantic_validate+0xcc8>
0x31a0 ldub r4,@r0
0x31a4 bne r11,r4,3050 <gxr2_semantic_validate+0xcc8>
0x31a8 ld r5,@(56,sp)
0x31ac ldi r4,#1
0x31ae sll r4,r8
0x31b0 or r5,r4
0x31b4 st r5,@(56,sp)
0x31b8 bra 309c <gxr2_semantic_validate+0xd14>
0x31bc ld r0,@(52,sp)
0x31c0 mv r2,r8
0x31c2 mv r1,r10
0x31c4 bl b48 <descriptor.lto_priv.0>
0x31c8 ldub r2,@r0
0x31cc mv r1,r10
```

gate_validate.constprop.0，bl，0x6370。
```text
0x634a addi r10,#12
0x634c bnez r6,62bc <gate_validate.constprop.0+0x89c>
0x6350 bne r4,r11,5ef0 <gate_validate.constprop.0+0x4d0>
0x6354 ld r9,@(20,sp)
0x6358 ldi r10,#0
0x635a addi r9,#12
0x635c add r9,r8
0x6360 seth r0,#0x1
0x6364 add3 r0,r0,#-9956
0x6368 ldi r2,#0
0x636a mv r1,r10
0x636c add r0,r12
0x6370 bl b48 <descriptor.lto_priv.0>
0x6374 ldub r5,@r0
0x6378 mv r11,r0
```

verify，bl，0x6734。
```text
0x6708 beqz r6,6be0 <verify+0x6d8>
0x670c ld r6,@(100,sp)
0x6710 add3 r0,r9,#68
0x6714 ld r5,@(116,sp)
0x6718 slli r6,#0x6
0x671c ld r4,@(104,sp)
0x6720 add r5,r6
0x6724 ld r1,@(100,sp)
0x6728 st r5,@(116,sp)
0x672c ldub r2,@r7
0x672e add r4,r5
0x6730 st r4,@(112,sp)
0x6734 bl b48 <descriptor.lto_priv.0>
0x6738 st r0,@(120,sp)
0x673c ld r0,@(112,sp)
```

verify，bl，0x6950。
```text
0x6920 ldi r2,#236
0x6924 seth r10,#0x1
0x6928 add3 r10,r10,#-6828
0x692c add r1,r12
0x6930 stb r4,@(233,r1)
0x6934 stb r5,@(232,r1)
0x6938 add r0,r12
0x693c bl 13c <ig_copy>
0x6940 ld r1,@(100,sp)
0x6944 add r10,r12
0x6948 add3 r0,r10,#68
0x694c ldi r2,#0
0x6950 bl b48 <descriptor.lto_priv.0>
0x6954 st r0,@(112,sp)
0x6958 ld r0,@(116,sp)
```

ig_init，bl，0x7a00。
```text
0x79d6 add r1,r0
0x79d8 ldi r0,#-1
0x79dc bl 2320 <gxr2_crc_add>
0x79e0 mv r10,r0
0x79e4 ldi fp,#0
0x79e8 ld r1,@(84,sp)
0x79ec seth r5,#0x1
0x79f0 add3 r5,r5,#-8160
0x79f4 add r5,r12
0x79f8 st r5,@(132,sp)
0x79fc ldi r2,#0
0x79fe mv r0,r5
0x7a00 bl b48 <descriptor.lto_priv.0>
0x7a04 ld r5,@(132,sp)
0x7a08 mv r2,fp
```

ig_init，bl，0x7a3c。
```text
0x7a14 srl3 r2,r1,#16
0x7a18 mv r1,r0
0x7a1a mv r0,r10
0x7a1c bl 2320 <gxr2_crc_add>
0x7a20 addi fp,#1
0x7a24 add3 r5,fp,#-10
0x7a28 mv r10,r0
0x7a2c bnez r5,79e8 <ig_init+0x698>
0x7a30 ld r1,@(84,sp)
0x7a34 mv r0,r11
0x7a36 ldi r2,#0
0x7a38 add r0,r12
0x7a3c bl b48 <descriptor.lto_priv.0>
0x7a40 add3 r1,r0,#2
0x7a44 ldi r2,#2
```


descriptor.lto_priv.1

slot_descriptor，bl，0xd0a。
```text
0xcea bl afc <metadata.lto_priv.0>
0xcec lduh r5,@(76,r8)
0xcf0 sll3 r4,r5,#1
0xcf4 add r4,r5
0xcf6 add r0,r4
0xcf8 ldub r5,@(1,r0)
0xcfc ldi r4,#1
0xcfe and r4,r5
0xd00 beqz r4,d1c <slot_descriptor+0x6c>
0xd04 ldub r2,@r0
0xd06 mv r1,r9
0xd08 mv r0,r8
0xd0a bl b48 <descriptor.lto_priv.0>
0xd0c mv r8,r0
0xd10 pop lr
```

gxr2_semantic_validate，bl，0x2414。
```text
0x23f0 st r6,@(72,sp)
0x23f4 add r4,r6
0x23f6 add r4,r9
0x23f8 st r4,@(64,sp)
0x23fc mv r0,r4
0x23fe addi r0,#12
0x2400 bl 104 <be32.lto_priv.0>
0x2404 ld r1,@(80,sp)
0x2408 mv r8,r9
0x240a add r8,r0
0x240c ld r0,@(52,sp)
0x2410 ldi r2,#0
0x2414 bl b48 <descriptor.lto_priv.0>
0x2418 seth r1,#0x1
0x241c add3 r1,r1,#-20668
```

gxr2_semantic_validate，bl，0x2ff8。
```text
0x2fd0 ld r6,@(68,sp)
0x2fd4 cmpu r8,r6
0x2fd6 bnc 3050 <gxr2_semantic_validate+0xcc8>
0x2fd8 add3 r4,r11,#-4
0x2fdc bnez r4,2fec <gxr2_semantic_validate+0xc64>
0x2fe0 bnez r8,3050 <gxr2_semantic_validate+0xcc8>
0x2fe4 add3 r4,r5,#-3
0x2fe8 bnez r4,3050 <gxr2_semantic_validate+0xcc8>
0x2fec ld r0,@(52,sp)
0x2ff0 st r5,@(128,sp)
0x2ff4 mv r2,r8
0x2ff6 mv r1,r10
0x2ff8 bl b48 <descriptor.lto_priv.0>
0x2ffc ld r5,@(128,sp)
0x3000 ldi r4,#2
```

gxr2_semantic_validate，bl，0x31c4。
```text
0x319c beqz r8,3050 <gxr2_semantic_validate+0xcc8>
0x31a0 ldub r4,@r0
0x31a4 bne r11,r4,3050 <gxr2_semantic_validate+0xcc8>
0x31a8 ld r5,@(56,sp)
0x31ac ldi r4,#1
0x31ae sll r4,r8
0x31b0 or r5,r4
0x31b4 st r5,@(56,sp)
0x31b8 bra 309c <gxr2_semantic_validate+0xd14>
0x31bc ld r0,@(52,sp)
0x31c0 mv r2,r8
0x31c2 mv r1,r10
0x31c4 bl b48 <descriptor.lto_priv.0>
0x31c8 ldub r2,@r0
0x31cc mv r1,r10
```

gate_validate.constprop.0，bl，0x6370。
```text
0x634a addi r10,#12
0x634c bnez r6,62bc <gate_validate.constprop.0+0x89c>
0x6350 bne r4,r11,5ef0 <gate_validate.constprop.0+0x4d0>
0x6354 ld r9,@(20,sp)
0x6358 ldi r10,#0
0x635a addi r9,#12
0x635c add r9,r8
0x6360 seth r0,#0x1
0x6364 add3 r0,r0,#-9956
0x6368 ldi r2,#0
0x636a mv r1,r10
0x636c add r0,r12
0x6370 bl b48 <descriptor.lto_priv.0>
0x6374 ldub r5,@r0
0x6378 mv r11,r0
```

verify，bl，0x6734。
```text
0x6708 beqz r6,6be0 <verify+0x6d8>
0x670c ld r6,@(100,sp)
0x6710 add3 r0,r9,#68
0x6714 ld r5,@(116,sp)
0x6718 slli r6,#0x6
0x671c ld r4,@(104,sp)
0x6720 add r5,r6
0x6724 ld r1,@(100,sp)
0x6728 st r5,@(116,sp)
0x672c ldub r2,@r7
0x672e add r4,r5
0x6730 st r4,@(112,sp)
0x6734 bl b48 <descriptor.lto_priv.0>
0x6738 st r0,@(120,sp)
0x673c ld r0,@(112,sp)
```

verify，bl，0x6950。
```text
0x6920 ldi r2,#236
0x6924 seth r10,#0x1
0x6928 add3 r10,r10,#-6828
0x692c add r1,r12
0x6930 stb r4,@(233,r1)
0x6934 stb r5,@(232,r1)
0x6938 add r0,r12
0x693c bl 13c <ig_copy>
0x6940 ld r1,@(100,sp)
0x6944 add r10,r12
0x6948 add3 r0,r10,#68
0x694c ldi r2,#0
0x6950 bl b48 <descriptor.lto_priv.0>
0x6954 st r0,@(112,sp)
0x6958 ld r0,@(116,sp)
```

ig_init，bl，0x7a00。
```text
0x79d6 add r1,r0
0x79d8 ldi r0,#-1
0x79dc bl 2320 <gxr2_crc_add>
0x79e0 mv r10,r0
0x79e4 ldi fp,#0
0x79e8 ld r1,@(84,sp)
0x79ec seth r5,#0x1
0x79f0 add3 r5,r5,#-8160
0x79f4 add r5,r12
0x79f8 st r5,@(132,sp)
0x79fc ldi r2,#0
0x79fe mv r0,r5
0x7a00 bl b48 <descriptor.lto_priv.0>
0x7a04 ld r5,@(132,sp)
0x7a08 mv r2,fp
```

ig_init，bl，0x7a3c。
```text
0x7a14 srl3 r2,r1,#16
0x7a18 mv r1,r0
0x7a1a mv r0,r10
0x7a1c bl 2320 <gxr2_crc_add>
0x7a20 addi fp,#1
0x7a24 add3 r5,fp,#-10
0x7a28 mv r10,r0
0x7a2c bnez r5,79e8 <ig_init+0x698>
0x7a30 ld r1,@(84,sp)
0x7a34 mv r0,r11
0x7a36 ldi r2,#0
0x7a38 add r0,r12
0x7a3c bl b48 <descriptor.lto_priv.0>
0x7a40 add3 r1,r0,#2
0x7a44 ldi r2,#2
```


descriptor.lto_priv.2

slot_descriptor，bl，0xd0a。
```text
0xcea bl afc <metadata.lto_priv.0>
0xcec lduh r5,@(76,r8)
0xcf0 sll3 r4,r5,#1
0xcf4 add r4,r5
0xcf6 add r0,r4
0xcf8 ldub r5,@(1,r0)
0xcfc ldi r4,#1
0xcfe and r4,r5
0xd00 beqz r4,d1c <slot_descriptor+0x6c>
0xd04 ldub r2,@r0
0xd06 mv r1,r9
0xd08 mv r0,r8
0xd0a bl b48 <descriptor.lto_priv.0>
0xd0c mv r8,r0
0xd10 pop lr
```

gxr2_semantic_validate，bl，0x2414。
```text
0x23f0 st r6,@(72,sp)
0x23f4 add r4,r6
0x23f6 add r4,r9
0x23f8 st r4,@(64,sp)
0x23fc mv r0,r4
0x23fe addi r0,#12
0x2400 bl 104 <be32.lto_priv.0>
0x2404 ld r1,@(80,sp)
0x2408 mv r8,r9
0x240a add r8,r0
0x240c ld r0,@(52,sp)
0x2410 ldi r2,#0
0x2414 bl b48 <descriptor.lto_priv.0>
0x2418 seth r1,#0x1
0x241c add3 r1,r1,#-20668
```

gxr2_semantic_validate，bl，0x2ff8。
```text
0x2fd0 ld r6,@(68,sp)
0x2fd4 cmpu r8,r6
0x2fd6 bnc 3050 <gxr2_semantic_validate+0xcc8>
0x2fd8 add3 r4,r11,#-4
0x2fdc bnez r4,2fec <gxr2_semantic_validate+0xc64>
0x2fe0 bnez r8,3050 <gxr2_semantic_validate+0xcc8>
0x2fe4 add3 r4,r5,#-3
0x2fe8 bnez r4,3050 <gxr2_semantic_validate+0xcc8>
0x2fec ld r0,@(52,sp)
0x2ff0 st r5,@(128,sp)
0x2ff4 mv r2,r8
0x2ff6 mv r1,r10
0x2ff8 bl b48 <descriptor.lto_priv.0>
0x2ffc ld r5,@(128,sp)
0x3000 ldi r4,#2
```

gxr2_semantic_validate，bl，0x31c4。
```text
0x319c beqz r8,3050 <gxr2_semantic_validate+0xcc8>
0x31a0 ldub r4,@r0
0x31a4 bne r11,r4,3050 <gxr2_semantic_validate+0xcc8>
0x31a8 ld r5,@(56,sp)
0x31ac ldi r4,#1
0x31ae sll r4,r8
0x31b0 or r5,r4
0x31b4 st r5,@(56,sp)
0x31b8 bra 309c <gxr2_semantic_validate+0xd14>
0x31bc ld r0,@(52,sp)
0x31c0 mv r2,r8
0x31c2 mv r1,r10
0x31c4 bl b48 <descriptor.lto_priv.0>
0x31c8 ldub r2,@r0
0x31cc mv r1,r10
```

gate_validate.constprop.0，bl，0x6370。
```text
0x634a addi r10,#12
0x634c bnez r6,62bc <gate_validate.constprop.0+0x89c>
0x6350 bne r4,r11,5ef0 <gate_validate.constprop.0+0x4d0>
0x6354 ld r9,@(20,sp)
0x6358 ldi r10,#0
0x635a addi r9,#12
0x635c add r9,r8
0x6360 seth r0,#0x1
0x6364 add3 r0,r0,#-9956
0x6368 ldi r2,#0
0x636a mv r1,r10
0x636c add r0,r12
0x6370 bl b48 <descriptor.lto_priv.0>
0x6374 ldub r5,@r0
0x6378 mv r11,r0
```

verify，bl，0x6734。
```text
0x6708 beqz r6,6be0 <verify+0x6d8>
0x670c ld r6,@(100,sp)
0x6710 add3 r0,r9,#68
0x6714 ld r5,@(116,sp)
0x6718 slli r6,#0x6
0x671c ld r4,@(104,sp)
0x6720 add r5,r6
0x6724 ld r1,@(100,sp)
0x6728 st r5,@(116,sp)
0x672c ldub r2,@r7
0x672e add r4,r5
0x6730 st r4,@(112,sp)
0x6734 bl b48 <descriptor.lto_priv.0>
0x6738 st r0,@(120,sp)
0x673c ld r0,@(112,sp)
```

verify，bl，0x6950。
```text
0x6920 ldi r2,#236
0x6924 seth r10,#0x1
0x6928 add3 r10,r10,#-6828
0x692c add r1,r12
0x6930 stb r4,@(233,r1)
0x6934 stb r5,@(232,r1)
0x6938 add r0,r12
0x693c bl 13c <ig_copy>
0x6940 ld r1,@(100,sp)
0x6944 add r10,r12
0x6948 add3 r0,r10,#68
0x694c ldi r2,#0
0x6950 bl b48 <descriptor.lto_priv.0>
0x6954 st r0,@(112,sp)
0x6958 ld r0,@(116,sp)
```

ig_init，bl，0x7a00。
```text
0x79d6 add r1,r0
0x79d8 ldi r0,#-1
0x79dc bl 2320 <gxr2_crc_add>
0x79e0 mv r10,r0
0x79e4 ldi fp,#0
0x79e8 ld r1,@(84,sp)
0x79ec seth r5,#0x1
0x79f0 add3 r5,r5,#-8160
0x79f4 add r5,r12
0x79f8 st r5,@(132,sp)
0x79fc ldi r2,#0
0x79fe mv r0,r5
0x7a00 bl b48 <descriptor.lto_priv.0>
0x7a04 ld r5,@(132,sp)
0x7a08 mv r2,fp
```

ig_init，bl，0x7a3c。
```text
0x7a14 srl3 r2,r1,#16
0x7a18 mv r1,r0
0x7a1a mv r0,r10
0x7a1c bl 2320 <gxr2_crc_add>
0x7a20 addi fp,#1
0x7a24 add3 r5,fp,#-10
0x7a28 mv r10,r0
0x7a2c bnez r5,79e8 <ig_init+0x698>
0x7a30 ld r1,@(84,sp)
0x7a34 mv r0,r11
0x7a36 ldi r2,#0
0x7a38 add r0,r12
0x7a3c bl b48 <descriptor.lto_priv.0>
0x7a40 add3 r1,r0,#2
0x7a44 ldi r2,#2
```


descriptor.lto_priv.3

slot_descriptor，bl，0xd0a。
```text
0xcea bl afc <metadata.lto_priv.0>
0xcec lduh r5,@(76,r8)
0xcf0 sll3 r4,r5,#1
0xcf4 add r4,r5
0xcf6 add r0,r4
0xcf8 ldub r5,@(1,r0)
0xcfc ldi r4,#1
0xcfe and r4,r5
0xd00 beqz r4,d1c <slot_descriptor+0x6c>
0xd04 ldub r2,@r0
0xd06 mv r1,r9
0xd08 mv r0,r8
0xd0a bl b48 <descriptor.lto_priv.0>
0xd0c mv r8,r0
0xd10 pop lr
```

gxr2_semantic_validate，bl，0x2414。
```text
0x23f0 st r6,@(72,sp)
0x23f4 add r4,r6
0x23f6 add r4,r9
0x23f8 st r4,@(64,sp)
0x23fc mv r0,r4
0x23fe addi r0,#12
0x2400 bl 104 <be32.lto_priv.0>
0x2404 ld r1,@(80,sp)
0x2408 mv r8,r9
0x240a add r8,r0
0x240c ld r0,@(52,sp)
0x2410 ldi r2,#0
0x2414 bl b48 <descriptor.lto_priv.0>
0x2418 seth r1,#0x1
0x241c add3 r1,r1,#-20668
```

gxr2_semantic_validate，bl，0x2ff8。
```text
0x2fd0 ld r6,@(68,sp)
0x2fd4 cmpu r8,r6
0x2fd6 bnc 3050 <gxr2_semantic_validate+0xcc8>
0x2fd8 add3 r4,r11,#-4
0x2fdc bnez r4,2fec <gxr2_semantic_validate+0xc64>
0x2fe0 bnez r8,3050 <gxr2_semantic_validate+0xcc8>
0x2fe4 add3 r4,r5,#-3
0x2fe8 bnez r4,3050 <gxr2_semantic_validate+0xcc8>
0x2fec ld r0,@(52,sp)
0x2ff0 st r5,@(128,sp)
0x2ff4 mv r2,r8
0x2ff6 mv r1,r10
0x2ff8 bl b48 <descriptor.lto_priv.0>
0x2ffc ld r5,@(128,sp)
0x3000 ldi r4,#2
```

gxr2_semantic_validate，bl，0x31c4。
```text
0x319c beqz r8,3050 <gxr2_semantic_validate+0xcc8>
0x31a0 ldub r4,@r0
0x31a4 bne r11,r4,3050 <gxr2_semantic_validate+0xcc8>
0x31a8 ld r5,@(56,sp)
0x31ac ldi r4,#1
0x31ae sll r4,r8
0x31b0 or r5,r4
0x31b4 st r5,@(56,sp)
0x31b8 bra 309c <gxr2_semantic_validate+0xd14>
0x31bc ld r0,@(52,sp)
0x31c0 mv r2,r8
0x31c2 mv r1,r10
0x31c4 bl b48 <descriptor.lto_priv.0>
0x31c8 ldub r2,@r0
0x31cc mv r1,r10
```

gate_validate.constprop.0，bl，0x6370。
```text
0x634a addi r10,#12
0x634c bnez r6,62bc <gate_validate.constprop.0+0x89c>
0x6350 bne r4,r11,5ef0 <gate_validate.constprop.0+0x4d0>
0x6354 ld r9,@(20,sp)
0x6358 ldi r10,#0
0x635a addi r9,#12
0x635c add r9,r8
0x6360 seth r0,#0x1
0x6364 add3 r0,r0,#-9956
0x6368 ldi r2,#0
0x636a mv r1,r10
0x636c add r0,r12
0x6370 bl b48 <descriptor.lto_priv.0>
0x6374 ldub r5,@r0
0x6378 mv r11,r0
```

verify，bl，0x6734。
```text
0x6708 beqz r6,6be0 <verify+0x6d8>
0x670c ld r6,@(100,sp)
0x6710 add3 r0,r9,#68
0x6714 ld r5,@(116,sp)
0x6718 slli r6,#0x6
0x671c ld r4,@(104,sp)
0x6720 add r5,r6
0x6724 ld r1,@(100,sp)
0x6728 st r5,@(116,sp)
0x672c ldub r2,@r7
0x672e add r4,r5
0x6730 st r4,@(112,sp)
0x6734 bl b48 <descriptor.lto_priv.0>
0x6738 st r0,@(120,sp)
0x673c ld r0,@(112,sp)
```

verify，bl，0x6950。
```text
0x6920 ldi r2,#236
0x6924 seth r10,#0x1
0x6928 add3 r10,r10,#-6828
0x692c add r1,r12
0x6930 stb r4,@(233,r1)
0x6934 stb r5,@(232,r1)
0x6938 add r0,r12
0x693c bl 13c <ig_copy>
0x6940 ld r1,@(100,sp)
0x6944 add r10,r12
0x6948 add3 r0,r10,#68
0x694c ldi r2,#0
0x6950 bl b48 <descriptor.lto_priv.0>
0x6954 st r0,@(112,sp)
0x6958 ld r0,@(116,sp)
```

ig_init，bl，0x7a00。
```text
0x79d6 add r1,r0
0x79d8 ldi r0,#-1
0x79dc bl 2320 <gxr2_crc_add>
0x79e0 mv r10,r0
0x79e4 ldi fp,#0
0x79e8 ld r1,@(84,sp)
0x79ec seth r5,#0x1
0x79f0 add3 r5,r5,#-8160
0x79f4 add r5,r12
0x79f8 st r5,@(132,sp)
0x79fc ldi r2,#0
0x79fe mv r0,r5
0x7a00 bl b48 <descriptor.lto_priv.0>
0x7a04 ld r5,@(132,sp)
0x7a08 mv r2,fp
```

ig_init，bl，0x7a3c。
```text
0x7a14 srl3 r2,r1,#16
0x7a18 mv r1,r0
0x7a1a mv r0,r10
0x7a1c bl 2320 <gxr2_crc_add>
0x7a20 addi fp,#1
0x7a24 add3 r5,fp,#-10
0x7a28 mv r10,r0
0x7a2c bnez r5,79e8 <ig_init+0x698>
0x7a30 ld r1,@(84,sp)
0x7a34 mv r0,r11
0x7a36 ldi r2,#0
0x7a38 add r0,r12
0x7a3c bl b48 <descriptor.lto_priv.0>
0x7a40 add3 r1,r0,#2
0x7a44 ldi r2,#2
```


descriptor.lto_priv.4

slot_descriptor，bl，0xd0a。
```text
0xcea bl afc <metadata.lto_priv.0>
0xcec lduh r5,@(76,r8)
0xcf0 sll3 r4,r5,#1
0xcf4 add r4,r5
0xcf6 add r0,r4
0xcf8 ldub r5,@(1,r0)
0xcfc ldi r4,#1
0xcfe and r4,r5
0xd00 beqz r4,d1c <slot_descriptor+0x6c>
0xd04 ldub r2,@r0
0xd06 mv r1,r9
0xd08 mv r0,r8
0xd0a bl b48 <descriptor.lto_priv.0>
0xd0c mv r8,r0
0xd10 pop lr
```

gxr2_semantic_validate，bl，0x2414。
```text
0x23f0 st r6,@(72,sp)
0x23f4 add r4,r6
0x23f6 add r4,r9
0x23f8 st r4,@(64,sp)
0x23fc mv r0,r4
0x23fe addi r0,#12
0x2400 bl 104 <be32.lto_priv.0>
0x2404 ld r1,@(80,sp)
0x2408 mv r8,r9
0x240a add r8,r0
0x240c ld r0,@(52,sp)
0x2410 ldi r2,#0
0x2414 bl b48 <descriptor.lto_priv.0>
0x2418 seth r1,#0x1
0x241c add3 r1,r1,#-20668
```

gxr2_semantic_validate，bl，0x2ff8。
```text
0x2fd0 ld r6,@(68,sp)
0x2fd4 cmpu r8,r6
0x2fd6 bnc 3050 <gxr2_semantic_validate+0xcc8>
0x2fd8 add3 r4,r11,#-4
0x2fdc bnez r4,2fec <gxr2_semantic_validate+0xc64>
0x2fe0 bnez r8,3050 <gxr2_semantic_validate+0xcc8>
0x2fe4 add3 r4,r5,#-3
0x2fe8 bnez r4,3050 <gxr2_semantic_validate+0xcc8>
0x2fec ld r0,@(52,sp)
0x2ff0 st r5,@(128,sp)
0x2ff4 mv r2,r8
0x2ff6 mv r1,r10
0x2ff8 bl b48 <descriptor.lto_priv.0>
0x2ffc ld r5,@(128,sp)
0x3000 ldi r4,#2
```

gxr2_semantic_validate，bl，0x31c4。
```text
0x319c beqz r8,3050 <gxr2_semantic_validate+0xcc8>
0x31a0 ldub r4,@r0
0x31a4 bne r11,r4,3050 <gxr2_semantic_validate+0xcc8>
0x31a8 ld r5,@(56,sp)
0x31ac ldi r4,#1
0x31ae sll r4,r8
0x31b0 or r5,r4
0x31b4 st r5,@(56,sp)
0x31b8 bra 309c <gxr2_semantic_validate+0xd14>
0x31bc ld r0,@(52,sp)
0x31c0 mv r2,r8
0x31c2 mv r1,r10
0x31c4 bl b48 <descriptor.lto_priv.0>
0x31c8 ldub r2,@r0
0x31cc mv r1,r10
```

gate_validate.constprop.0，bl，0x6370。
```text
0x634a addi r10,#12
0x634c bnez r6,62bc <gate_validate.constprop.0+0x89c>
0x6350 bne r4,r11,5ef0 <gate_validate.constprop.0+0x4d0>
0x6354 ld r9,@(20,sp)
0x6358 ldi r10,#0
0x635a addi r9,#12
0x635c add r9,r8
0x6360 seth r0,#0x1
0x6364 add3 r0,r0,#-9956
0x6368 ldi r2,#0
0x636a mv r1,r10
0x636c add r0,r12
0x6370 bl b48 <descriptor.lto_priv.0>
0x6374 ldub r5,@r0
0x6378 mv r11,r0
```

verify，bl，0x6734。
```text
0x6708 beqz r6,6be0 <verify+0x6d8>
0x670c ld r6,@(100,sp)
0x6710 add3 r0,r9,#68
0x6714 ld r5,@(116,sp)
0x6718 slli r6,#0x6
0x671c ld r4,@(104,sp)
0x6720 add r5,r6
0x6724 ld r1,@(100,sp)
0x6728 st r5,@(116,sp)
0x672c ldub r2,@r7
0x672e add r4,r5
0x6730 st r4,@(112,sp)
0x6734 bl b48 <descriptor.lto_priv.0>
0x6738 st r0,@(120,sp)
0x673c ld r0,@(112,sp)
```

verify，bl，0x6950。
```text
0x6920 ldi r2,#236
0x6924 seth r10,#0x1
0x6928 add3 r10,r10,#-6828
0x692c add r1,r12
0x6930 stb r4,@(233,r1)
0x6934 stb r5,@(232,r1)
0x6938 add r0,r12
0x693c bl 13c <ig_copy>
0x6940 ld r1,@(100,sp)
0x6944 add r10,r12
0x6948 add3 r0,r10,#68
0x694c ldi r2,#0
0x6950 bl b48 <descriptor.lto_priv.0>
0x6954 st r0,@(112,sp)
0x6958 ld r0,@(116,sp)
```

ig_init，bl，0x7a00。
```text
0x79d6 add r1,r0
0x79d8 ldi r0,#-1
0x79dc bl 2320 <gxr2_crc_add>
0x79e0 mv r10,r0
0x79e4 ldi fp,#0
0x79e8 ld r1,@(84,sp)
0x79ec seth r5,#0x1
0x79f0 add3 r5,r5,#-8160
0x79f4 add r5,r12
0x79f8 st r5,@(132,sp)
0x79fc ldi r2,#0
0x79fe mv r0,r5
0x7a00 bl b48 <descriptor.lto_priv.0>
0x7a04 ld r5,@(132,sp)
0x7a08 mv r2,fp
```

ig_init，bl，0x7a3c。
```text
0x7a14 srl3 r2,r1,#16
0x7a18 mv r1,r0
0x7a1a mv r0,r10
0x7a1c bl 2320 <gxr2_crc_add>
0x7a20 addi fp,#1
0x7a24 add3 r5,fp,#-10
0x7a28 mv r10,r0
0x7a2c bnez r5,79e8 <ig_init+0x698>
0x7a30 ld r1,@(84,sp)
0x7a34 mv r0,r11
0x7a36 ldi r2,#0
0x7a38 add r0,r12
0x7a3c bl b48 <descriptor.lto_priv.0>
0x7a40 add3 r1,r0,#2
0x7a44 ldi r2,#2
```


disarm

fresh，bl，0x45e8。
```text
0x45c0 add3 r12,r12,#-17596
0x45c4 add r12,lr
0x45c6 add r8,r12
0x45c8 ldub r4,@(2465,r8)
0x45cc addi sp,#-28
0x45d0 ld lr,@(28,sp)
0x45d4 bnez r4,45fc <fresh+0x54>
0x45d8 seth r4,#0x1
0x45dc add3 r4,r4,#-6828
0x45e0 add r4,r12
0x45e2 ldi r5,#0
0x45e4 stb r5,@(2465,r4)
0x45e8 bl 968 <disarm>
0x45ec ldi r0,#0
0x45f0 addi sp,#28
```

eng_apply，bl，0x4ea0。
```text
0x4e7c ldi r5,#8
0x4e80 mul r5,r3
0x4e82 addi r5,#9
0x4e84 mul r4,r7
0x4e86 stb r5,@r9
0x4e88 add r6,r2
0x4e8a addi r4,#9
0x4e8c stb r4,@r6
0x4e90 bl 45a8 <fresh>
0x4e94 beqz r0,575c <eng_apply+0xe0c>
0x4e98 seth r10,#0x1
0x4e9c add3 r10,r10,#-8928
0x4ea0 bl 968 <disarm>
0x4ea4 add r10,r12
0x4ea8 mv r11,r8
```

eng_apply，bl，0x56d0。
```text
0x56a4 ld r5,@(28,r11)
0x56a8 stb r10,@(2468,r11)
0x56ac ld r10,@(8,r11)
0x56b0 beqz r5,56cc <eng_apply+0xd7c>
0x56b4 ldub r4,@(1361,r11)
0x56b8 ldi r2,#1
0x56bc ldub r1,@(219,r11)
0x56c0 srli r4,#0x3
0x56c4 ld r0,@(4,r11)
0x56c8 and r2,r4
0x56ca jl r5
0x56cc beqz r10,5730 <eng_apply+0xde0>
0x56d0 bl 968 <disarm>
0x56d4 add r8,r12
0x56d8 ld r4,@(156,r8)
```


end

eng_apply，bl，0x52cc。
```text
0x529e add r5,r12
0x52a0 ldi r6,#1
0x52a4 stb r6,@(2474,r5)
0x52a8 st r5,@(80,sp)
0x52ac bl 4850 <t_read>
0x52b0 cmpui r11,#1
0x52b4 mvfc r6,cbr
0x52b8 ld r5,@(80,sp)
0x52bc slli r6,#0x1
0x52c0 beq r6,r0,52d4 <eng_apply+0x984>
0x52c4 ldi r4,#257
0x52c8 sth r4,@(2470,r5)
0x52cc bl 48e8 <end>
0x52d0 bra 5108 <eng_apply+0x7b8>
0x52d4 ldi r6,#0
```

eng_apply，bl，0x5460。
```text
0x5438 ldi r6,#1
0x543a mv r5,r0
0x543c st r5,@(80,sp)
0x5440 and r6,r0
0x5444 st r6,@(76,sp)
0x5448 mv r1,r2
0x544a ldi r0,#4
0x544c bl 4764 <expect>
0x5450 ld r5,@(80,sp)
0x5454 ld r6,@(76,sp)
0x5458 bnez r0,5480 <eng_apply+0xb30>
0x545c ldi r11,#0
0x5460 bl 48e8 <end>
0x5464 beqz r0,528c <eng_apply+0x93c>
0x5468 beqz r11,528c <eng_apply+0x93c>
```


eng_apply

select_cached，bl，0x581c。
```text
0x57f4 ld r0,@(48,r9)
0x57f8 stb r11,@(1,sp)
0x57fc stb r4,@sp
0x5800 sll3 r4,r8,#6
0x5804 addi r4,#-32
0x5806 add r0,r4
0x5808 bl b94 <eng_identity>
0x580c sll3 r1,r8,#3
0x5810 add3 r1,r1,#1348
0x5814 stb r11,@(803,r9)
0x5818 add r1,r10
0x581a mv r0,sp
0x581c bl 4950 <eng_apply>
0x5820 beqz r0,5834 <select_cached+0xb0>
0x5824 ldub r4,@(2467,r9)
```

ig_event，bl，0x81d4。
```text
0x81b2 mv r0,r10
0x81b4 bl 1280 <ui_finish>
0x81b8 bra 82f8 <ig_event+0x224>
0x81bc ldi r4,#0
0x81be bra 8198 <ig_event+0xc4>
0x81c0 ldi r4,#1
0x81c2 bra 8198 <ig_event+0xc4>
0x81c4 beqz r4,8224 <ig_event+0x150>
0x81c8 mv r8,r9
0x81ca add r8,r12
0x81cc add3 r1,r8,#511
0x81d0 add3 r0,r8,#452
0x81d4 bl 4950 <eng_apply>
0x81d8 mv r11,r0
0x81dc bnez r0,81ac <ig_event+0xd8>
```


eng_current

ig_event，bl，0x8274。
```text
0x8248 add3 r4,r4,#-6828
0x824c add r4,r12
0x8250 ldub r4,@(805,r4)
0x8254 bnez r4,81b0 <ig_event+0xdc>
0x8258 mv r4,r9
0x825a add r4,r12
0x825c ldub r5,@(2080,r4)
0x8260 bnez r5,8278 <ig_event+0x1a4>
0x8264 add3 r1,sp,#63
0x8268 add3 r0,sp,#12
0x826c ldi r5,#1
0x8270 stb r5,@(2080,r4)
0x8274 bl 4654 <eng_current>
0x8278 add r9,r12
0x827a ldi r4,#1
```

ig_panel_open，bl，0x8494。
```text
0x8468 add3 r11,r11,#380
0x846c st r11,@(428,r8)
0x8470 add r4,r12
0x8474 st r4,@(432,r8)
0x8478 ldub r4,@(2078,r8)
0x847c beqz r4,8488 <ig_panel_open+0x158>
0x8480 ldi r4,#-1
0x8484 st r4,@(576,r8)
0x8488 mv r8,r9
0x848a add r8,r12
0x848c add3 r1,r8,#503
0x8490 add3 r0,r8,#452
0x8494 bl 4654 <eng_current>
0x8498 mv r11,r0
0x849c bnez r0,83c0 <ig_panel_open+0x90>
```


eng_entry.constprop.0

eng_apply，bl，0x4b04。
```text
0x4ae0 beqz r0,4aec <eng_apply+0x19c>
0x4ae4 addi r0,#-1
0x4ae6 slli r0,#0x2
0x4ae8 add r0,r4
0x4aea st r5,@r0
0x4aec addi r10,#1
0x4af0 add3 r5,r10,#-8
0x4af4 addi r11,#3
0x4af8 bnez r5,4ab4 <eng_apply+0x164>
0x4afc ldub r0,@(24,r9)
0x4b00 mv r11,r8
0x4b02 add r11,r12
0x4b04 bl 3b88 <eng_entry.constprop.0>
0x4b08 ldi r2,#552
0x4b0c mv r1,r0
```

ig_init，bl，0x7b1c。
```text
0x7af0 ldi r2,#84
0x7af2 add r1,r12
0x7af4 bl ae94 <memcpy>
0x7af8 ld r6,@(92,sp)
0x7afc add3 r1,sp,#40
0x7b00 add3 r0,r10,#156
0x7b04 st r6,@(152,r10)
0x7b08 ldi r2,#28
0x7b0c bl ae94 <memcpy>
0x7b10 ldi r4,#257
0x7b14 sth r4,@(2464,r10)
0x7b18 ldi r0,#0
0x7b1c bl 3b88 <eng_entry.constprop.0>
0x7b20 ldi r2,#552
0x7b24 mv r1,r0
```


eng_identity

eng_apply，bl，0x4a6c。
```text
0x4a48 cmpu r4,r11
0x4a4a bc 4a10 <eng_apply+0xc0>
0x4a4c ld r5,@(48,r10)
0x4a50 sll3 r4,r11,#6
0x4a54 seth r1,#0x1
0x4a58 add3 r1,r1,#-9116
0x4a5c ld r9,@(56,r10)
0x4a60 addi r4,#-32
0x4a62 add r5,r4
0x4a64 st r5,@(28,sp)
0x4a68 mv r0,r5
0x4a6a add r1,r12
0x4a6c bl b94 <eng_identity>
0x4a70 ld r5,@(28,sp)
0x4a74 ldub r4,@(1,r5)
```

select_cached，bl，0x5808。
```text
0x57e0 ldub r4,@(807,r9)
0x57e4 and3 r11,r8,#0xff
0x57e8 cmpu r4,r11
0x57ea bc 5844 <select_cached+0xc0>
0x57ec ldub r4,@(64,r9)
0x57f0 add3 r1,sp,#2
0x57f4 ld r0,@(48,r9)
0x57f8 stb r11,@(1,sp)
0x57fc stb r4,@sp
0x5800 sll3 r4,r8,#6
0x5804 addi r4,#-32
0x5806 add r0,r4
0x5808 bl b94 <eng_identity>
0x580c sll3 r1,r8,#3
0x5810 add3 r1,r1,#1348
```

verify，bl，0x6694。
```text
0x6670 addi r6,#16
0x6672 add r0,r6
0x6674 add r0,r5
0x6678 bl 104 <be32.lto_priv.0>
0x667c ld r4,@(104,sp)
0x6680 stb r11,@(13,sp)
0x6684 add3 r1,sp,#14
0x6688 stb fp,@(12,sp)
0x668c slli r11,#0x6
0x668e addi r11,#-32
0x6690 add r0,r11
0x6692 add r0,r4
0x6694 bl b94 <eng_identity>
0x6698 ldub r4,@(150,r9)
0x669c ld fp,@(2104,r10)
```


eng_visible_rows

select_cached，bl，0x57c0。
```text
0x5798 push lr
0x579a bl 579c <select_cached+0x18>
0x579c seth r12,#0x0
0x57a0 add3 r12,r12,#-22172
0x57a4 add r12,lr
0x57a6 add r10,r12
0x57a8 ldub r4,@(1484,r10)
0x57ac addi sp,#-52
0x57b0 ld lr,@(52,sp)
0x57b4 mv r8,r0
0x57b8 beqz r4,5844 <select_cached+0xc0>
0x57bc beqz r0,5844 <select_cached+0xc0>
0x57c0 bl a74 <eng_visible_rows>
0x57c4 cmpu r0,r8
0x57c8 bc 5844 <select_cached+0xc0>
```

verify，bl，0x6638。
```text
0x660c add3 r5,r4,#-24
0x6610 bnez r5,65fc <verify+0xf4>
0x6614 ldi r4,#184
0x6618 mv r5,r8
0x661a add r5,r4
0x661c ldub r5,@r5
0x6620 bnez r5,6be0 <verify+0x6d8>
0x6624 addi r4,#1
0x6628 add3 r5,r4,#-192
0x662c bnez r5,6618 <verify+0x110>
0x6630 ldub r11,@(16,r8)
0x6634 beqz r11,6be0 <verify+0x6d8>
0x6638 bl a74 <eng_visible_rows>
0x663c cmpu r0,r11
0x6640 bc 6be0 <verify+0x6d8>
```

ig_menu，bl，0x7c98。
```text
0x7c6c beqz r4,7c80 <ig_menu+0xfc>
0x7c70 ldi r1,#5
0x7c74 mv r0,r10
0x7c78 bl 11a4 <finish>
0x7c7c bra 7cac <ig_menu+0x128>
0x7c80 ld r4,@(2124,r8)
0x7c84 add3 r5,r4,#5
0x7c88 beqz r5,7c94 <ig_menu+0x110>
0x7c8c addi r4,#8
0x7c90 bnez r4,7c98 <ig_menu+0x114>
0x7c94 ldi r1,#3
0x7c96 bra 7c74 <ig_menu+0xf0>
0x7c98 bl a74 <eng_visible_rows>
0x7c9c bnez r0,7cc0 <ig_menu+0x13c>
0x7ca0 add r9,r12
```

ig_menu，bl，0x7e3c。
```text
0x7e18 add3 r5,r4,#-6
0x7e1c addi r8,#1
0x7e20 bnez r5,7de0 <ig_menu+0x25c>
0x7e24 mv fp,r9
0x7e26 add fp,r12
0x7e28 add3 fp,fp,#1356
0x7e2c mv r6,r11
0x7e2e ldi r7,#0
0x7e30 ldi r8,#1
0x7e32 add r6,r12
0x7e34 st r6,@(40,sp)
0x7e38 st r7,@(44,sp)
0x7e3c bl a74 <eng_visible_rows>
0x7e40 ld r6,@(40,sp)
0x7e44 cmpu r0,r8
```

ig_menu，bl，0x7e78。
```text
0x7e50 bnc 7ee0 <ig_menu+0x35c>
0x7e52 add r9,r12
0x7e54 ldi r4,#1
0x7e58 stb r4,@(1484,r9)
0x7e5c mv r8,r11
0x7e5e add r8,r12
0x7e60 ldub r4,@(2464,r8)
0x7e64 beqz r4,7c94 <ig_menu+0x110>
0x7e68 bl 45a8 <fresh>
0x7e6c beqz r0,7c94 <ig_menu+0x110>
0x7e70 ldub r4,@(2466,r8)
0x7e74 bnez r4,8008 <ig_menu+0x484>
0x7e78 bl a74 <eng_visible_rows>
0x7e7c and3 r0,r0,#0xff
0x7e80 stb r0,@(807,r8)
```

ig_panel_open，bl，0x8434。
```text
0x8414 ldi r1,#1
0x8418 mv r0,r10
0x841c bl 11a4 <finish>
0x8420 addi sp,#32
0x8422 pop lr
0x8424 pop r12
0x8426 pop r11
0x8428 pop r10
0x842a pop r9
0x842c pop r8
0x842e pop fp
0x8430 jmp lr
0x8434 bl a74 <eng_visible_rows>
0x8438 cmpu r0,r11
0x843c bc 83e0 <ig_panel_open+0xb0>
```


es_allocation

es_session.constprop.0，bl，0x393c。
```text
0x3914 or3 r5,r5,#0x348c
0x3918 ld r6,@(100,r4)
0x391c ld r5,@r5
0x3920 bne r6,r5,3944 <es_session.constprop.0+0xac>
0x3924 ld r10,@(104,r4)
0x3928 ld24 r6,1bf00 <n+0xcf00>
0x392c add3 r5,r10,#-7760
0x3930 cmpu r6,r5
0x3932 bc 3944 <es_session.constprop.0+0xac>
0x3934 ld r2,@(108,r4)
0x3938 mv r1,r10
0x393a mv r0,r8
0x393c bl 1d88 <es_allocation>
0x3940 bnez r0,3958 <es_session.constprop.0+0xc0>
0x3944 ldi r0,#0
```

ui_prepare.constprop.0，bl，0x6e3c。
```text
0x6e10 add3 r12,r12,#-27916
0x6e14 add r12,lr
0x6e16 slli r4,#0x6
0x6e18 ld r8,@(136,r4)
0x6e1c ld lr,@sp
0x6e20 beqz r8,6e80 <ui_prepare.constprop.0+0x84>
0x6e24 ld r9,@(140,r4)
0x6e28 not r5,r8
0x6e2c bne r9,r5,6e70 <ui_prepare.constprop.0+0x74>
0x6e30 ld r2,@(144,r4)
0x6e34 ldi r1,#1968
0x6e38 mv r0,r8
0x6e3c bl 1d88 <es_allocation>
0x6e40 beqz r0,6e70 <ui_prepare.constprop.0+0x74>
0x6e44 ldi r1,#1968
```

ui_prepare.constprop.0，bl，0x6e4c。
```text
0x6e20 beqz r8,6e80 <ui_prepare.constprop.0+0x84>
0x6e24 ld r9,@(140,r4)
0x6e28 not r5,r8
0x6e2c bne r9,r5,6e70 <ui_prepare.constprop.0+0x74>
0x6e30 ld r2,@(144,r4)
0x6e34 ldi r1,#1968
0x6e38 mv r0,r8
0x6e3c bl 1d88 <es_allocation>
0x6e40 beqz r0,6e70 <ui_prepare.constprop.0+0x74>
0x6e44 ldi r1,#1968
0x6e48 ldi r2,#0
0x6e4a mv r0,r8
0x6e4c bl 1d88 <es_allocation>
0x6e50 beqz r0,6e70 <ui_prepare.constprop.0+0x74>
0x6e54 ld r5,@(1960,r8)
```

ui_prepare.constprop.0，bl，0x6ea0。
```text
0x6e78 pop r9
0x6e7a pop r8
0x6e7c jmp lr
0x6e80 ldi r0,#1968
0x6e84 bl af04 <rv_native_alloc>
0x6e88 mv r8,r0
0x6e8c beqz r0,6e70 <ui_prepare.constprop.0+0x74>
0x6e90 bl 3898 <es_session.constprop.0>
0x6e94 beqz r0,6e70 <ui_prepare.constprop.0+0x74>
0x6e98 ldi r1,#1968
0x6e9c ldi r2,#0
0x6e9e mv r0,r8
0x6ea0 bl 1d88 <es_allocation>
0x6ea4 beqz r0,6e70 <ui_prepare.constprop.0+0x74>
0x6ea8 add3 r5,r8,#1968
```

rv_call，bl，0x9980。
```text
0x9954 ld r11,@(16,sp)
0x9958 ldi r10,#20
0x995a mul r10,r8
0x995c add r10,r11
0x9960 ld r9,@(168,r10)
0x9964 addi r4,#-4
0x9968 bnez r4,99e0 <rv_call+0x11a0>
0x996c ld r5,@(24,sp)
0x9970 ldi r2,#0
0x9974 st r4,@(28,r5)
0x9978 ld r1,@(172,r10)
0x997c ld r0,@(168,r10)
0x9980 bl 1d88 <es_allocation>
0x9984 bnez r0,9994 <rv_call+0x1154>
0x9988 ldi r10,#-6
```

rv_call，bl，0xaa20。
```text
0xa9f8 bra 8998 <rv_call+0x158>
0xa9fc bnez r7,97bc <rv_call+0xf7c>
0xaa00 ld r11,@(20,sp)
0xaa04 addi r11,#-32
0xaa08 bnez r11,97bc <rv_call+0xf7c>
0xaa0c bra 984c <rv_call+0x100c>
0xaa10 ldi r5,#20
0xaa12 mul r4,r5
0xaa14 add r0,r4
0xaa18 ld r1,@(172,r0)
0xaa1c ldi r2,#0
0xaa1e mv r0,r9
0xaa20 bl 1d88 <es_allocation>
0xaa24 beqz r0,9988 <rv_call+0x1148>
0xaa28 ld r6,@(24,sp)
```


es_range.constprop.0

ingress，bl，0x7230。
```text
0x7200 add r4,r7
0x7204 bne r2,r4,7294 <ingress+0x2e4>
0x7208 ld r4,@(348,r0)
0x720c sub r4,r7
0x7210 ld r7,@(52,r10)
0x7214 bne r7,r4,7294 <ingress+0x2e4>
0x7218 ld r11,@(32,r10)
0x721c ld r2,@(28,r10)
0x7220 mv r0,r11
0x7224 ld r1,@(24,r10)
0x7228 st r5,@(16,sp)
0x722c st r6,@(12,sp)
0x7230 bl 39e8 <es_range.constprop.0>
0x7234 ld r5,@(16,sp)
0x7238 ld r6,@(12,sp)
```

ingress，bl，0x724c。
```text
0x7220 mv r0,r11
0x7224 ld r1,@(24,r10)
0x7228 st r5,@(16,sp)
0x722c st r6,@(12,sp)
0x7230 bl 39e8 <es_range.constprop.0>
0x7234 ld r5,@(16,sp)
0x7238 ld r6,@(12,sp)
0x723c beqz r0,7294 <ingress+0x2e4>
0x7240 ld r0,@(44,r10)
0x7244 mv r2,r6
0x7246 add r2,r5
0x7248 mv r1,fp
0x724c bl 39e8 <es_range.constprop.0>
0x7250 beqz r0,7294 <ingress+0x2e4>
0x7254 ld fp,@(72,r10)
```

ingress，bl，0x7264。
```text
0x7238 ld r6,@(12,sp)
0x723c beqz r0,7294 <ingress+0x2e4>
0x7240 ld r0,@(44,r10)
0x7244 mv r2,r6
0x7246 add r2,r5
0x7248 mv r1,fp
0x724c bl 39e8 <es_range.constprop.0>
0x7250 beqz r0,7294 <ingress+0x2e4>
0x7254 ld fp,@(72,r10)
0x7258 mv r0,r11
0x725c ld r1,@(64,r10)
0x7260 mv r2,fp
0x7264 bl 39e8 <es_range.constprop.0>
0x7268 beqz r0,7294 <ingress+0x2e4>
0x726c ld r4,@(68,r10)
```

rv_call，bl，0x8bec。
```text
0x8bbc add3 r4,r0,#280
0x8bc0 ld r0,@r6
0x8bc4 bnez r0,8bd8 <rv_call+0x398>
0x8bc8 addi r6,#20
0x8bcc bne r4,r6,8bc0 <rv_call+0x380>
0x8bd0 ldi r10,#-10
0x8bd4 bra 8998 <rv_call+0x158>
0x8bd8 ld r1,@(20,sp)
0x8bdc st r4,@(48,sp)
0x8be0 st r5,@(60,sp)
0x8be4 st r6,@(52,sp)
0x8be8 mv r2,r5
0x8bec bl 39e8 <es_range.constprop.0>
0x8bf0 ld r4,@(48,sp)
0x8bf4 ld r5,@(60,sp)
```

rv_call，bl，0x96d8。
```text
0x96b6 bra 95a4 <rv_call+0xd64>
0x96b8 ldi r4,#15
0x96ba bra 95a4 <rv_call+0xd64>
0x96bc ldi r4,#28
0x96be bra 95a4 <rv_call+0xd64>
0x96c0 ldi r4,#13
0x96c2 bra 95a4 <rv_call+0xd64>
0x96c4 ld r0,@(12,fp)
0x96c8 st r5,@(60,sp)
0x96cc ld r2,@(20,sp)
0x96d0 st r7,@(48,sp)
0x96d4 mv r1,r5
0x96d8 bl 39e8 <es_range.constprop.0>
0x96dc ld r5,@(60,sp)
0x96e0 ld r7,@(48,sp)
```

rv_call，bl，0xa180。
```text
0xa150 bc 9e7c <rv_call+0x163c>
0xa154 ld r6,@(24,r9)
0xa158 cmpu r6,r3
0xa15c bnc 9e7c <rv_call+0x163c>
0xa160 ld r2,@(16,r9)
0xa164 cmpu r5,r2
0xa168 bnc 9e7c <rv_call+0x163c>
0xa16c ld r7,@(36,r9)
0xa170 ld r1,@(12,r9)
0xa174 st r7,@(16,sp)
0xa178 st r3,@(56,sp)
0xa17c mv r0,r7
0xa180 bl 39e8 <es_range.constprop.0>
0xa184 ld r3,@(56,sp)
0xa188 beqz r0,9e7c <rv_call+0x163c>
```

rv_call，bl，0xa198。
```text
0xa168 bnc 9e7c <rv_call+0x163c>
0xa16c ld r7,@(36,r9)
0xa170 ld r1,@(12,r9)
0xa174 st r7,@(16,sp)
0xa178 st r3,@(56,sp)
0xa17c mv r0,r7
0xa180 bl 39e8 <es_range.constprop.0>
0xa184 ld r3,@(56,sp)
0xa188 beqz r0,9e7c <rv_call+0x163c>
0xa18c ld r1,@(28,r9)
0xa190 sll3 r2,r3,#2
0xa194 ld r0,@(16,sp)
0xa198 bl 39e8 <es_range.constprop.0>
0xa19c ld r3,@(56,sp)
0xa1a0 beqz r0,9e7c <rv_call+0x163c>
```

rv_call，bl，0xa1b8。
```text
0xa18c ld r1,@(28,r9)
0xa190 sll3 r2,r3,#2
0xa194 ld r0,@(16,sp)
0xa198 bl 39e8 <es_range.constprop.0>
0xa19c ld r3,@(56,sp)
0xa1a0 beqz r0,9e7c <rv_call+0x163c>
0xa1a4 ld r4,@(32,r9)
0xa1a8 ldi r2,#12
0xa1ac ld r0,@(16,sp)
0xa1b0 st r4,@(48,sp)
0xa1b4 mul r2,r3
0xa1b6 mv r1,r4
0xa1b8 bl 39e8 <es_range.constprop.0>
0xa1bc ld r3,@(56,sp)
0xa1c0 ld r4,@(48,sp)
```

rv_call，bl，0xa270。
```text
0xa244 ld r0,@(28,sp)
0xa248 bra 9e40 <rv_call+0x1600>
0xa24c ld r7,@(28,r9)
0xa250 sll3 r5,r8,#2
0xa254 ld r4,@(36,r9)
0xa258 add r5,r7
0xa25a ld r5,@r5
0xa25c ldi r2,#4
0xa260 st r4,@(28,sp)
0xa264 mv r0,r4
0xa268 st r5,@(60,sp)
0xa26c mv r1,r5
0xa270 bl 39e8 <es_range.constprop.0>
0xa274 ld r5,@(60,sp)
0xa278 beqz r0,9e7c <rv_call+0x163c>
```

rv_call，bl，0xa298。
```text
0xa274 ld r5,@(60,sp)
0xa278 beqz r0,9e7c <rv_call+0x163c>
0xa27c ld r7,@r5
0xa27e ldi r5,#0
0xa280 st r5,@(60,sp)
0xa284 ld r0,@(28,sp)
0xa288 st r7,@(48,sp)
0xa28c mv r3,r5
0xa28e add r3,r7
0xa290 st r3,@(56,sp)
0xa294 mv r1,r3
0xa296 ldi r2,#1
0xa298 bl 39e8 <es_range.constprop.0>
0xa29c ld r3,@(56,sp)
0xa2a0 ld r5,@(60,sp)
```

rv_call，bl，0xa50c。
```text
0xa4e0 ld r5,@(12,r9)
0xa4e4 addi r5,#-2
0xa4e8 bnez r5,9e7c <rv_call+0x163c>
0xa4ec ld r5,@(16,r9)
0xa4f0 addi r5,#-33
0xa4f4 bnez r5,9e7c <rv_call+0x163c>
0xa4f8 ld r2,@(24,r9)
0xa4fc ldi r5,#15
0xa4fe cmpu r5,r2
0xa500 bnc 9e7c <rv_call+0x163c>
0xa504 ld r1,@(20,r9)
0xa508 ld r0,@(28,r9)
0xa50c bl 39e8 <es_range.constprop.0>
0xa510 beqz r0,9e7c <rv_call+0x163c>
0xa514 seth r5,#0x205a
```

rv_call，bl，0xa66c。
```text
0xa640 ld r11,@(24,r9)
0xa644 sll3 r6,r10,#1
0xa648 addi r6,#1
0xa64c st r11,@(16,sp)
0xa650 cmpu r11,r6
0xa654 bc 9e7c <rv_call+0x163c>
0xa658 ld r11,@(8,r9)
0xa65c add3 r3,r10,#1
0xa660 ld r0,@(16,r9)
0xa664 st r3,@(20,sp)
0xa668 mv r2,r3
0xa66a mv r1,r11
0xa66c bl 39e8 <es_range.constprop.0>
0xa670 beqz r0,9e7c <rv_call+0x163c>
0xa674 ld r4,@(20,r9)
```

rv_call，bl，0xa688。
```text
0xa65c add3 r3,r10,#1
0xa660 ld r0,@(16,r9)
0xa664 st r3,@(20,sp)
0xa668 mv r2,r3
0xa66a mv r1,r11
0xa66c bl 39e8 <es_range.constprop.0>
0xa670 beqz r0,9e7c <rv_call+0x163c>
0xa674 ld r4,@(20,r9)
0xa678 ld r0,@(28,r9)
0xa67c st r4,@(48,sp)
0xa680 ld r2,@(16,sp)
0xa684 mv r1,r4
0xa688 bl 39e8 <es_range.constprop.0>
0xa68c ld r4,@(48,sp)
0xa690 beqz r0,9e7c <rv_call+0x163c>
```


es_session.constprop.0

es_range.constprop.0，bl，0x3a06。
```text
0x39ea push r9
0x39ec push r10
0x39ee push r12
0x39f0 push lr
0x39f2 bl 39f4 <es_range.constprop.0+0xc>
0x39f4 seth r12,#0x0
0x39f8 add3 r12,r12,#-14580
0x39fc add r12,lr
0x39fe ld lr,@sp
0x3a00 mv r9,r0
0x3a02 mv r8,r1
0x3a04 mv r10,r2
0x3a06 bl 3898 <es_session.constprop.0>
0x3a08 beqz r0,3a50 <es_range.constprop.0+0x68>
0x3a0c add3 r5,r0,#160
```

same.constprop.0，bl，0x6ca0。
```text
0x6c84 push r8
0x6c86 push r9
0x6c88 push r10
0x6c8a push r12
0x6c8c push lr
0x6c8e bl 6c90 <same.constprop.0+0xc>
0x6c90 seth r12,#0x0
0x6c94 add3 r12,r12,#-27536
0x6c98 add r12,lr
0x6c9a ld lr,@sp
0x6c9c mv r10,r0
0x6c9e mv r9,r1
0x6ca0 bl 3898 <es_session.constprop.0>
0x6ca4 mv r8,r0
0x6ca8 bnez r0,6cbc <same.constprop.0+0x38>
```

ui_prepare.constprop.0，bl，0x6e90。
```text
0x6e68 ld r4,@(1964,r8)
0x6e6c beq r9,r4,6e74 <ui_prepare.constprop.0+0x78>
0x6e70 ldi r0,#0
0x6e74 pop lr
0x6e76 pop r12
0x6e78 pop r9
0x6e7a pop r8
0x6e7c jmp lr
0x6e80 ldi r0,#1968
0x6e84 bl af04 <rv_native_alloc>
0x6e88 mv r8,r0
0x6e8c beqz r0,6e70 <ui_prepare.constprop.0+0x74>
0x6e90 bl 3898 <es_session.constprop.0>
0x6e94 beqz r0,6e70 <ui_prepare.constprop.0+0x74>
0x6e98 ldi r1,#1968
```

ingress，bl，0x702c。
```text
0x7004 addi r4,#-120
0x7008 bnez r4,7294 <ingress+0x2e4>
0x700c ld r4,@(48,r2)
0x7010 beqz r4,7294 <ingress+0x2e4>
0x7014 ldi r1,#32
0x7016 mv r0,r3
0x7018 bl 128 <ig_zero>
0x701c ld24 r4,10020 <n+0x1020>
0x7020 st r4,@r10
0x7022 ldi r4,#-3
0x7024 st r4,@(4,r10)
0x7028 ld r10,@(48,r8)
0x702c bl 3898 <es_session.constprop.0>
0x7030 ld24 r4,80151c <n+0x7f251c>
0x7034 seth r5,#0x5256
```

identity.constprop.0，bl，0x8798。
```text
0x877a addi sp,#-12
0x877c ld lr,@(12,sp)
0x8780 and r4,r5
0x8782 mv r9,r0
0x8784 beqz r4,8798 <identity.constprop.0+0x40>
0x8788 ldi r0,#0
0x878c addi sp,#12
0x878e pop lr
0x8790 pop r12
0x8792 pop r9
0x8794 pop r8
0x8796 jmp lr
0x8798 bl 3898 <es_session.constprop.0>
0x879c beqz r0,8788 <identity.constprop.0+0x30>
0x87a0 mv r0,sp
```

rv_call，bl，0x886c。
```text
0x884a push r12
0x884c push lr
0x884e bl 8850 <rv_call+0x10>
0x8850 seth r12,#0xffff
0x8854 add3 r12,r12,#30896
0x8858 add r12,lr
0x885a addi sp,#-64
0x885c ld lr,@(64,sp)
0x8860 st r0,@(32,sp)
0x8864 st r3,@(24,sp)
0x8868 mv fp,r2
0x886a mv r11,r1
0x886c bl 3898 <es_session.constprop.0>
0x8870 beqz fp,a944 <rv_call+0x2104>
0x8874 ld r4,@(24,sp)
```

rv_call，bl，0x88f0。
```text
0x88c8 st r6,@(44,sp)
0x88cc bnez r6,a908 <rv_call+0x20c8>
0x88d0 bnez r4,939c <rv_call+0xb5c>
0x88d4 ld24 r4,80151c <n+0x7f251c>
0x88d8 slli r4,#0x6
0x88dc ld r6,@(212,r4)
0x88e0 ldi r5,#16
0x88e2 and r5,r6
0x88e4 bnez r5,a914 <rv_call+0x20d4>
0x88e8 ldi r5,#16
0x88ea or r5,r6
0x88ec st r5,@(212,r4)
0x88f0 bl 3898 <es_session.constprop.0>
0x88f4 add3 r5,r11,#-1
0x88f8 mv r8,r0
```

rv_call，bl，0x8bac。
```text
0x8b88 mv r7,r11
0x8b8a addi r7,#-5
0x8b8c cmpui r7,#1
0x8b90 mvfc r6,cbr
0x8b92 ldi lr,#0
0x8b94 cmpu lr,r5
0x8b96 mvfc r5,cbr
0x8b98 bne r6,r5,8bd0 <rv_call+0x390>
0x8b9c ld r3,@(32,fp)
0x8ba0 ld r5,@(36,fp)
0x8ba4 st r3,@(20,sp)
0x8ba8 st r5,@(60,sp)
0x8bac bl 3898 <es_session.constprop.0>
0x8bb0 ld r5,@(60,sp)
0x8bb4 beqz r0,8bd0 <rv_call+0x390>
```

rv_call，bl，0x8c7c。
```text
0x8c4c beqz r6,8c60 <rv_call+0x420>
0x8c50 addi r6,#-1
0x8c54 bnez r6,8bd0 <rv_call+0x390>
0x8c58 ldi r10,#1
0x8c5c bra 8998 <rv_call+0x158>
0x8c60 ld r1,@(20,sp)
0x8c64 mv r2,r5
0x8c68 ld r0,@(4,r9)
0x8c6c bl aebc <rv_native_read>
0x8c70 ld r4,@(24,sp)
0x8c74 mv r9,r0
0x8c78 st r0,@(8,r4)
0x8c7c bl 3898 <es_session.constprop.0>
0x8c80 beqz r0,8ce8 <rv_call+0x4a8>
0x8c84 ld24 r5,80151c <n+0x7f251c>
```

rv_call，bl，0x8f70。
```text
0x8f44 bc 8ad0 <rv_call+0x290>
0x8f48 bl 33dc <token.constprop.0>
0x8f4c st r0,@(32,sp)
0x8f50 beqz r0,9394 <rv_call+0xb54>
0x8f54 ld r3,@(20,sp)
0x8f58 bnez r3,8fe0 <rv_call+0x7a0>
0x8f5c ldi r1,#0
0x8f5e mv r0,r9
0x8f60 bl aeb0 <rv_native_open>
0x8f64 ld r4,@(24,sp)
0x8f68 mv r9,r0
0x8f6c st r0,@(8,r4)
0x8f70 bl 3898 <es_session.constprop.0>
0x8f74 beqz r0,8ce8 <rv_call+0x4a8>
0x8f78 ld24 r5,80151c <n+0x7f251c>
```

rv_call，bl，0x90d8。
```text
0x90ac beq r7,r2,8ecc <rv_call+0x68c>
0x90b0 ld r7,@(296,r8)
0x90b4 beqz r7,90c8 <rv_call+0x888>
0x90b8 ld r2,@(28,sp)
0x90bc ld r7,@(508,r8)
0x90c0 srli r2,#0x8
0x90c2 srli r7,#0x8
0x90c4 beq r2,r7,8ecc <rv_call+0x68c>
0x90c8 add3 r7,r11,#-9
0x90cc bnez r7,9338 <rv_call+0xaf8>
0x90d0 st r5,@(60,sp)
0x90d4 st r6,@(52,sp)
0x90d8 bl 3898 <es_session.constprop.0>
0x90dc ld r7,@(48,fp)
0x90e0 mv r9,r0
```

rv_call，bl，0x9508。
```text
0x94e0 ldub r4,@(6,r8)
0x94e4 bnez r4,94ec <rv_call+0xcac>
0x94e8 ldi r10,#-9
0x94ea bra 93e4 <rv_call+0xba4>
0x94ec bl af70 <rv_native_context>
0x94f0 bnez r0,94e8 <rv_call+0xca8>
0x94f4 ld r8,@(212,r8)
0x94f8 st r8,@(36,sp)
0x94fc ld r6,@(36,sp)
0x9500 ldi r8,#16
0x9502 and r8,r6
0x9504 bnez r8,a934 <rv_call+0x20f4>
0x9508 bl 3898 <es_session.constprop.0>
0x950c ld r4,@(52,fp)
0x9510 st r0,@(16,sp)
```

rv_call，bl，0x99e0。
```text
0x99b8 st r5,@(28,r7)
0x99bc bnez r4,9bc8 <rv_call+0x1388>
0x99c0 ld r11,@(16,sp)
0x99c4 ldi r4,#20
0x99c6 mul r4,r8
0x99c8 add r4,r11
0x99ca ldi r5,#0
0x99cc st r5,@(160,r4)
0x99d0 ld r4,@(24,sp)
0x99d4 st r5,@(16,r4)
0x99d8 ldi r10,#0
0x99dc bra 97bc <rv_call+0xf7c>
0x99e0 bl 3898 <es_session.constprop.0>
0x99e4 ld r5,@(24,sp)
0x99e8 ldi r4,#0
```

rv_call，bl，0x9c7c。
```text
0x9c54 ldi r11,#0
0x9c56 cmpu r11,r0
0x9c58 st r0,@(8,r7)
0x9c5c mvfc r0,cbr
0x9c5e neg r10,r0
0x9c60 bra 97bc <rv_call+0xf7c>
0x9c64 add3 r6,r11,#-1
0x9c68 bnez r6,9cb0 <rv_call+0x1470>
0x9c6c ld r4,@(20,sp)
0x9c70 addi r4,#-24
0x9c74 bnez r4,aa44 <rv_call+0x2204>
0x9c78 st r6,@(52,sp)
0x9c7c bl 3898 <es_session.constprop.0>
0x9c80 seth r5,#0x200c
0x9c84 or3 r5,r5,#0xdac
```

rv_call，bl，0xa138。
```text
0xa10c ldi r6,#2
0xa10e cmpu r6,r5
0xa110 bc 97bc <rv_call+0xf7c>
0xa114 ld r4,@(20,sp)
0xa118 addi r4,#-40
0xa11c bnez r4,97bc <rv_call+0xf7c>
0xa120 ld r3,@(20,r9)
0xa124 ld r6,@(40,sp)
0xa128 bne r6,r3,9e5c <rv_call+0x161c>
0xa12c beqz r7,a134 <rv_call+0x18f4>
0xa130 bne r7,r6,9e5c <rv_call+0x161c>
0xa134 st r3,@(56,sp)
0xa138 bl 3898 <es_session.constprop.0>
0xa13c ld r3,@(56,sp)
0xa140 mv r10,r0
```

rv_call，bl，0xa3dc。
```text
0xa3b0 stb r7,@r5
0xa3b4 ld r5,@(32,r6)
0xa3b8 st r5,@(8,r9)
0xa3bc ld r0,@(28,sp)
0xa3c0 bl b01c <rv_irq_restore>
0xa3c4 bnez r11,a3e8 <rv_call+0x1ba8>
0xa3c8 ld r1,@(456,r10)
0xa3cc ldi r5,#1
0xa3d0 st r5,@(480,r10)
0xa3d4 ldi r2,#0
0xa3d6 ldi r0,#2
0xa3d8 bl af4c <rv_native_draw>
0xa3dc bl 3898 <es_session.constprop.0>
0xa3e0 beqz r0,a3e8 <rv_call+0x1ba8>
0xa3e4 st r11,@(480,r10)
```


es_ui_abort.constprop.0

rv_call，bl，0xa0fc。
```text
0xa0cc add3 r5,r11,#-4
0xa0d0 bnez r5,a108 <rv_call+0x18c8>
0xa0d4 ld r11,@(20,sp)
0xa0d8 addi r11,#-40
0xa0dc bnez r11,a0e8 <rv_call+0x18a8>
0xa0e0 ld r9,@(8,r9)
0xa0e4 st r9,@(28,sp)
0xa0e8 ld24 r4,80151c <n+0x7f251c>
0xa0ec ld r5,@(28,sp)
0xa0f0 slli r4,#0x6
0xa0f4 ld r4,@(32,r4)
0xa0f8 bne r4,r5,97a4 <rv_call+0xf64>
0xa0fc bl 58c4 <es_ui_abort.constprop.0>
0xa100 mv r10,r0
0xa104 bra 97bc <rv_call+0xf7c>
```


expect

write_word，bl，0x47d0。
```text
0x47ae push lr
0x47b0 bl 47b4 <write_word+0x10>
0x47b4 seth r12,#0x0
0x47b8 add3 r12,r12,#-18100
0x47bc add r12,lr
0x47be add r4,r12
0x47c0 ldi r5,#1
0x47c2 ld lr,@sp
0x47c4 mv r2,r0
0x47c8 stb r5,@(2468,r4)
0x47cc mv r1,r0
0x47ce ldi r0,#3
0x47d0 bl 4764 <expect>
0x47d4 beqz r0,47f4 <write_word+0x50>
0x47d8 seth r4,#0x1
```

t_store，bl，0x483c。
```text
0x4814 beqz r0,4848 <t_store+0x4c>
0x4818 seth r4,#0x1
0x481c add3 r4,r4,#-6828
0x4820 add r4,r12
0x4824 ld r4,@(44,r4)
0x4828 mv r2,r8
0x482a ldi r0,#2
0x482c ldub r1,@(30,r4)
0x4830 ldub r4,@(31,r4)
0x4834 slli r1,#0x8
0x4836 add r1,r4
0x4838 and3 r1,r1,#0xffff
0x483c bl 4764 <expect>
0x4840 ldi r4,#0
0x4844 cmpu r4,r0
```

t_read，bl，0x4892。
```text
0x486c add r12,lr
0x486e add r8,r12
0x4870 ld r4,@(44,r8)
0x4874 addi sp,#-4
0x4878 ld lr,@(4,sp)
0x487c ldi r0,#4
0x4880 ldub r2,@(28,r4)
0x4884 ldub r4,@(29,r4)
0x4888 slli r2,#0x8
0x488a add r2,r4
0x488c and3 r2,r2,#0xffff
0x4890 mv r1,r2
0x4892 bl 4764 <expect>
0x4894 bnez r0,48bc <t_read+0x6c>
0x4898 ldi r5,#0
```

eng_apply，bl，0x5324。
```text
0x52fa add r11,r12
0x52fc ldi r5,#0
0x5300 stb r5,@(2473,r11)
0x5304 beqz r0,577c <eng_apply+0xe2c>
0x5308 ld r0,@(44,r11)
0x530c addi r0,#24
0x5310 bl 944 <b32>
0x5314 srl3 r2,r0,#16
0x5318 mv r5,r0
0x531c st r5,@(80,sp)
0x5320 mv r1,r2
0x5322 ldi r0,#4
0x5324 bl 4764 <expect>
0x5328 ld r5,@(80,sp)
0x532c beqz r0,577c <eng_apply+0xe2c>
```

eng_apply，bl，0x544c。
```text
0x5428 cmpu r5,r0
0x542a mvfc r11,cbr
0x542c bra 5460 <eng_apply+0xb10>
0x5430 bl 944 <b32>
0x5434 srl3 r2,r0,#16
0x5438 ldi r6,#1
0x543a mv r5,r0
0x543c st r5,@(80,sp)
0x5440 and r6,r0
0x5444 st r6,@(76,sp)
0x5448 mv r1,r2
0x544a ldi r0,#4
0x544c bl 4764 <expect>
0x5450 ld r5,@(80,sp)
0x5454 ld r6,@(76,sp)
```


failure

eng_apply，bl，0x528c。
```text
0x5264 bra 5278 <eng_apply+0x928>
0x5268 mv r6,r8
0x526a add r6,r12
0x526c ldi r7,#1
0x5270 stb r7,@(2469,r6)
0x5274 beqz r5,5258 <eng_apply+0x908>
0x5278 add3 r10,sp,#12
0x527c mv r2,r10
0x527e ldi r1,#0
0x5280 ldi r0,#1
0x5284 bl 46cc <rpc.lto_priv.0>
0x5288 bnez r0,529c <eng_apply+0x94c>
0x528c bl a30 <failure>
0x5290 mv r8,r0
0x5294 beqz r0,546c <eng_apply+0xb1c>
```

eng_apply，bl，0x5474。
```text
0x5448 mv r1,r2
0x544a ldi r0,#4
0x544c bl 4764 <expect>
0x5450 ld r5,@(80,sp)
0x5454 ld r6,@(76,sp)
0x5458 bnez r0,5480 <eng_apply+0xb30>
0x545c ldi r11,#0
0x5460 bl 48e8 <end>
0x5464 beqz r0,528c <eng_apply+0x93c>
0x5468 beqz r11,528c <eng_apply+0x93c>
0x546c bl 45a8 <fresh>
0x5470 bnez r0,5560 <eng_apply+0xc10>
0x5474 bl a30 <failure>
0x5478 mv r8,r0
0x547c bra 510c <eng_apply+0x7bc>
```

eng_apply，bl，0x563c。
```text
0x5614 add r4,r12
0x5618 ld r2,@(8,r4)
0x561c st r10,@(8,sp)
0x5620 st fp,@(4,sp)
0x5624 ldi r3,#0
0x5626 ldi r1,#3
0x5628 st fp,@sp
0x562a ldi r0,#6
0x562c bl 43c0 <svc.constprop.0>
0x5630 bl 9bc <mapped>
0x5634 mv r10,r0
0x5638 beqz r0,564c <eng_apply+0xcfc>
0x563c bl a30 <failure>
0x5640 mv r8,r0
0x5644 beqz r8,5730 <eng_apply+0xde0>
```


finish

ig_init，bl，0x73b4。
```text
0x7384 seth r11,#0x1
0x7388 add3 r11,r11,#-4352
0x738c seth r10,#0x1
0x7390 add3 r10,r10,#-4352
0x7394 add r11,r12
0x7398 ldub r4,@(2072,r11)
0x739c beqz r4,73cc <ig_init+0x7c>
0x73a0 ld r5,@(88,sp)
0x73a4 ld24 r4,e0000 <n+0xd1000>
0x73a8 ldi r1,#0
0x73ac st r4,@(24,r5)
0x73b0 mv r0,r5
0x73b4 bl 11a4 <finish>
0x73b8 add3 sp,sp,#136
0x73bc pop lr
```

ig_menu，bl，0x7c78。
```text
0x7c50 ldi r4,#1
0x7c54 stb r4,@(2074,r8)
0x7c58 ldi r2,#8
0x7c5a ldi r4,#2
0x7c5c st r4,@(2124,r8)
0x7c60 ldi r1,#2
0x7c62 ldi r0,#1
0x7c64 bl 4e0 <ig_bx_receipt>
0x7c68 ldub r4,@(2076,r8)
0x7c6c beqz r4,7c80 <ig_menu+0xfc>
0x7c70 ldi r1,#5
0x7c74 mv r0,r10
0x7c78 bl 11a4 <finish>
0x7c7c bra 7cac <ig_menu+0x128>
0x7c80 ld r4,@(2124,r8)
```

ig_apply，bl，0x80c4。
```text
0x809c and3 r4,r4,#0xff
0x80a0 beqz r4,80cc <ig_apply+0xb4>
0x80a4 ldub r6,@(807,r5)
0x80a8 cmpu r6,r4
0x80aa bc 80cc <ig_apply+0xb4>
0x80ac stb r4,@(803,r5)
0x80b0 bl 1e7c <list_bind>
0x80b4 ldi r4,#0
0x80b8 cmpu r4,r0
0x80ba mvfc r1,cbr
0x80bc slli r1,#0x2
0x80c0 mv r0,r8
0x80c4 bl 11a4 <finish>
0x80c8 bra 8074 <ig_apply+0x5c>
0x80cc ldi r1,#1
```

ig_event，bl，0x82f4。
```text
0x82cc add3 r4,r4,#-19772
0x82d0 add r4,r12
0x82d2 ld r4,@r4
0x82d4 st r0,@sp
0x82d8 st r4,@(4,sp)
0x82dc ld r2,@(44,r8)
0x82e0 ld r1,@(56,r8)
0x82e4 ld r0,@(60,r8)
0x82e8 bl 7b4 <ig_bx_apply>
0x82ec beqz r11,830c <ig_event+0x238>
0x82f0 mv r1,r11
0x82f2 mv r0,r10
0x82f4 bl 11a4 <finish>
0x82f8 addi sp,#76
0x82fa pop lr
```

ig_panel_open，bl，0x841c。
```text
0x83f4 st r4,@(8,sp)
0x83f8 seth r4,#0x1
0x83fc add3 r4,r4,#-19772
0x8400 add r4,r12
0x8402 ld r4,@r4
0x8404 st r4,@(4,sp)
0x8408 ldi r4,#1
0x840a st r4,@sp
0x840c ld r1,@(56,fp)
0x8410 bl 7b4 <ig_bx_apply>
0x8414 ldi r1,#1
0x8418 mv r0,r10
0x841c bl 11a4 <finish>
0x8420 addi sp,#32
0x8422 pop lr
```

ig_stop，bl，0x8744。
```text
0x8718 stb r5,@(805,r4)
0x871c bl 10f8 <workspace_close>
0x8720 bnez r0,8750 <ig_stop+0x88>
0x8724 ldi r1,#0
0x8728 seth r4,#0x1
0x872c add3 r4,r4,#-4352
0x8730 add r4,r12
0x8732 ldi r5,#1
0x8734 stb r5,@(2075,r4)
0x8738 bra 8740 <ig_stop+0x78>
0x873c ldi r1,#2
0x8740 mv r0,r8
0x8744 bl 11a4 <finish>
0x8748 pop lr
0x874a pop r12
```


fresh

eng_current，bl，0x46a0。
```text
0x467e ld lr,@sp
0x4680 mv r9,r1
0x4684 bnez r4,46c8 <eng_current+0x74>
0x4688 ldub r4,@(2467,r8)
0x468c bnez r4,46a0 <eng_current+0x4c>
0x4690 ldi r0,#3
0x4694 pop lr
0x4696 pop r12
0x4698 pop r10
0x469a pop r9
0x469c pop r8
0x469e jmp lr
0x46a0 bl 45a8 <fresh>
0x46a4 beqz r0,4690 <eng_current+0x3c>
0x46a8 add3 r1,r8,#184
```

rpc.lto_priv.0，bl，0x46ee。
```text
0x46d0 push r10
0x46d2 push r12
0x46d4 push lr
0x46d6 bl 46d8 <rpc.lto_priv.0+0xc>
0x46d8 seth r12,#0x0
0x46dc add3 r12,r12,#-17880
0x46e0 add r12,lr
0x46e2 addi sp,#-12
0x46e4 ld lr,@(12,sp)
0x46e8 mv r8,r0
0x46ea mv r10,r1
0x46ec mv r9,r2
0x46ee bl 45a8 <fresh>
0x46f0 bnez r0,4708 <rpc.lto_priv.0+0x3c>
0x46f4 ldi r0,#0
```

rpc.lto_priv.0，bl，0x4734。
```text
0x470c add3 r4,r4,#-8872
0x4710 add r4,r12
0x4714 st r4,@(8,sp)
0x4718 ldi r4,#0
0x471c st r4,@(4,sp)
0x4720 st r4,@sp
0x4722 ldi r3,#0
0x4724 mv r2,r10
0x4726 mv r1,r8
0x4728 ldi r0,#4
0x472c bl 43c0 <svc.constprop.0>
0x4730 bnez r0,46f4 <rpc.lto_priv.0+0x28>
0x4734 bl 45a8 <fresh>
0x4738 beqz r0,46f4 <rpc.lto_priv.0+0x28>
0x473c seth r4,#0x1
```

eng_apply，bl，0x4e90。
```text
0x4e70 add r5,r10
0x4e72 ldi r10,#8
0x4e74 cmp r10,r5
0x4e78 bnc 51c4 <eng_apply+0x874>
0x4e7c ldi r5,#8
0x4e80 mul r5,r3
0x4e82 addi r5,#9
0x4e84 mul r4,r7
0x4e86 stb r5,@r9
0x4e88 add r6,r2
0x4e8a addi r4,#9
0x4e8c stb r4,@r6
0x4e90 bl 45a8 <fresh>
0x4e94 beqz r0,575c <eng_apply+0xe0c>
0x4e98 seth r10,#0x1
```

eng_apply，bl，0x4f2c。
```text
0x4efc bne r5,fp,5754 <eng_apply+0xe04>
0x4f00 ld r5,@(4,r10)
0x4f04 st r5,@(24,sp)
0x4f08 bnez r5,5754 <eng_apply+0xe04>
0x4f0c beqz r4,5754 <eng_apply+0xe04>
0x4f10 ld r4,@(16,r10)
0x4f14 ldi r5,#2229
0x4f18 cmpu r5,r4
0x4f1c bnc 5754 <eng_apply+0xe04>
0x4f20 ld r5,@(20,r10)
0x4f24 ld r4,@(176,r11)
0x4f28 bne r5,r4,5754 <eng_apply+0xe04>
0x4f2c bl 45a8 <fresh>
0x4f30 beqz r0,5754 <eng_apply+0xe04>
0x4f34 ld r5,@(36,sp)
```

eng_apply，bl，0x546c。
```text
0x5440 and r6,r0
0x5444 st r6,@(76,sp)
0x5448 mv r1,r2
0x544a ldi r0,#4
0x544c bl 4764 <expect>
0x5450 ld r5,@(80,sp)
0x5454 ld r6,@(76,sp)
0x5458 bnez r0,5480 <eng_apply+0xb30>
0x545c ldi r11,#0
0x5460 bl 48e8 <end>
0x5464 beqz r0,528c <eng_apply+0x93c>
0x5468 beqz r11,528c <eng_apply+0x93c>
0x546c bl 45a8 <fresh>
0x5470 bnez r0,5560 <eng_apply+0xc10>
0x5474 bl a30 <failure>
```

eng_apply，bl，0x55c4。
```text
0x55a4 mv r5,r10
0x55a6 add r5,r12
0x55a8 st r5,@(8,sp)
0x55ac ldi r4,#80
0x55ae st r4,@sp
0x55b0 add r3,r12
0x55b2 ldi r2,#0
0x55b4 ldi r1,#2
0x55b6 ldi r0,#6
0x55b8 bl 43c0 <svc.constprop.0>
0x55bc bl 9bc <mapped>
0x55c0 bnez r0,5474 <eng_apply+0xb24>
0x55c4 bl 45a8 <fresh>
0x55c8 beqz r0,5474 <eng_apply+0xb24>
0x55cc mv r11,r8
```

eng_apply，bl，0x5604。
```text
0x55dc st r10,@(8,sp)
0x55e0 ldi r4,#0
0x55e4 st r4,@(4,sp)
0x55e8 st r4,@sp
0x55ea ldi r3,#0
0x55ec ldi r2,#0
0x55ee ldi r1,#1
0x55f0 ldi r0,#5
0x55f4 bl 43c0 <svc.constprop.0>
0x55f8 bl 9bc <mapped>
0x55fc mv fp,r0
0x5600 bnez r0,5474 <eng_apply+0xb24>
0x5604 bl 45a8 <fresh>
0x5608 beqz r0,5474 <eng_apply+0xb24>
0x560c seth r4,#0x1
```

eng_apply，bl，0x564c。
```text
0x5624 ldi r3,#0
0x5626 ldi r1,#3
0x5628 st fp,@sp
0x562a ldi r0,#6
0x562c bl 43c0 <svc.constprop.0>
0x5630 bl 9bc <mapped>
0x5634 mv r10,r0
0x5638 beqz r0,564c <eng_apply+0xcfc>
0x563c bl a30 <failure>
0x5640 mv r8,r0
0x5644 beqz r8,5730 <eng_apply+0xde0>
0x5648 bra 4a14 <eng_apply+0xc4>
0x564c bl 45a8 <fresh>
0x5650 beqz r0,563c <eng_apply+0xcec>
0x5654 add3 r1,r11,#1912
```

ig_menu，bl，0x7e68。
```text
0x7e40 ld r6,@(40,sp)
0x7e44 cmpu r0,r8
0x7e48 ld r7,@(44,sp)
0x7e4c ldub r4,@(2464,r6)
0x7e50 bnc 7ee0 <ig_menu+0x35c>
0x7e52 add r9,r12
0x7e54 ldi r4,#1
0x7e58 stb r4,@(1484,r9)
0x7e5c mv r8,r11
0x7e5e add r8,r12
0x7e60 ldub r4,@(2464,r8)
0x7e64 beqz r4,7c94 <ig_menu+0x110>
0x7e68 bl 45a8 <fresh>
0x7e6c beqz r0,7c94 <ig_menu+0x110>
0x7e70 ldub r4,@(2466,r8)
```

ig_menu，bl，0x7eec。
```text
0x7ec0 cmpu r4,r0
0x7ec2 mvfc r1,cbr
0x7ec4 slli r1,#0x2
0x7ec8 bra 7c74 <ig_menu+0xf0>
0x7ecc addi fp,#1
0x7ed0 add3 r5,fp,#-8
0x7ed4 bnez r5,7dec <ig_menu+0x268>
0x7ed8 ldi r1,#4
0x7edc bra 7c74 <ig_menu+0xf0>
0x7ee0 beqz r4,7ed8 <ig_menu+0x354>
0x7ee4 st r6,@(40,sp)
0x7ee8 st r7,@(44,sp)
0x7eec bl 45a8 <fresh>
0x7ef0 ld r6,@(40,sp)
0x7ef4 ld r7,@(44,sp)
```


gate_validate.constprop.0

verify，bl，0x6ba8。
```text
0x6b8a pop r10
0x6b8c pop r9
0x6b8e pop r8
0x6b90 pop fp
0x6b92 jmp lr
0x6b94 addi r4,#-1
0x6b98 bnez r4,6be0 <verify+0x6d8>
0x6b9c add3 fp,sp,#12
0x6ba0 st r4,@sp
0x6ba2 mv r3,fp
0x6ba4 mv r1,r9
0x6ba6 mv r0,r8
0x6ba8 bl 5a20 <gate_validate.constprop.0>
0x6bac bnez r0,6be0 <verify+0x6d8>
0x6bb0 seth r11,#0x1
```

ig_init，bl，0x7518。
```text
0x74f0 stb r4,@(2083,r10)
0x74f4 ldi r1,#1
0x74f8 ld r0,@(88,sp)
0x74fc bra 73b4 <ig_init+0x64>
0x7500 not r6,r4
0x7502 cmpu r6,r1
0x7504 bc 74dc <ig_init+0x18c>
0x7508 add3 r3,r9,#72
0x750c st r5,@(132,sp)
0x7510 st r4,@sp
0x7512 mv r2,fp
0x7514 mv r0,r8
0x7518 bl 5a20 <gate_validate.constprop.0>
0x751c bnez r0,74dc <ig_init+0x18c>
0x7520 ldi r1,#0
```


grain_snapshot

地址引用：{"pc": "0x7558", "kind": "encoded GOTOFF function address", "target": "grain_snapshot", "owner": "ig_init"}

gxr2_crc32

gxr2_semantic_validate，bl，0x269c。
```text
0x2670 bl 104 <be32.lto_priv.0>
0x2674 beqz r0,2714 <gxr2_semantic_validate+0x38c>
0x2678 add3 r0,r9,#20
0x267c bl 104 <be32.lto_priv.0>
0x2680 add3 r0,r0,#-1024
0x2684 bnez r0,2714 <gxr2_semantic_validate+0x38c>
0x2688 add3 r0,r9,#24
0x268c bl 104 <be32.lto_priv.0>
0x2690 add3 r11,r9,#32
0x2694 ldi r1,#1024
0x2698 mv fp,r0
0x269a mv r0,r11
0x269c bl 2360 <gxr2_crc32>
0x26a0 bne fp,r0,2714 <gxr2_semantic_validate+0x38c>
0x26a4 add3 r0,r9,#28
```

gxr2_semantic_validate，bl，0x26b4。
```text
0x268c bl 104 <be32.lto_priv.0>
0x2690 add3 r11,r9,#32
0x2694 ldi r1,#1024
0x2698 mv fp,r0
0x269a mv r0,r11
0x269c bl 2360 <gxr2_crc32>
0x26a0 bne fp,r0,2714 <gxr2_semantic_validate+0x38c>
0x26a4 add3 r0,r9,#28
0x26a8 bl 104 <be32.lto_priv.0>
0x26ac mv fp,r0
0x26b0 ldi r1,#28
0x26b2 mv r0,r9
0x26b4 bl 2360 <gxr2_crc32>
0x26b8 bne fp,r0,2714 <gxr2_semantic_validate+0x38c>
0x26bc mv fp,r11
```

gxr2_semantic_validate，bl，0x26ec。
```text
0x26c4 bne r11,r5,2714 <gxr2_semantic_validate+0x38c>
0x26c8 ldub r6,@(1,fp)
0x26cc ldi r4,#1
0x26ce cmpu r4,r6
0x26d0 bc 2714 <gxr2_semantic_validate+0x38c>
0x26d4 add3 r0,fp,#60
0x26d8 st r6,@(124,sp)
0x26dc bl 104 <be32.lto_priv.0>
0x26e0 mv r5,r0
0x26e4 st r5,@(128,sp)
0x26e8 ldi r1,#60
0x26ea mv r0,fp
0x26ec bl 2360 <gxr2_crc32>
0x26f0 ld r5,@(128,sp)
0x26f4 ld r6,@(124,sp)
```

gxr2_semantic_validate，bl，0x2a3c。
```text
0x2a10 st r5,@(56,sp)
0x2a14 bl 104 <be32.lto_priv.0>
0x2a18 ld r10,@(68,sp)
0x2a1c add r10,r0
0x2a20 add3 r0,r8,#8
0x2a24 bl 104 <be32.lto_priv.0>
0x2a28 ld r4,@(56,sp)
0x2a2c mv fp,r0
0x2a30 ld r11,@(76,sp)
0x2a34 mv r0,r10
0x2a36 mul r11,r4
0x2a38 mv r1,r11
0x2a3c bl 2360 <gxr2_crc32>
0x2a40 bne fp,r0,28b4 <gxr2_semantic_validate+0x52c>
0x2a44 add3 r1,r11,#3
```

gxr2_semantic_validate，bl，0x2b4c。
```text
0x2b24 add3 r0,r11,#10
0x2b28 ldi r1,#2
0x2b2c bl bec <zero.lto_priv.0>
0x2b30 beqz r0,28b4 <gxr2_semantic_validate+0x52c>
0x2b34 add3 r0,r11,#12
0x2b38 bl 104 <be32.lto_priv.0>
0x2b3c ld r6,@(68,sp)
0x2b40 addi r11,#16
0x2b42 ldi r1,#20
0x2b44 mv r10,r0
0x2b46 mul r1,r6
0x2b48 mv r0,r11
0x2b4c bl 2360 <gxr2_crc32>
0x2b50 bne r10,r0,28b4 <gxr2_semantic_validate+0x52c>
0x2b54 ldi r4,#0
```

gxr2_semantic_validate，bl，0x2d88。
```text
0x2d5c st r4,@(132,sp)
0x2d60 ldi r2,#32
0x2d62 stb r6,@sp
0x2d64 bl 13c <ig_copy>
0x2d68 ldub r6,@(3,r10)
0x2d6c add3 r1,r10,#36
0x2d70 add3 r0,sp,#34
0x2d74 stb r6,@(33,sp)
0x2d78 ldi r2,#15
0x2d7c bl 13c <ig_copy>
0x2d80 ldi r1,#49
0x2d84 mv r0,sp
0x2d88 bl 2360 <gxr2_crc32>
0x2d8c ld r4,@(132,sp)
0x2d90 bne r4,r0,28b4 <gxr2_semantic_validate+0x52c>
```

gxr2_expand.constprop.0，bl，0x3b48。
```text
0x3b26 add r9,r12
0x3b28 seth r5,#0x1
0x3b2c add3 r5,r5,#-20028
0x3b30 seth r4,#0x1
0x3b34 add3 r4,r4,#-20010
0x3b38 add r5,r12
0x3b3a add r5,r8
0x3b3c add r4,r12
0x3b3e add r4,r8
0x3b40 lduh r0,@r5
0x3b42 lduh r1,@r4
0x3b44 add r0,r9
0x3b48 bl 2360 <gxr2_crc32>
0x3b4c seth r4,#0x1
0x3b50 add3 r4,r4,#-20046
```

gate_validate.constprop.0，bl，0x5bc8。
```text
0x5b9c mv fp,r0
0x5b9e ldi r2,#20
0x5ba0 mv r0,r8
0x5ba4 bl 3594 <gxr2_crc_zeroed.constprop.0>
0x5ba8 bne fp,r0,64e0 <gate_validate.constprop.0+0xac0>
0x5bac ld r3,@(116,sp)
0x5bb0 bnez r3,5bd0 <gate_validate.constprop.0+0x1b0>
0x5bb4 add3 r0,r8,#24
0x5bb8 bl 104 <be32.lto_priv.0>
0x5bbc mv fp,r0
0x5bc0 add3 r0,r8,#256
0x5bc4 mv r1,r11
0x5bc8 bl 2360 <gxr2_crc32>
0x5bcc bne fp,r0,64e0 <gate_validate.constprop.0+0xac0>
0x5bd0 seth r1,#0x1
```

verify，bl，0x6b70。
```text
0x6b40 mv r1,r9
0x6b44 bl 158 <ig_equal>
0x6b48 beqz r0,6be0 <verify+0x6d8>
0x6b4c ld r0,@(124,sp)
0x6b50 bl 104 <be32.lto_priv.0>
0x6b54 ld r4,@(172,sp)
0x6b58 ldi r1,#192
0x6b5c ld r5,@(172,sp)
0x6b60 st r0,@r4
0x6b64 ldi r4,#192
0x6b68 st r4,@(4,r5)
0x6b6c mv r0,r8
0x6b70 bl 2360 <gxr2_crc32>
0x6b74 ld r4,@(172,sp)
0x6b78 st r0,@(8,r4)
```

ig_init，bl，0x7850。
```text
0x7824 add3 r10,r10,#-8160
0x7828 add r10,r12
0x782c ldi r2,#4
0x782e mv r1,r9
0x7830 mv r0,r10
0x7834 bl 3a64 <gxr2_expand.constprop.0>
0x7838 st r0,@(92,sp)
0x783c bnez r0,74f4 <ig_init+0x1a4>
0x7840 seth r0,#0x1
0x7844 add3 r0,r0,#-8712
0x7848 ldi r1,#552
0x784c add r0,r12
0x7850 bl 2360 <gxr2_crc32>
0x7854 seth r5,#0x1
0x7858 add3 r5,r5,#-19864
```

ig_bootstrap，bl，0xae20。
```text
0xadf8 add3 r1,r1,#-20408
0xadfc ldi r2,#8
0xadfe add r1,r12
0xae00 mv r0,r11
0xae04 bl 158 <ig_equal>
0xae08 beqz r0,aa8c <ig_bootstrap+0x3c>
0xae0c add3 r0,sp,#16
0xae10 bl 104 <be32.lto_priv.0>
0xae14 mv r8,r0
0xae18 bnez r0,aa8c <ig_bootstrap+0x3c>
0xae1c ldi r1,#12
0xae1e mv r0,r11
0xae20 bl 2360 <gxr2_crc32>
0xae24 mv r9,r0
0xae28 add3 r0,sp,#20
```


gxr2_crc_zeroed.constprop.0

io_close，bl，0x375e。
```text
0x3734 add3 r0,r0,#-192
0x3738 bnez r0,387c <io_close+0x270>
0x373c add3 r0,r10,#584
0x3740 bl 104 <be32.lto_priv.0>
0x3744 mv r9,r0
0x3748 bnez r0,387c <io_close+0x270>
0x374c add3 r0,r10,#412
0x3750 bl 104 <be32.lto_priv.0>
0x3754 ldi r1,#240
0x3758 mv fp,r0
0x375a ldi r2,#16
0x375c mv r0,r11
0x375e bl 3594 <gxr2_crc_zeroed.constprop.0>
0x3760 bne fp,r0,387c <io_close+0x270>
0x3764 ldi r2,#160
```

gate_validate.constprop.0，bl，0x5ba4。
```text
0x5b78 bl bec <zero.lto_priv.0>
0x5b7c beqz r0,64d8 <gate_validate.constprop.0+0xab8>
0x5b80 add3 r0,r8,#228
0x5b84 ldi r1,#28
0x5b88 bl bec <zero.lto_priv.0>
0x5b8c beqz r0,64d8 <gate_validate.constprop.0+0xab8>
0x5b90 add3 r0,r8,#20
0x5b94 bl 104 <be32.lto_priv.0>
0x5b98 ldi r1,#256
0x5b9c mv fp,r0
0x5b9e ldi r2,#20
0x5ba0 mv r0,r8
0x5ba4 bl 3594 <gxr2_crc_zeroed.constprop.0>
0x5ba8 bne fp,r0,64e0 <gate_validate.constprop.0+0xac0>
0x5bac ld r3,@(116,sp)
```

verify，bl，0x65f0。
```text
0x65c4 bne fp,r4,6be0 <verify+0x6d8>
0x65c8 ldub r4,@(1,r11)
0x65cc addi fp,#1
0x65d0 bne r4,fp,6be0 <verify+0x6d8>
0x65d4 ldub r4,@(2,r11)
0x65d8 bnez r4,6be0 <verify+0x6d8>
0x65dc add3 r0,r8,#12
0x65e0 bl 104 <be32.lto_priv.0>
0x65e4 ldi r1,#192
0x65e8 mv r9,r0
0x65ea ldi r2,#12
0x65ec mv r0,r8
0x65f0 bl 3594 <gxr2_crc_zeroed.constprop.0>
0x65f4 bne r9,r0,6be0 <verify+0x6d8>
0x65f8 ldi r4,#18
```


gxr2_expand.constprop.0

eng_entry.constprop.0，bl，0x3bdc。
```text
0x3bb6 pop r12
0x3bb8 jmp lr
0x3bbc ld r5,@(52,r4)
0x3bc0 ldi r6,#20
0x3bc4 ldub r1,@(64,r4)
0x3bc8 mul r0,r6
0x3bca add r5,r0
0x3bcc ldub r2,@(16,r5)
0x3bd0 seth r0,#0x1
0x3bd4 add3 r0,r0,#-6828
0x3bd8 add r0,r12
0x3bda addi r0,#68
0x3bdc bl 3a64 <gxr2_expand.constprop.0>
0x3be0 bnez r0,3bb0 <eng_entry.constprop.0+0x28>
0x3be4 seth r0,#0x1
```

ig_init，bl，0x7834。
```text
0x780c stb r7,@(80,r0)
0x7810 add r2,r12
0x7812 add r1,r12
0x7814 bl 2388 <gxr2_semantic_validate>
0x7818 mv r9,r0
0x781c bnez r0,74f4 <ig_init+0x1a4>
0x7820 seth r10,#0x1
0x7824 add3 r10,r10,#-8160
0x7828 add r10,r12
0x782c ldi r2,#4
0x782e mv r1,r9
0x7830 mv r0,r10
0x7834 bl 3a64 <gxr2_expand.constprop.0>
0x7838 st r0,@(92,sp)
0x783c bnez r0,74f4 <ig_init+0x1a4>
```


gxr2_parameter

verify，bl，0x68f0。
```text
0x68c8 ld r2,@(108,sp)
0x68cc seth r0,#0x1
0x68d0 add3 r0,r0,#-6828
0x68d4 ld r1,@(100,sp)
0x68d8 st r4,@(8,sp)
0x68dc add3 r4,r10,#24
0x68e0 st r4,@(4,sp)
0x68e4 addi r11,#1
0x68e6 add r0,r12
0x68e8 st r10,@sp
0x68ea mv r3,r11
0x68ec addi r0,#68
0x68f0 bl d20 <gxr2_parameter>
0x68f4 mv r9,r0
0x68f8 addi r10,#4
```

ig_panel_open，bl，0x8504。
```text
0x84dc add3 r0,r0,#-6828
0x84e0 ldub r1,@(452,r8)
0x84e4 add3 r4,sp,#20
0x84e8 st r6,@(8,sp)
0x84ec st r5,@(4,sp)
0x84f0 st r5,@(24,sp)
0x84f4 st r6,@(28,sp)
0x84f8 addi r11,#1
0x84fa add r0,r12
0x84fc st r4,@sp
0x84fe mv r3,r11
0x8500 addi r0,#68
0x8504 bl d20 <gxr2_parameter>
0x8508 ld r5,@(24,sp)
0x850c ld r6,@(28,sp)
```


gxr2_raw_row

gxr2_semantic_validate，bl，0x28ac。
```text
0x2880 ldub r4,@(225,r9)
0x2884 addi r4,#-1
0x2888 bnez r4,2714 <gxr2_semantic_validate+0x38c>
0x288c ldi r2,#152
0x2890 mv r1,r8
0x2892 ldi r0,#-1
0x2894 bl 2320 <gxr2_crc_add>
0x2898 mv r9,r0
0x289c ldi r8,#0
0x28a0 ld r1,@(60,sp)
0x28a4 mv r2,r8
0x28a8 ld r0,@(52,sp)
0x28ac bl 1c44 <gxr2_raw_row>
0x28b0 bnez r0,2904 <gxr2_semantic_validate+0x57c>
0x28b4 ldi r8,#13
```

gxr2_semantic_validate，bl，0x2da0。
```text
0x2d74 stb r6,@(33,sp)
0x2d78 ldi r2,#15
0x2d7c bl 13c <ig_copy>
0x2d80 ldi r1,#49
0x2d84 mv r0,sp
0x2d88 bl 2360 <gxr2_crc32>
0x2d8c ld r4,@(132,sp)
0x2d90 bne r4,r0,28b4 <gxr2_semantic_validate+0x52c>
0x2d94 ldi r10,#1
0x2d98 ld r0,@(52,sp)
0x2d9c mv r2,fp
0x2d9e mv r1,r11
0x2da0 bl 1c44 <gxr2_raw_row>
0x2da4 mv r2,r0
0x2da8 beqz r2,28b4 <gxr2_semantic_validate+0x52c>
```

gxr2_expand.constprop.0，bl，0x3af4。
```text
0x3acc ldub r5,@(1,r8)
0x3ad0 ldi r2,#4
0x3ad2 ldi r10,#0
0x3ad4 stb r5,@(1,r4)
0x3ad8 bl 13c <ig_copy>
0x3adc add3 r1,r8,#2
0x3ae0 add3 r0,fp,#445
0x3ae4 ldi r2,#2
0x3ae8 bl 13c <ig_copy>
0x3aec mv r2,r10
0x3aee mv r1,r8
0x3af0 mv r0,r11
0x3af4 bl 1c44 <gxr2_raw_row>
0x3af8 seth r5,#0x1
0x3afc add3 r5,r5,#-20352
```

gate_validate.constprop.0，bl，0x63dc。
```text
0x63b2 add r1,r0
0x63b4 ldi r0,#-1
0x63b8 bl 2320 <gxr2_crc_add>
0x63bc mv r4,r0
0x63c0 ldi r5,#0
0x63c4 seth r0,#0x1
0x63c8 add3 r0,r0,#-9956
0x63cc st r4,@(76,sp)
0x63d0 st r5,@(84,sp)
0x63d4 mv r2,r5
0x63d6 mv r1,r11
0x63d8 add r0,r12
0x63dc bl 1c44 <gxr2_raw_row>
0x63e0 ld r4,@(76,sp)
0x63e4 beqz r0,5ef0 <gate_validate.constprop.0+0x4d0>
```

verify，bl，0x6810。
```text
0x67e8 ldi r2,#1
0x67ea ldi r0,#-1
0x67ec addi r1,#1
0x67f0 bl 2320 <gxr2_crc_add>
0x67f4 mv r9,r0
0x67f8 ldi r10,#0
0x67fc ld r1,@(120,sp)
0x6800 seth r0,#0x1
0x6804 add3 r0,r0,#-6828
0x6808 add r0,r12
0x680a mv r2,r10
0x680c addi r0,#68
0x6810 bl 1c44 <gxr2_raw_row>
0x6814 srl3 r2,r1,#16
0x6818 mv r1,r0
```

verify，bl，0x699c。
```text
0x6974 ldi r2,#152
0x6978 add r1,r0
0x697a ldi r0,#-1
0x697c bl 2320 <gxr2_crc_add>
0x6980 seth r5,#0x1
0x6984 add3 r5,r5,#-7212
0x6988 st r5,@(104,sp)
0x698c mv r4,r0
0x6990 ld r1,@(112,sp)
0x6994 st r4,@(140,sp)
0x6998 mv r2,r11
0x699a mv r0,r10
0x699c bl 1c44 <gxr2_raw_row>
0x69a0 ld r4,@(140,sp)
0x69a4 beqz r0,6be0 <verify+0x6d8>
```

ig_init，bl，0x7a10。
```text
0x79e8 ld r1,@(84,sp)
0x79ec seth r5,#0x1
0x79f0 add3 r5,r5,#-8160
0x79f4 add r5,r12
0x79f8 st r5,@(132,sp)
0x79fc ldi r2,#0
0x79fe mv r0,r5
0x7a00 bl b48 <descriptor.lto_priv.0>
0x7a04 ld r5,@(132,sp)
0x7a08 mv r2,fp
0x7a0a mv r1,r0
0x7a0c mv r0,r5
0x7a10 bl 1c44 <gxr2_raw_row>
0x7a14 srl3 r2,r1,#16
0x7a18 mv r1,r0
```


gxr2_semantic_validate

verify，bl，0x6bc4。
```text
0x6ba2 mv r3,fp
0x6ba4 mv r1,r9
0x6ba6 mv r0,r8
0x6ba8 bl 5a20 <gate_validate.constprop.0>
0x6bac bnez r0,6be0 <verify+0x6d8>
0x6bb0 seth r11,#0x1
0x6bb4 add3 r11,r11,#-6976
0x6bb8 add r11,r12
0x6bba add r10,r12
0x6bbc add3 r1,r10,#156
0x6bc0 mv r2,r11
0x6bc2 mv r0,fp
0x6bc4 bl 2388 <gxr2_semantic_validate>
0x6bc8 bnez r0,6be0 <verify+0x6d8>
0x6bcc ld r4,@(8,r11)
```

ig_init，bl，0x7814。
```text
0x77ec add r1,r12
0x77ee mv r0,r4
0x77f0 bl ae94 <memcpy>
0x77f4 ld r7,@(84,sp)
0x77f8 seth r2,#0x1
0x77fc add3 r2,r2,#-8160
0x7800 mv r1,r9
0x7804 and3 r7,r7,#0xff
0x7808 st r7,@(100,sp)
0x780c stb r7,@(80,r0)
0x7810 add r2,r12
0x7812 add r1,r12
0x7814 bl 2388 <gxr2_semantic_validate>
0x7818 mv r9,r0
0x781c bnez r0,74f4 <ig_init+0x1a4>
```


identity.constprop.0

current.constprop.0，bl，0x87ee。
```text
0x87d8 push r8
0x87da push r12
0x87dc push lr
0x87de bl 87e0 <current.constprop.0+0x8>
0x87e0 seth r12,#0xffff
0x87e4 add3 r12,r12,#31008
0x87e8 add r12,lr
0x87ea ld lr,@sp
0x87ec mv r8,r0
0x87ee bl 8758 <identity.constprop.0>
0x87f0 beqz r0,8834 <current.constprop.0+0x5c>
0x87f4 ld24 r4,80151c <n+0x7f251c>
```

rv_call，bl，0x9484。
```text
0x9458 ld r6,@(24,sp)
0x945c st r4,@(24,r6)
0x9460 ldi r4,#160
0x9464 st r4,@(28,r6)
0x9468 add3 r4,r11,#-2
0x946c bnez r4,9420 <rv_call+0xbe0>
0x9470 ldi r10,#0
0x9472 bra 9480 <rv_call+0xc40>
0x9474 add3 r4,r11,#-2
0x9478 beqz r4,9444 <rv_call+0xc04>
0x947c ldi r10,#-4
0x9480 mv r0,fp
0x9484 bl 8758 <identity.constprop.0>
0x9488 cmpui r0,#1
0x948c mvfc r4,cbr
```

rv_call，bl，0x97dc。
```text
0x97b0 addi r5,#20
0x97b4 bnez r6,9778 <rv_call+0xf38>
0x97b8 ldi r10,#-2
0x97bc ld24 r4,80151c <n+0x7f251c>
0x97c0 slli r4,#0x6
0x97c4 ld r5,@(212,r4)
0x97c8 ldi r6,#-17
0x97ca mv r0,fp
0x97cc and r5,r6
0x97d0 st r5,@(212,r4)
0x97d4 ld r5,@(44,sp)
0x97d8 beqz r5,a900 <rv_call+0x20c0>
0x97dc bl 8758 <identity.constprop.0>
0x97e0 cmpui r0,#1
0x97e4 mvfc r4,cbr
```

rv_call，bl，0x9f48。
```text
0x9f1e add r6,r4
0x9f20 stb r7,@r6
0x9f22 bra 9f04 <rv_call+0x16c4>
0x9f24 add3 r5,r11,#-1
0x9f28 bnez r5,97bc <rv_call+0xf7c>
0x9f2c ld r11,@(20,sp)
0x9f30 addi r11,#-36
0x9f34 bnez r11,97bc <rv_call+0xf7c>
0x9f38 mv r0,sp
0x9f3c bl 6ef0 <rv_unit.constprop.0>
0x9f40 mv r10,r0
0x9f44 mv r0,fp
0x9f48 bl 8758 <identity.constprop.0>
0x9f4c beqz r0,97a4 <rv_call+0xf64>
0x9f50 bnez r10,9f6c <rv_call+0x172c>
```


ig_apply

地址引用：{"pc": "0xad30", "kind": "encoded GOTOFF function address", "target": "ig_apply", "owner": "ig_bootstrap"}
地址引用：{"pc": "0x8018", "kind": "resident entry offset, DAT/bootstrap exports", "target": "ig_apply", "owner": "resident"}

ig_bootstrap

地址引用：{"pc": "0xaa50", "kind": "resident entry offset, DAT/bootstrap exports", "target": "ig_bootstrap", "owner": "resident"}

ig_bx_apply

ig_event，bl，0x82e8。
```text
0x82c0 mv r11,r0
0x82c2 mv r3,fp
0x82c4 st r4,@(8,sp)
0x82c8 seth r4,#0x1
0x82cc add3 r4,r4,#-19772
0x82d0 add r4,r12
0x82d2 ld r4,@r4
0x82d4 st r0,@sp
0x82d8 st r4,@(4,sp)
0x82dc ld r2,@(44,r8)
0x82e0 ld r1,@(56,r8)
0x82e4 ld r0,@(60,r8)
0x82e8 bl 7b4 <ig_bx_apply>
0x82ec beqz r11,830c <ig_event+0x238>
0x82f0 mv r1,r11
```

ig_panel_open，bl，0x8410。
```text
0x83ec ldi r0,#37
0x83ee mv r3,r11
0x83f0 ldi r2,#0
0x83f4 st r4,@(8,sp)
0x83f8 seth r4,#0x1
0x83fc add3 r4,r4,#-19772
0x8400 add r4,r12
0x8402 ld r4,@r4
0x8404 st r4,@(4,sp)
0x8408 ldi r4,#1
0x840a st r4,@sp
0x840c ld r1,@(56,fp)
0x8410 bl 7b4 <ig_bx_apply>
0x8414 ldi r1,#1
0x8418 mv r0,r10
```


ig_bx_event

core_call，bl，0x434。
```text
0x404 addi r10,#-2
0x408 bnez r10,440 <core_call+0x148>
0x40c ldi r0,#9
0x410 ld r7,@(8,fp)
0x414 mv r1,r8
0x418 ld r2,@(8,sp)
0x41c st r7,@(4,sp)
0x420 ld r7,@(28,fp)
0x424 st r7,@sp
0x428 ld r3,@(16,fp)
0x42c st r5,@(16,sp)
0x430 st r6,@(12,sp)
0x434 bl 208 <ig_bx_event>
0x438 ld r6,@(12,sp)
0x43c ld r5,@(16,sp)
```

ig_bx_receipt，bl，0x630。
```text
0x602 ldub r5,@r5
0x604 add r9,r4
0x608 stb r5,@(33,r8)
0x60c ld r1,@r9
0x610 bl 184 <p32>
0x614 ldi r0,#3
0x618 ld r3,@(476,r10)
0x61c ldi r4,#0
0x620 ld r2,@(472,r10)
0x624 st r11,@(4,sp)
0x628 ld r1,@(8,sp)
0x62c st r4,@sp
0x630 bl 208 <ig_bx_event>
0x634 addi sp,#12
0x636 pop lr
```

finish，bl，0x120c。
```text
0x11ee add r4,r12
0x11f0 ldub r1,@(2474,r4)
0x11f4 mv r4,r9
0x11f6 add r4,r12
0x11f8 add r4,r5
0x11fa ld r4,@r4
0x11fc ldi r3,#0
0x11fe mv r2,r8
0x1200 ldi r0,#5
0x1204 st r4,@(4,sp)
0x1208 ldi r4,#0
0x120a st r4,@sp
0x120c bl 208 <ig_bx_event>
0x1210 bl 10f8 <workspace_close>
0x1214 beqz r0,121c <finish+0x78>
```

list_bind，bl，0x2250。
```text
0x2228 ld r2,@(392,r8)
0x222c mv r1,fp
0x2230 st r2,@(24,sp)
0x2234 st r2,@(36,sp)
0x2238 bl fbc <pn_request>
0x223c ldi r2,#0
0x2240 st r2,@(4,sp)
0x2244 st r2,@sp
0x2246 ldi r3,#0
0x2248 mv r2,r10
0x224a ldi r1,#16
0x224c ldi r0,#3
0x2250 bl 208 <ig_bx_event>
0x2254 seth r2,#0x1
0x2258 add3 r2,r2,#-7640
```

list_bind，bl，0x22c4。
```text
0x229c bl 13c <ig_copy>
0x22a0 ld r3,@(64,sp)
0x22a4 add3 r7,r8,#2128
0x22a8 st r7,@(48,fp)
0x22ac ldi r7,#40
0x22b0 st r7,@(52,fp)
0x22b4 st r3,@(4,sp)
0x22b8 st r3,@sp
0x22ba mv r2,r10
0x22bc ldi r3,#0
0x22be ldi r1,#17
0x22c0 ldi r0,#3
0x22c4 bl 208 <ig_bx_event>
0x22c8 ld r5,@(52,sp)
0x22cc add3 r0,r8,#380
```

ig_menu，bl，0x7be8。
```text
0x7bc0 add r8,r12
0x7bc4 ldub r4,@(2072,r8)
0x7bc8 beqz r4,8010 <ig_menu+0x48c>
0x7bcc ldi r11,#1
0x7bd0 stb r11,@(2082,r8)
0x7bd4 ldi r4,#0
0x7bd8 st r4,@(4,sp)
0x7bdc st r4,@sp
0x7bde ldi r2,#0
0x7be0 ldi r3,#0
0x7be2 ldi r1,#0
0x7be4 ldi r0,#10
0x7be8 bl 208 <ig_bx_event>
0x7bec ld r6,@(4,r8)
0x7bf0 ldi r4,#64
```

ig_menu，bl，0x7cd4。
```text
0x7cb4 pop r10
0x7cb6 pop r9
0x7cb8 pop r8
0x7cba pop fp
0x7cbc jmp lr
0x7cc0 ldi r4,#0
0x7cc4 st r4,@(4,sp)
0x7cc8 st r4,@sp
0x7cca ldi r3,#0
0x7ccc ldi r2,#0
0x7cce ldi r1,#9
0x7cd0 ldi r0,#10
0x7cd4 bl 208 <ig_bx_event>
0x7cd8 ld24 r5,ffff <n+0xfff>
0x7cdc mv r8,r9
```

ig_bootstrap，bl，0xac78。
```text
0xac48 bl 184 <p32>
0xac4c ld r1,@(352,fp)
0xac50 add3 r0,r8,#160
0xac54 bl 184 <p32>
0xac58 ld r5,@(68,sp)
0xac5c ldi r1,#0
0xac60 ld r3,@(332,fp)
0xac64 ldi r0,#1
0xac68 ld r2,@(328,fp)
0xac6c st r5,@(4,sp)
0xac70 ld r4,@(212,r11)
0xac74 st r4,@sp
0xac78 bl 208 <ig_bx_event>
0xac7c ld r5,@(68,sp)
0xac80 ldi r1,#5
```

ig_bootstrap，bl，0xac9c。
```text
0xac6c st r5,@(4,sp)
0xac70 ld r4,@(212,r11)
0xac74 st r4,@sp
0xac78 bl 208 <ig_bx_event>
0xac7c ld r5,@(68,sp)
0xac80 ldi r1,#5
0xac84 ld r3,@(104,r11)
0xac88 ldi r0,#9
0xac8c ld r2,@(56,r11)
0xac90 st r5,@(4,sp)
0xac94 ld r4,@(28,r10)
0xac98 st r4,@sp
0xac9c bl 208 <ig_bx_event>
0xaca0 ld r4,@(4,r9)
0xaca4 ldi r1,#40
```


ig_bx_receipt

list_bind，bl，0x1ea4。
```text
0x1e84 push r11
0x1e86 push r12
0x1e88 push lr
0x1e8a bl 1e8c <list_bind+0x10>
0x1e8c seth r12,#0x0
0x1e90 add3 r12,r12,#-7564
0x1e94 add r12,lr
0x1e96 addi sp,#-72
0x1e98 ld lr,@(72,sp)
0x1e9c ldi r2,#15
0x1e9e ldi r1,#0
0x1ea0 ldi r0,#0
0x1ea4 bl 4e0 <ig_bx_receipt>
0x1ea8 seth r4,#0x1
0x1eac add3 r4,r4,#-7644
```

list_bind，bl，0x2168。
```text
0x213c bl fbc <pn_request>
0x2140 ld r5,@(64,sp)
0x2144 ldi r2,#26
0x2146 ldi r1,#0
0x2148 ldub r4,@(807,r5)
0x214c ldi r0,#0
0x2150 st r4,@(56,r9)
0x2154 st r4,@(44,r9)
0x2158 add3 r4,r8,#3648
0x215c st r4,@(48,r9)
0x2160 ldi r4,#40
0x2164 st r4,@(52,r9)
0x2168 bl 4e0 <ig_bx_receipt>
0x216c seth r4,#0x1
0x2170 add3 r4,r4,#-7640
```

list_bind，bl，0x2198。
```text
0x2174 add3 r0,r8,#380
0x2178 add r4,r12
0x217a mv r3,r9
0x217c ldi r2,#1
0x217e st r4,@sp
0x2180 ldi r1,#10
0x2184 bl 101c <pn_call>
0x2188 mv r9,r0
0x218c ldi r2,#26
0x2190 beqz r0,22fc <list_bind+0x480>
0x2194 ldi r1,#-1
0x2196 ldi r0,#0
0x2198 bl 4e0 <ig_bx_receipt>
0x219c ldi r9,#-1
0x21a0 addi sp,#72
```

list_bind，bl，0x2300。
```text
0x22d8 add r3,r12
0x22da ldi r1,#11
0x22dc bl 101c <pn_call>
0x22e0 ld r4,@(68,sp)
0x22e4 add3 r5,r11,#70
0x22e8 bnez r0,219c <list_bind+0x320>
0x22ec st r11,@+r4
0x22f0 st r4,@(-64,r4)
0x22f4 addi r10,#1
0x22f6 mv r11,r5
0x22f8 bra 2084 <list_bind+0x208>
0x22fc ldi r1,#1
0x2300 bl 4e0 <ig_bx_receipt>
0x2304 seth r4,#0x1
0x2308 add3 r4,r4,#-7640
```

ig_menu，bl，0x7c64。
```text
0x7c40 bnez r4,7c98 <ig_menu+0x114>
0x7c44 mv r8,r9
0x7c46 add r8,r12
0x7c48 ldub r4,@(2074,r8)
0x7c4c bnez r4,7c98 <ig_menu+0x114>
0x7c50 ldi r4,#1
0x7c54 stb r4,@(2074,r8)
0x7c58 ldi r2,#8
0x7c5a ldi r4,#2
0x7c5c st r4,@(2124,r8)
0x7c60 ldi r1,#2
0x7c62 ldi r0,#1
0x7c64 bl 4e0 <ig_bx_receipt>
0x7c68 ldub r4,@(2076,r8)
0x7c6c beqz r4,7c80 <ig_menu+0xfc>
```


ig_bx_unit

ig_init，bl，0x74e8。
```text
0x74c4 bne r4,r7,7468 <ig_init+0x118>
0x74c8 mv r9,r10
0x74ca add r9,r12
0x74cc ld r4,@(4,r9)
0x74d0 ld r1,@(40,r4)
0x74d4 ld r4,@(36,r4)
0x74d8 bnez r4,7500 <ig_init+0x1b0>
0x74dc ldi r4,#1
0x74de add r10,r12
0x74e0 stb r4,@(2082,r10)
0x74e4 ldi r1,#-6
0x74e6 ldi r0,#1
0x74e8 bl 69c <ig_bx_unit>
0x74ec ldi r4,#3
0x74f0 stb r4,@(2083,r10)
```

ig_init，bl，0x7524。
```text
0x74fc bra 73b4 <ig_init+0x64>
0x7500 not r6,r4
0x7502 cmpu r6,r1
0x7504 bc 74dc <ig_init+0x18c>
0x7508 add3 r3,r9,#72
0x750c st r5,@(132,sp)
0x7510 st r4,@sp
0x7512 mv r2,fp
0x7514 mv r0,r8
0x7518 bl 5a20 <gate_validate.constprop.0>
0x751c bnez r0,74dc <ig_init+0x18c>
0x7520 ldi r1,#0
0x7524 bl 69c <ig_bx_unit>
0x7528 seth fp,#0x1
0x752c add3 fp,fp,#-7684
```


ig_event

地址引用：{"pc": "0xacf0", "kind": "encoded GOTOFF function address", "target": "ig_event", "owner": "ig_bootstrap"}
地址引用：{"pc": "0x80d4", "kind": "resident entry offset, DAT/bootstrap exports", "target": "ig_event", "owner": "resident"}

ig_init

地址引用：{"pc": "0xacbc", "kind": "encoded GOTOFF function address", "target": "ig_init", "owner": "ig_bootstrap"}
地址引用：{"pc": "0x7350", "kind": "resident entry offset, DAT/bootstrap exports", "target": "ig_init", "owner": "resident"}

ig_menu

地址引用：{"pc": "0xace0", "kind": "encoded GOTOFF function address", "target": "ig_menu", "owner": "ig_bootstrap"}
地址引用：{"pc": "0x7b84", "kind": "resident entry offset, DAT/bootstrap exports", "target": "ig_menu", "owner": "resident"}

ig_panel_abort

地址引用：{"pc": "0xad20", "kind": "encoded GOTOFF function address", "target": "ig_panel_abort", "owner": "ig_bootstrap"}
地址引用：{"pc": "0x8654", "kind": "resident entry offset, DAT/bootstrap exports", "target": "ig_panel_abort", "owner": "resident"}

ig_panel_event

地址引用：{"pc": "0xad10", "kind": "encoded GOTOFF function address", "target": "ig_panel_event", "owner": "ig_bootstrap"}
地址引用：{"pc": "0x85f0", "kind": "resident entry offset, DAT/bootstrap exports", "target": "ig_panel_event", "owner": "resident"}

ig_panel_open

地址引用：{"pc": "0xad00", "kind": "encoded GOTOFF function address", "target": "ig_panel_open", "owner": "ig_bootstrap"}
地址引用：{"pc": "0x8330", "kind": "resident entry offset, DAT/bootstrap exports", "target": "ig_panel_open", "owner": "resident"}

ig_stop

地址引用：{"pc": "0xad40", "kind": "encoded GOTOFF function address", "target": "ig_stop", "owner": "ig_bootstrap"}
地址引用：{"pc": "0x86c8", "kind": "resident entry offset, DAT/bootstrap exports", "target": "ig_stop", "owner": "resident"}

ingress

ig_init，bl，0x737c。
```text
0x7354 push r9
0x7356 push r10
0x7358 push r11
0x735a push r12
0x735c push lr
0x7360 add3 sp,sp,#-136
0x7364 bl 7368 <ig_init+0x18>
0x7368 seth r12,#0x0
0x736c add3 r12,r12,#-29288
0x7370 add r12,lr
0x7374 ld lr,@(136,sp)
0x7378 st r3,@(88,sp)
0x737c bl 6fb0 <ingress>
0x7380 beqz r0,7b7c <ig_init+0x82c>
0x7384 seth r11,#0x1
```

ig_menu，bl，0x7ba8。
```text
0x7b88 push r9
0x7b8a push r10
0x7b8c push r11
0x7b8e push r12
0x7b90 push lr
0x7b92 bl 7b94 <ig_menu+0x10>
0x7b94 seth r12,#0x0
0x7b98 add3 r12,r12,#-31380
0x7b9c add r12,lr
0x7b9e addi sp,#-48
0x7ba0 ld lr,@(48,sp)
0x7ba4 mv r10,r3
0x7ba8 bl 6fb0 <ingress>
0x7bac beqz r0,8010 <ig_menu+0x48c>
0x7bb0 seth r8,#0x1
```

ig_apply，bl，0x8034。
```text
0x8018 push r8
0x801a push r9
0x801c push r12
0x801e push lr
0x8020 bl 8024 <ig_apply+0xc>
0x8024 seth r12,#0x0
0x8028 add3 r12,r12,#-32548
0x802c add r12,lr
0x802e ld lr,@sp
0x8030 mv r9,r2
0x8032 mv r8,r3
0x8034 bl 6fb0 <ingress>
0x8038 beqz r0,80d0 <ig_apply+0xb8>
0x803c seth r4,#0x1
```

ig_event，bl，0x80f8。
```text
0x80da push r10
0x80dc push r11
0x80de push r12
0x80e0 push lr
0x80e2 bl 80e4 <ig_event+0x10>
0x80e4 seth r12,#0x0
0x80e8 add3 r12,r12,#-32740
0x80ec add r12,lr
0x80ee addi sp,#-76
0x80f0 ld lr,@(76,sp)
0x80f4 mv r8,r2
0x80f6 mv r10,r3
0x80f8 bl 6fb0 <ingress>
0x80fc beqz r0,832c <ig_event+0x258>
0x8100 seth r4,#0x1
```

ig_panel_open，bl，0x8354。
```text
0x8336 push r10
0x8338 push r11
0x833a push r12
0x833c push lr
0x833e bl 8340 <ig_panel_open+0x10>
0x8340 seth r12,#0xffff
0x8344 add3 r12,r12,#32192
0x8348 add r12,lr
0x834a addi sp,#-32
0x834c ld lr,@(32,sp)
0x8350 mv fp,r2
0x8352 mv r10,r3
0x8354 bl 6fb0 <ingress>
0x8358 beqz r0,85ec <ig_panel_open+0x2bc>
0x835c seth r8,#0x1
```

ig_panel_event，bl，0x860c。
```text
0x85f0 push r8
0x85f2 push r9
0x85f4 push r12
0x85f6 push lr
0x85f8 bl 85fc <ig_panel_event+0xc>
0x85fc seth r12,#0xffff
0x8600 add3 r12,r12,#31492
0x8604 add r12,lr
0x8606 ld lr,@sp
0x8608 mv r9,r2
0x860a mv r8,r3
0x860c bl 6fb0 <ingress>
0x8610 beqz r0,8650 <ig_panel_event+0x60>
0x8614 seth r4,#0x1
```

ig_panel_abort，bl，0x866c。
```text
0x8654 push r8
0x8656 push r12
0x8658 push lr
0x865a bl 865c <ig_panel_abort+0x8>
0x865c seth r12,#0xffff
0x8660 add3 r12,r12,#31396
0x8664 add r12,lr
0x8666 ld lr,@sp
0x8668 mv r8,r3
0x866c bl 6fb0 <ingress>
0x8670 beqz r0,86c4 <ig_panel_abort+0x70>
0x8674 seth r5,#0x1
```

ig_stop，bl，0x86e0。
```text
0x86c8 push r8
0x86ca push r12
0x86cc push lr
0x86ce bl 86d0 <ig_stop+0x8>
0x86d0 seth r12,#0xffff
0x86d4 add3 r12,r12,#31280
0x86d8 add r12,lr
0x86da ld lr,@sp
0x86dc mv r8,r3
0x86e0 bl 6fb0 <ingress>
0x86e4 beqz r0,8754 <ig_stop+0x8c>
0x86e8 seth r5,#0x1
```

ig_bootstrap，bl，0xaa74。
```text
0xaa54 push r9
0xaa56 push r10
0xaa58 push r11
0xaa5a push r12
0xaa5c push lr
0xaa5e bl aa60 <ig_bootstrap+0x10>
0xaa60 seth r12,#0xffff
0xaa64 add3 r12,r12,#22176
0xaa68 add r12,lr
0xaa6a addi sp,#-72
0xaa6c ld lr,@(72,sp)
0xaa70 st r3,@(60,sp)
0xaa74 bl 6fb0 <ingress>
0xaa78 beqz r0,ae90 <ig_bootstrap+0x440>
0xaa7c add3 fp,sp,#40
```


io_close

地址引用：{"pc": "0x6b14", "kind": "encoded GOTOFF function address", "target": "io_close", "owner": "verify"}

io_open

地址引用：{"pc": "0x6ad8", "kind": "encoded GOTOFF function address", "target": "io_open", "owner": "verify"}

io_read

地址引用：{"pc": "0x6af4", "kind": "encoded GOTOFF function address", "target": "io_read", "owner": "verify"}

io_remove

地址引用：{"pc": "0x6b24", "kind": "encoded GOTOFF function address", "target": "io_remove", "owner": "verify"}

io_rename

地址引用：{"pc": "0x6b34", "kind": "encoded GOTOFF function address", "target": "io_rename", "owner": "verify"}

io_write

地址引用：{"pc": "0x6b04", "kind": "encoded GOTOFF function address", "target": "io_write", "owner": "verify"}

list_bind

ig_menu，bl，0x7eb8。
```text
0x7e8c ldub r4,@(807,r9)
0x7e90 cmpu r4,fp
0x7e92 bnc 7f5c <ig_menu+0x3d8>
0x7e94 ldub r4,@(2470,r9)
0x7e98 stb r4,@(806,r9)
0x7e9c ldi r4,#1
0x7ea0 stb r4,@(805,r9)
0x7ea4 ldub r4,@(2467,r9)
0x7ea8 beqz r4,8004 <ig_menu+0x480>
0x7eac ldub r4,@(185,r9)
0x7eb0 add r11,r12
0x7eb4 stb r4,@(803,r11)
0x7eb8 bl 1e7c <list_bind>
0x7ebc ldi r4,#0
0x7ec0 cmpu r4,r0
```

ig_apply，bl，0x80b0。
```text
0x8084 add3 r5,r5,#-6828
0x8088 add r5,r12
0x808c ldub r4,@(805,r5)
0x8090 beqz r4,80cc <ig_apply+0xb4>
0x8094 ld r4,@(40,r9)
0x8098 addi r4,#1
0x809c and3 r4,r4,#0xff
0x80a0 beqz r4,80cc <ig_apply+0xb4>
0x80a4 ldub r6,@(807,r5)
0x80a8 cmpu r6,r4
0x80aa bc 80cc <ig_apply+0xb4>
0x80ac stb r4,@(803,r5)
0x80b0 bl 1e7c <list_bind>
0x80b4 ldi r4,#0
0x80b8 cmpu r4,r0
```


mapped

eng_apply，bl，0x4ee8。
```text
0x4ec8 st fp,@r10
0x4eca add r4,r12
0x4ecc st r4,@(8,sp)
0x4ed0 ldi r4,#0
0x4ed4 st r4,@(4,sp)
0x4ed8 ldi r4,#24
0x4eda st r4,@sp
0x4edc mv r3,r10
0x4ede ldi r2,#0
0x4ee0 ldi r1,#1
0x4ee2 ldi r0,#6
0x4ee4 bl 43c0 <svc.constprop.0>
0x4ee8 bl 9bc <mapped>
0x4eec mv r9,r0
0x4ef0 bnez r0,5764 <eng_apply+0xe14>
```

eng_apply，bl，0x5148。
```text
0x5120 add3 r4,r4,#-8960
0x5124 add r4,r12
0x5128 st r4,@(8,sp)
0x512c ldi r4,#0
0x5130 st r4,@(4,sp)
0x5134 st r4,@sp
0x5136 ldi r3,#0
0x5138 ldi r1,#3
0x513a ldi r0,#6
0x513c bl 43c0 <svc.constprop.0>
0x5140 beqz r0,5644 <eng_apply+0xcf4>
0x5144 bnez r8,4a14 <eng_apply+0xc4>
0x5148 bl 9bc <mapped>
0x514c bra 5640 <eng_apply+0xcf0>
0x5150 ld r2,@(24,sp)
```

eng_apply，bl，0x55bc。
```text
0x559c stb r6,@(2468,r5)
0x55a0 st r4,@(4,sp)
0x55a4 mv r5,r10
0x55a6 add r5,r12
0x55a8 st r5,@(8,sp)
0x55ac ldi r4,#80
0x55ae st r4,@sp
0x55b0 add r3,r12
0x55b2 ldi r2,#0
0x55b4 ldi r1,#2
0x55b6 ldi r0,#6
0x55b8 bl 43c0 <svc.constprop.0>
0x55bc bl 9bc <mapped>
0x55c0 bnez r0,5474 <eng_apply+0xb24>
0x55c4 bl 45a8 <fresh>
```

eng_apply，bl，0x55f8。
```text
0x55d0 add r11,r12
0x55d4 stb r4,@(2474,r11)
0x55d8 add r10,r12
0x55dc st r10,@(8,sp)
0x55e0 ldi r4,#0
0x55e4 st r4,@(4,sp)
0x55e8 st r4,@sp
0x55ea ldi r3,#0
0x55ec ldi r2,#0
0x55ee ldi r1,#1
0x55f0 ldi r0,#5
0x55f4 bl 43c0 <svc.constprop.0>
0x55f8 bl 9bc <mapped>
0x55fc mv fp,r0
0x5600 bnez r0,5474 <eng_apply+0xb24>
```

eng_apply，bl，0x5630。
```text
0x5608 beqz r0,5474 <eng_apply+0xb24>
0x560c seth r4,#0x1
0x5610 add3 r4,r4,#-8928
0x5614 add r4,r12
0x5618 ld r2,@(8,r4)
0x561c st r10,@(8,sp)
0x5620 st fp,@(4,sp)
0x5624 ldi r3,#0
0x5626 ldi r1,#3
0x5628 st fp,@sp
0x562a ldi r0,#6
0x562c bl 43c0 <svc.constprop.0>
0x5630 bl 9bc <mapped>
0x5634 mv r10,r0
0x5638 beqz r0,564c <eng_apply+0xcfc>
```


metadata.lto_priv.0

slot_descriptor，bl，0xcea。
```text
0xcca mv r9,r1
0xccc mv r4,r2
0xcd0 beqz r0,d10 <slot_descriptor+0x60>
0xcd4 ldub r5,@(82,r0)
0xcd8 beqz r5,d1c <slot_descriptor+0x6c>
0xcdc ldi r5,#2
0xcde cmpu r5,r1
0xce0 bc d1c <slot_descriptor+0x6c>
0xce2 addi r4,#-1
0xce4 ldi r5,#15
0xce6 cmpu r5,r4
0xce8 bc d1c <slot_descriptor+0x6c>
0xcea bl afc <metadata.lto_priv.0>
0xcec lduh r5,@(76,r8)
0xcf0 sll3 r4,r5,#1
```

gxr2_parameter，bl，0xd8c。
```text
0xd6a bra de8 <gxr2_parameter+0xc8>
0xd6c st r4,@(4,sp)
0xd70 mv r0,r4
0xd72 st r6,@sp
0xd74 bl 104 <be32.lto_priv.0>
0xd78 ld r4,@(4,sp)
0xd7c ld r6,@sp
0xd7e addi r4,#4
0xd80 bne r0,fp,dfc <gxr2_parameter+0xdc>
0xd84 mv r2,r11
0xd86 mv r1,r10
0xd88 mv r0,r8
0xd8c bl afc <metadata.lto_priv.0>
0xd90 sll3 r4,r9,#1
0xd94 add r4,r9
```

gxr2_semantic_validate，bl，0x2f58。
```text
0x2f30 ldi r6,#0
0x2f34 ld r4,@(64,sp)
0x2f38 st r6,@(56,sp)
0x2f3c ldub r5,@(14,r5)
0x2f40 add r4,r0
0x2f44 st r4,@(76,sp)
0x2f48 st r5,@(68,sp)
0x2f4c mv fp,r4
0x2f4e addi fp,#68
0x2f50 ld r0,@(52,sp)
0x2f54 mv r2,r11
0x2f56 mv r1,r10
0x2f58 bl afc <metadata.lto_priv.0>
0x2f5c ld r6,@(96,sp)
0x2f60 mv r5,r0
```

gxr2_semantic_validate，bl，0x31d4。
```text
0x31ac ldi r4,#1
0x31ae sll r4,r8
0x31b0 or r5,r4
0x31b4 st r5,@(56,sp)
0x31b8 bra 309c <gxr2_semantic_validate+0xd14>
0x31bc ld r0,@(52,sp)
0x31c0 mv r2,r8
0x31c2 mv r1,r10
0x31c4 bl b48 <descriptor.lto_priv.0>
0x31c8 ldub r2,@r0
0x31cc mv r1,r10
0x31d0 ld r0,@(52,sp)
0x31d4 bl afc <metadata.lto_priv.0>
0x31d8 mv r4,r0
0x31dc add r4,r9
```

verify，bl，0x66e0。
```text
0x66b0 cmpu r4,r5
0x66b4 bc 6be0 <verify+0x6d8>
0x66b8 ldub r4,@(13,sp)
0x66bc ldi r6,#15
0x66c0 st r4,@(108,sp)
0x66c4 addi r4,#-1
0x66c8 and3 r4,r4,#0xff
0x66cc cmpu r6,r4
0x66d0 bc 6be0 <verify+0x6d8>
0x66d4 ld r2,@(108,sp)
0x66d8 add3 r0,r9,#68
0x66dc mv r1,r5
0x66e0 bl afc <metadata.lto_priv.0>
0x66e4 lduh r11,@(144,r9)
0x66e8 st r0,@(128,sp)
```

ig_init，bl，0x78c8。
```text
0x78a2 addi r4,#16
0x78a4 add r10,r4
0x78a8 mv r0,r10
0x78ac bl 104 <be32.lto_priv.0>
0x78b0 ld fp,@(116,sp)
0x78b4 ldi r11,#1
0x78b6 add fp,r0
0x78b8 seth r0,#0x1
0x78bc add3 r0,r0,#-8160
0x78c0 mv r2,r11
0x78c2 mv r1,r9
0x78c4 add r0,r12
0x78c8 bl afc <metadata.lto_priv.0>
0x78cc ld r2,@(108,sp)
0x78d0 add3 r7,r0,#24
```


metadata.lto_priv.1

slot_descriptor，bl，0xcea。
```text
0xcca mv r9,r1
0xccc mv r4,r2
0xcd0 beqz r0,d10 <slot_descriptor+0x60>
0xcd4 ldub r5,@(82,r0)
0xcd8 beqz r5,d1c <slot_descriptor+0x6c>
0xcdc ldi r5,#2
0xcde cmpu r5,r1
0xce0 bc d1c <slot_descriptor+0x6c>
0xce2 addi r4,#-1
0xce4 ldi r5,#15
0xce6 cmpu r5,r4
0xce8 bc d1c <slot_descriptor+0x6c>
0xcea bl afc <metadata.lto_priv.0>
0xcec lduh r5,@(76,r8)
0xcf0 sll3 r4,r5,#1
```

gxr2_parameter，bl，0xd8c。
```text
0xd6a bra de8 <gxr2_parameter+0xc8>
0xd6c st r4,@(4,sp)
0xd70 mv r0,r4
0xd72 st r6,@sp
0xd74 bl 104 <be32.lto_priv.0>
0xd78 ld r4,@(4,sp)
0xd7c ld r6,@sp
0xd7e addi r4,#4
0xd80 bne r0,fp,dfc <gxr2_parameter+0xdc>
0xd84 mv r2,r11
0xd86 mv r1,r10
0xd88 mv r0,r8
0xd8c bl afc <metadata.lto_priv.0>
0xd90 sll3 r4,r9,#1
0xd94 add r4,r9
```

gxr2_semantic_validate，bl，0x2f58。
```text
0x2f30 ldi r6,#0
0x2f34 ld r4,@(64,sp)
0x2f38 st r6,@(56,sp)
0x2f3c ldub r5,@(14,r5)
0x2f40 add r4,r0
0x2f44 st r4,@(76,sp)
0x2f48 st r5,@(68,sp)
0x2f4c mv fp,r4
0x2f4e addi fp,#68
0x2f50 ld r0,@(52,sp)
0x2f54 mv r2,r11
0x2f56 mv r1,r10
0x2f58 bl afc <metadata.lto_priv.0>
0x2f5c ld r6,@(96,sp)
0x2f60 mv r5,r0
```

gxr2_semantic_validate，bl，0x31d4。
```text
0x31ac ldi r4,#1
0x31ae sll r4,r8
0x31b0 or r5,r4
0x31b4 st r5,@(56,sp)
0x31b8 bra 309c <gxr2_semantic_validate+0xd14>
0x31bc ld r0,@(52,sp)
0x31c0 mv r2,r8
0x31c2 mv r1,r10
0x31c4 bl b48 <descriptor.lto_priv.0>
0x31c8 ldub r2,@r0
0x31cc mv r1,r10
0x31d0 ld r0,@(52,sp)
0x31d4 bl afc <metadata.lto_priv.0>
0x31d8 mv r4,r0
0x31dc add r4,r9
```

verify，bl，0x66e0。
```text
0x66b0 cmpu r4,r5
0x66b4 bc 6be0 <verify+0x6d8>
0x66b8 ldub r4,@(13,sp)
0x66bc ldi r6,#15
0x66c0 st r4,@(108,sp)
0x66c4 addi r4,#-1
0x66c8 and3 r4,r4,#0xff
0x66cc cmpu r6,r4
0x66d0 bc 6be0 <verify+0x6d8>
0x66d4 ld r2,@(108,sp)
0x66d8 add3 r0,r9,#68
0x66dc mv r1,r5
0x66e0 bl afc <metadata.lto_priv.0>
0x66e4 lduh r11,@(144,r9)
0x66e8 st r0,@(128,sp)
```

ig_init，bl，0x78c8。
```text
0x78a2 addi r4,#16
0x78a4 add r10,r4
0x78a8 mv r0,r10
0x78ac bl 104 <be32.lto_priv.0>
0x78b0 ld fp,@(116,sp)
0x78b4 ldi r11,#1
0x78b6 add fp,r0
0x78b8 seth r0,#0x1
0x78bc add3 r0,r0,#-8160
0x78c0 mv r2,r11
0x78c2 mv r1,r9
0x78c4 add r0,r12
0x78c8 bl afc <metadata.lto_priv.0>
0x78cc ld r2,@(108,sp)
0x78d0 add3 r7,r0,#24
```


metadata.lto_priv.2

slot_descriptor，bl，0xcea。
```text
0xcca mv r9,r1
0xccc mv r4,r2
0xcd0 beqz r0,d10 <slot_descriptor+0x60>
0xcd4 ldub r5,@(82,r0)
0xcd8 beqz r5,d1c <slot_descriptor+0x6c>
0xcdc ldi r5,#2
0xcde cmpu r5,r1
0xce0 bc d1c <slot_descriptor+0x6c>
0xce2 addi r4,#-1
0xce4 ldi r5,#15
0xce6 cmpu r5,r4
0xce8 bc d1c <slot_descriptor+0x6c>
0xcea bl afc <metadata.lto_priv.0>
0xcec lduh r5,@(76,r8)
0xcf0 sll3 r4,r5,#1
```

gxr2_parameter，bl，0xd8c。
```text
0xd6a bra de8 <gxr2_parameter+0xc8>
0xd6c st r4,@(4,sp)
0xd70 mv r0,r4
0xd72 st r6,@sp
0xd74 bl 104 <be32.lto_priv.0>
0xd78 ld r4,@(4,sp)
0xd7c ld r6,@sp
0xd7e addi r4,#4
0xd80 bne r0,fp,dfc <gxr2_parameter+0xdc>
0xd84 mv r2,r11
0xd86 mv r1,r10
0xd88 mv r0,r8
0xd8c bl afc <metadata.lto_priv.0>
0xd90 sll3 r4,r9,#1
0xd94 add r4,r9
```

gxr2_semantic_validate，bl，0x2f58。
```text
0x2f30 ldi r6,#0
0x2f34 ld r4,@(64,sp)
0x2f38 st r6,@(56,sp)
0x2f3c ldub r5,@(14,r5)
0x2f40 add r4,r0
0x2f44 st r4,@(76,sp)
0x2f48 st r5,@(68,sp)
0x2f4c mv fp,r4
0x2f4e addi fp,#68
0x2f50 ld r0,@(52,sp)
0x2f54 mv r2,r11
0x2f56 mv r1,r10
0x2f58 bl afc <metadata.lto_priv.0>
0x2f5c ld r6,@(96,sp)
0x2f60 mv r5,r0
```

gxr2_semantic_validate，bl，0x31d4。
```text
0x31ac ldi r4,#1
0x31ae sll r4,r8
0x31b0 or r5,r4
0x31b4 st r5,@(56,sp)
0x31b8 bra 309c <gxr2_semantic_validate+0xd14>
0x31bc ld r0,@(52,sp)
0x31c0 mv r2,r8
0x31c2 mv r1,r10
0x31c4 bl b48 <descriptor.lto_priv.0>
0x31c8 ldub r2,@r0
0x31cc mv r1,r10
0x31d0 ld r0,@(52,sp)
0x31d4 bl afc <metadata.lto_priv.0>
0x31d8 mv r4,r0
0x31dc add r4,r9
```

verify，bl，0x66e0。
```text
0x66b0 cmpu r4,r5
0x66b4 bc 6be0 <verify+0x6d8>
0x66b8 ldub r4,@(13,sp)
0x66bc ldi r6,#15
0x66c0 st r4,@(108,sp)
0x66c4 addi r4,#-1
0x66c8 and3 r4,r4,#0xff
0x66cc cmpu r6,r4
0x66d0 bc 6be0 <verify+0x6d8>
0x66d4 ld r2,@(108,sp)
0x66d8 add3 r0,r9,#68
0x66dc mv r1,r5
0x66e0 bl afc <metadata.lto_priv.0>
0x66e4 lduh r11,@(144,r9)
0x66e8 st r0,@(128,sp)
```

ig_init，bl，0x78c8。
```text
0x78a2 addi r4,#16
0x78a4 add r10,r4
0x78a8 mv r0,r10
0x78ac bl 104 <be32.lto_priv.0>
0x78b0 ld fp,@(116,sp)
0x78b4 ldi r11,#1
0x78b6 add fp,r0
0x78b8 seth r0,#0x1
0x78bc add3 r0,r0,#-8160
0x78c0 mv r2,r11
0x78c2 mv r1,r9
0x78c4 add r0,r12
0x78c8 bl afc <metadata.lto_priv.0>
0x78cc ld r2,@(108,sp)
0x78d0 add3 r7,r0,#24
```


open_read

remove_owned，bl，0x1620。
```text
0x15fc add3 r12,r12,#-5368
0x1600 add r12,lr
0x1602 ldi r4,#16
0x1604 addi sp,#-4
0x1608 ld lr,@(4,sp)
0x160c and r4,r5
0x160e mv fp,r0
0x1610 mv r8,r1
0x1612 mv r10,r2
0x1614 mv r9,r3
0x1618 beqz r4,16a0 <remove_owned+0xc0>
0x161c mv r3,sp
0x1620 bl 1380 <open_read>
0x1624 bnez r0,168c <remove_owned+0xac>
0x1628 ld r1,@sp
```

io_open，bl，0x1898。
```text
0x1874 bra 183c <io_open+0x16c>
0x1878 bnc 18b0 <io_open+0x1e0>
0x187c ldi r1,#-3
0x187e bra 183c <io_open+0x16c>
0x1880 ldi r7,#15
0x1882 cmpu r7,r11
0x1884 bc 1790 <io_open+0xc0>
0x1888 beqz r9,1864 <io_open+0x194>
0x188c bnez r6,1794 <io_open+0xc4>
0x1890 mv r1,sp
0x1892 mv r3,r9
0x1894 mv r0,fp
0x1898 bl 1380 <open_read>
0x189c mv r1,r0
0x18a0 beqz r0,1858 <io_open+0x188>
```


path

rv_call，bl，0x8d88。
```text
0x8d5c bnez r6,8ad0 <rv_call+0x290>
0x8d60 ld r6,@(32,fp)
0x8d64 bnez r6,8ad0 <rv_call+0x290>
0x8d68 ld r6,@(36,fp)
0x8d6c bnez r6,8ad0 <rv_call+0x290>
0x8d70 ld r2,@(28,fp)
0x8d74 add3 r4,fp,#8
0x8d78 add3 r9,r8,#720
0x8d7c st r4,@(48,sp)
0x8d80 st r5,@(60,sp)
0x8d84 mv r1,r4
0x8d86 mv r0,r9
0x8d88 bl 3214 <path>
0x8d8c ld r4,@(48,sp)
0x8d90 ld r5,@(60,sp)
```

rv_call，bl，0xa9bc。
```text
0xa990 addi r5,#-4
0xa994 bnez r5,8ad0 <rv_call+0x290>
0xa998 ld r2,@(44,fp)
0xa99c ldi r6,#1
0xa9a0 add3 r5,r2,#-2
0xa9a4 cmpu r6,r5
0xa9a8 bc 8ad0 <rv_call+0x290>
0xa9ac ld r5,@(48,fp)
0xa9b0 beq r2,r5,8ad0 <rv_call+0x290>
0xa9b4 add3 r10,r8,#744
0xa9b8 mv r1,r4
0xa9ba mv r0,r10
0xa9bc bl 3214 <path>
0xa9c0 beqz r0,8ad0 <rv_call+0x290>
0xa9c4 mv r1,r10
```


pn_address

pn_native_from_seed，bl，0xf48。
```text
0xf20 ld r1,@(8,r9)
0xf24 ldi r2,#132
0xf28 add3 r0,r8,#104
0xf2c bl 13c <ig_copy>
0xf30 add3 r4,r8,#276
0xf34 ld r6,@(4,fp)
0xf38 addi fp,#4
0xf3a ldi r2,#4
0xf3c st r6,@+r4
0xf40 st r4,@(8,sp)
0xf44 mv r1,r4
0xf46 mv r0,r10
0xf48 bl e00 <pn_address>
0xf4c ld r4,@(8,sp)
0xf50 st r0,@(-44,r4)
```

pn_native_from_seed，bl，0xf66。
```text
0xf40 st r4,@(8,sp)
0xf44 mv r1,r4
0xf46 mv r0,r10
0xf48 bl e00 <pn_address>
0xf4c ld r4,@(8,sp)
0xf50 st r0,@(-44,r4)
0xf54 beqz r0,e70 <pn_native_from_seed+0x30>
0xf58 ld r5,@(4,sp)
0xf5c bne fp,r5,f34 <pn_native_from_seed+0xf4>
0xf60 ld r1,@sp
0xf62 ldi r2,#72
0xf64 mv r0,r10
0xf66 bl e00 <pn_address>
0xf68 add3 r1,r8,#236
0xf6c mv fp,r0
```

pn_native_from_seed，bl，0xf72。
```text
0xf50 st r0,@(-44,r4)
0xf54 beqz r0,e70 <pn_native_from_seed+0x30>
0xf58 ld r5,@(4,sp)
0xf5c bne fp,r5,f34 <pn_native_from_seed+0xf4>
0xf60 ld r1,@sp
0xf62 ldi r2,#72
0xf64 mv r0,r10
0xf66 bl e00 <pn_address>
0xf68 add3 r1,r8,#236
0xf6c mv fp,r0
0xf6e ldi r2,#44
0xf70 mv r0,r10
0xf72 bl e00 <pn_address>
0xf74 mv r9,r0
0xf78 beqz fp,e70 <pn_native_from_seed+0x30>
```

transfer，bl，0x1534。
```text
0x1510 ldi r1,#64
0x1512 st r2,@sp
0x1514 bl 128 <ig_zero>
0x1518 ld24 r4,10040 <n+0x1040>
0x151c ld r2,@sp
0x151e st r4,@r11
0x1520 mv r1,fp
0x1524 ld r4,@(12,r9)
0x1528 st r2,@(12,r11)
0x152c ld r0,@r9
0x152e mv r2,r10
0x1530 st r4,@(8,r11)
0x1534 bl e00 <pn_address>
0x1538 st r0,@(32,r11)
0x153c st r10,@(36,r11)
```

ui_call.constprop.0，bl，0x3e00。
```text
0x3dd8 mv fp,r2
0x3dda add r8,r12
0x3ddc ld r2,@(12,r0)
0x3de0 mv r11,r1
0x3de2 mv r1,r8
0x3de4 mv r9,r3
0x3de8 bl fbc <pn_request>
0x3dec ld r5,@(36,sp)
0x3df0 mv r2,r9
0x3df4 ld r0,@(428,r10)
0x3df8 st r5,@(44,r8)
0x3dfc mv r1,fp
0x3e00 bl e00 <pn_address>
0x3e04 st r0,@(48,r8)
0x3e08 st r9,@(52,r8)
```

pn_ui_render.constprop.0，bl，0x4030。
```text
0x4004 sll3 r2,fp,#3
0x4008 add r2,fp
0x400a add r2,r8
0x400c add r2,r5
0x4010 ldb r3,@(584,r2)
0x4014 bnez r3,3f88 <pn_ui_render.constprop.0+0x144>
0x4018 ld r0,@(428,r8)
0x401c add3 r2,r5,#1
0x4020 add3 r1,r10,#584
0x4024 st r3,@(24,sp)
0x4028 st r7,@(28,sp)
0x402c st r5,@(20,sp)
0x4030 bl e00 <pn_address>
0x4034 ld r5,@(20,sp)
0x4038 st r0,@(1324,r8)
```

pn_ui_render.constprop.0，bl，0x4054。
```text
0x4024 st r3,@(24,sp)
0x4028 st r7,@(28,sp)
0x402c st r5,@(20,sp)
0x4030 bl e00 <pn_address>
0x4034 ld r5,@(20,sp)
0x4038 st r0,@(1324,r8)
0x403c ld r0,@(428,r8)
0x4040 st r5,@(1328,r8)
0x4044 ld r1,@(4,sp)
0x4048 ldi r2,#18
0x404c ld r5,@(12,r0)
0x4050 st r5,@(1332,r8)
0x4054 bl e00 <pn_address>
0x4058 ld r4,@(12,sp)
0x405c st r0,@(1336,r8)
```

pn_ui_render.constprop.0，bl，0x413c。
```text
0x410e jl r4
0x4110 bnez r0,3e94 <pn_ui_render.constprop.0+0x50>
0x4114 ldub r4,@(562,r8)
0x4118 bnez r4,3e90 <pn_ui_render.constprop.0+0x4c>
0x411c st r4,@(1232,r8)
0x4120 ld r0,@(428,r8)
0x4124 ld24 r5,10028 <n+0x1028>
0x4128 ld r4,@(568,r8)
0x412c add3 r1,r11,#904
0x4130 st r5,@(1228,r8)
0x4134 st r4,@(1236,r8)
0x4138 ldi r2,#32
0x413c bl e00 <pn_address>
0x4140 st r0,@(1240,r8)
0x4144 ld r0,@(428,r8)
```

pn_ui_render.constprop.0，bl，0x4168。
```text
0x4138 ldi r2,#32
0x413c bl e00 <pn_address>
0x4140 st r0,@(1240,r8)
0x4144 ld r0,@(428,r8)
0x4148 add3 r1,r11,#1140
0x414c ldi r4,#32
0x4150 st r4,@(1244,r8)
0x4154 ldi r4,#11
0x4158 st r4,@(1248,r8)
0x415c ldub r4,@(553,r8)
0x4160 ldi r2,#44
0x4164 st r4,@(1252,r8)
0x4168 bl e00 <pn_address>
0x416c st r0,@(1256,r8)
0x4170 ld r0,@(428,r8)
```

pn_ui_render.constprop.0，bl，0x417c。
```text
0x414c ldi r4,#32
0x4150 st r4,@(1244,r8)
0x4154 ldi r4,#11
0x4158 st r4,@(1248,r8)
0x415c ldub r4,@(553,r8)
0x4160 ldi r2,#44
0x4164 st r4,@(1252,r8)
0x4168 bl e00 <pn_address>
0x416c st r0,@(1256,r8)
0x4170 ld r0,@(428,r8)
0x4174 ldi r2,#132
0x4178 add3 r1,r11,#1008
0x417c bl e00 <pn_address>
0x4180 ld r4,@(428,r8)
0x4184 st r0,@(1260,r8)
```


pn_call

workspace_close，bl，0x1182。
```text
0x1160 mv r1,r10
0x1162 ldi r11,#1
0x1164 stb r11,@(2077,r8)
0x1168 bl fbc <pn_request>
0x116c seth r4,#0x1
0x1170 add3 r4,r4,#-7544
0x1174 add3 r0,r9,#380
0x1178 add r4,r12
0x117a st r4,@sp
0x117c mv r3,r10
0x117e ldi r2,#2
0x1180 ldi r1,#2
0x1182 bl 101c <pn_call>
0x1184 bnez r0,1198 <workspace_close+0xa0>
0x1188 add3 r0,r9,#2092
```

rpc.lto_priv.1，bl，0x1328。
```text
0x130c add3 r12,r12,#-4616
0x1310 add r12,lr
0x1312 addi sp,#-4
0x1314 ld lr,@(4,sp)
0x1318 st r3,@sp
0x131a mv r9,r0
0x131c ld r0,@r0
0x131e mv r8,r1
0x1320 mv r10,r3
0x1322 mv r3,r2
0x1324 mv r2,r1
0x1326 ldi r1,#1
0x1328 bl 101c <pn_call>
0x132c add3 r4,r0,#8
0x1330 bnez r4,1358 <rpc.lto_priv.1+0x5c>
```

list_bind，bl，0x2184。
```text
0x215c st r4,@(48,r9)
0x2160 ldi r4,#40
0x2164 st r4,@(52,r9)
0x2168 bl 4e0 <ig_bx_receipt>
0x216c seth r4,#0x1
0x2170 add3 r4,r4,#-7640
0x2174 add3 r0,r8,#380
0x2178 add r4,r12
0x217a mv r3,r9
0x217c ldi r2,#1
0x217e st r4,@sp
0x2180 ldi r1,#10
0x2184 bl 101c <pn_call>
0x2188 mv r9,r0
0x218c ldi r2,#26
```

list_bind，bl，0x226c。
```text
0x2248 mv r2,r10
0x224a ldi r1,#16
0x224c ldi r0,#3
0x2250 bl 208 <ig_bx_event>
0x2254 seth r2,#0x1
0x2258 add3 r2,r2,#-7640
0x225c add3 r0,r8,#380
0x2260 add r2,r12
0x2262 st r2,@sp
0x2264 mv r3,fp
0x2266 ldi r2,#2
0x2268 ldi r1,#11
0x226c bl 101c <pn_call>
0x2270 ld r7,@(64,sp)
0x2274 mv r3,r0
```

list_bind，bl，0x22dc。
```text
0x22ba mv r2,r10
0x22bc ldi r3,#0
0x22be ldi r1,#17
0x22c0 ldi r0,#3
0x22c4 bl 208 <ig_bx_event>
0x22c8 ld r5,@(52,sp)
0x22cc add3 r0,r8,#380
0x22d0 ld r3,@(60,sp)
0x22d4 st r5,@sp
0x22d6 ldi r2,#1
0x22d8 add r3,r12
0x22da ldi r1,#11
0x22dc bl 101c <pn_call>
0x22e0 ld r4,@(68,sp)
0x22e4 add3 r5,r11,#70
```

ui_call.constprop.0，bl，0x3e28。
```text
0x3e00 bl e00 <pn_address>
0x3e04 st r0,@(48,r8)
0x3e08 st r9,@(52,r8)
0x3e0c beqz r0,3e40 <ui_call.constprop.0+0xa4>
0x3e10 ld r0,@(428,r10)
0x3e14 seth r4,#0x1
0x3e18 add3 r4,r4,#-10184
0x3e1c ld r1,@(4,sp)
0x3e20 add r4,r12
0x3e22 st r4,@sp
0x3e24 mv r3,r8
0x3e26 mv r2,r11
0x3e28 bl 101c <pn_call>
0x3e2c addi sp,#8
0x3e2e pop lr
```

pn_ui_render.constprop.0，bl，0x3f68。
```text
0x3f44 add r10,r12
0x3f46 mv r1,r10
0x3f48 ld r2,@(12,r0)
0x3f4c bl fbc <pn_request>
0x3f50 ld r0,@(428,r8)
0x3f54 seth r4,#0x1
0x3f58 add3 r4,r4,#-10184
0x3f5c add r4,r12
0x3f5e st r4,@sp
0x3f60 mv r3,r10
0x3f62 ldi r2,#2
0x3f64 ldi r1,#11
0x3f68 bl 101c <pn_call>
0x3f6c seth r4,#0x1
0x3f70 add3 r4,r4,#-10184
```


pn_native_from_seed

地址引用：{"pc": "0x8464", "kind": "encoded GOTOFF function address", "target": "pn_native_from_seed", "owner": "ig_panel_open"}

pn_request

workspace_close，bl，0x1168。
```text
0x1140 ldub r4,@(2077,r8)
0x1144 bnez r4,11a0 <workspace_close+0xa8>
0x1148 seth r10,#0x1
0x114c add3 r10,r10,#-7512
0x1150 seth r9,#0x1
0x1154 add3 r9,r9,#-4352
0x1158 add r10,r12
0x115a add r9,r12
0x115c add3 r0,r9,#380
0x1160 mv r1,r10
0x1162 ldi r11,#1
0x1164 stb r11,@(2077,r8)
0x1168 bl fbc <pn_request>
0x116c seth r4,#0x1
0x1170 add3 r4,r4,#-7544
```

list_bind，bl，0x213c。
```text
0x210c add3 r6,r4,#32
0x2110 st r6,@(4,r4)
0x2114 ld r4,@(3660,r8)
0x2118 ld r6,@(3676,r8)
0x211c st r6,@(92,r4)
0x2120 ld r4,@(3660,r8)
0x2124 ldi r6,#0
0x2128 stb r2,@(96,r4)
0x212c ld r4,@(3660,r8)
0x2130 st r6,@(100,r4)
0x2134 ld r2,@(392,r8)
0x2138 st r5,@(64,sp)
0x213c bl fbc <pn_request>
0x2140 ld r5,@(64,sp)
0x2144 ldi r2,#26
```

list_bind，bl，0x2238。
```text
0x220c add r8,r12
0x2210 add3 r0,r8,#380
0x2214 st r3,@(12,sp)
0x2218 ld r2,@r6
0x221a add fp,r12
0x221c ldi r6,#70
0x2220 st r6,@(32,sp)
0x2224 st r2,@(8,sp)
0x2228 ld r2,@(392,r8)
0x222c mv r1,fp
0x2230 st r2,@(24,sp)
0x2234 st r2,@(36,sp)
0x2238 bl fbc <pn_request>
0x223c ldi r2,#0
0x2240 st r2,@(4,sp)
```

ui_call.constprop.0，bl，0x3de8。
```text
0x3dc4 add r12,lr
0x3dc6 addi sp,#-8
0x3dc8 st r0,@(4,sp)
0x3dcc ld lr,@(8,sp)
0x3dd0 add r10,r12
0x3dd4 ld r0,@(428,r10)
0x3dd8 mv fp,r2
0x3dda add r8,r12
0x3ddc ld r2,@(12,r0)
0x3de0 mv r11,r1
0x3de2 mv r1,r8
0x3de4 mv r9,r3
0x3de8 bl fbc <pn_request>
0x3dec ld r5,@(36,sp)
0x3df0 mv r2,r9
```

pn_ui_render.constprop.0，bl，0x3f4c。
```text
0x3f28 add3 r0,r0,#584
0x3f2c ldi r2,#9
0x3f2e add r1,r12
0x3f30 bl 13c <ig_copy>
0x3f34 seth r10,#0x1
0x3f38 add3 r10,r10,#-10152
0x3f3c mv r8,r9
0x3f3e add r8,r12
0x3f40 ld r0,@(428,r8)
0x3f44 add r10,r12
0x3f46 mv r1,r10
0x3f48 ld r2,@(12,r0)
0x3f4c bl fbc <pn_request>
0x3f50 ld r0,@(428,r8)
0x3f54 seth r4,#0x1
```


pn_ui_render.constprop.0

a4_move，bl，0x4348。
```text
0x4324 cmp r6,r5
0x4326 bnc 4334 <a4_move+0x6c>
0x4328 ldb r6,@(1511,r4)
0x432c add3 r5,r0,#-5
0x4330 cmp r6,r5
0x4332 bnc 436c <a4_move+0xa4>
0x4334 add r10,r12
0x4336 add fp,r10
0x4338 ldub r4,@(511,fp)
0x433c addi r4,#5
0x4340 stb r4,@(553,r10)
0x4344 ldi r0,#0
0x4348 bl 3e44 <pn_ui_render.constprop.0>
0x434c bnez r0,4368 <a4_move+0xa0>
0x4350 ldi r0,#1
```

ig_panel_open，bl，0x83b8。
```text
0x838c ldub r4,@(549,r9)
0x8390 ldi r0,#0
0x8394 add3 r5,r4,#1
0x8398 ldi r4,#3
0x839a and r4,r5
0x839c stb r4,@(549,r9)
0x83a0 add r4,r9
0x83a4 ldub r4,@(519,r4)
0x83a8 add r4,r9
0x83ac ldub r4,@(511,r4)
0x83b0 addi r4,#5
0x83b4 stb r4,@(553,r9)
0x83b8 bl 3e44 <pn_ui_render.constprop.0>
0x83bc beqz r0,85e4 <ig_panel_open+0x2b4>
0x83c0 ldi r1,#3
```

ig_panel_open，bl，0x85d4。
```text
0x85b0 ldi r2,#1
0x85b2 cmpu r2,r7
0x85b4 bc 83c0 <ig_panel_open+0x90>
0x85b8 st r5,@(1300,r8)
0x85bc st r6,@(1304,r8)
0x85c0 slli r4,#0x3
0x85c2 add r4,r5
0x85c4 ldub r5,@r4
0x85c6 ldi r0,#1
0x85c8 st r5,@(1308,r8)
0x85cc ld r4,@(4,r4)
0x85d0 st r4,@(1312,r8)
0x85d4 bl 3e44 <pn_ui_render.constprop.0>
0x85d8 bnez r0,83c0 <ig_panel_open+0x90>
0x85dc ldi r4,#257
```


read_exact

rv_call，bl，0x92c0。
```text
0x9294 ld r4,@(352,r9)
0x9298 not r5,r3
0x929c bne r5,r4,91c0 <rv_call+0x980>
0x92a0 bra 91c4 <rv_call+0x984>
0x92a4 ldi r5,#128
0x92a8 cmpu r5,r10
0x92aa mv r8,r10
0x92ac bnc 92b4 <rv_call+0xa74>
0x92b0 ldi r8,#128
0x92b4 ld r1,@(32,sp)
0x92b8 mv r2,r8
0x92bc ld r0,@(36,sp)
0x92c0 bl 6be4 <read_exact>
0x92c4 bnez r0,91c0 <rv_call+0x980>
0x92c8 ld r1,@(40,sp)
```

rv_call，bl，0x92d4。
```text
0x92a8 cmpu r5,r10
0x92aa mv r8,r10
0x92ac bnc 92b4 <rv_call+0xa74>
0x92b0 ldi r8,#128
0x92b4 ld r1,@(32,sp)
0x92b8 mv r2,r8
0x92bc ld r0,@(36,sp)
0x92c0 bl 6be4 <read_exact>
0x92c4 bnez r0,91c0 <rv_call+0x980>
0x92c8 ld r1,@(40,sp)
0x92cc mv r2,r8
0x92d0 ld r0,@(28,sp)
0x92d4 bl 6be4 <read_exact>
0x92d8 bnez r0,91c0 <rv_call+0x980>
0x92dc ld r1,@(40,sp)
```


remember_load

地址引用：{"pc": "0x7574", "kind": "encoded GOTOFF function address", "target": "remember_load", "owner": "ig_init"}

remove_owned

io_remove，bl，0x1ae4。
```text
0x1ab8 ld r0,@r0
0x1abc beqz r5,1b00 <io_remove+0xb0>
0x1ac0 bnez r3,1b00 <io_remove+0xb0>
0x1ac4 ldub r5,@(369,r8)
0x1ac8 srl r5,r4
0x1aca ldi r4,#1
0x1acc and r4,r5
0x1ad0 beqz r4,1b00 <io_remove+0xb0>
0x1ad4 beqz r0,1b18 <io_remove+0xc8>
0x1ad8 ldub r4,@(21,r0)
0x1adc bnez r4,1b1c <io_remove+0xcc>
0x1ae0 mv r1,sp
0x1ae4 bl 15e0 <remove_owned>
0x1ae8 mv r1,r0
0x1aec mv r0,r8
```


rpc.lto_priv.0

expect，bl，0x4780。
```text
0x4764 push r8
0x4766 push r12
0x4768 push lr
0x476a bl 476c <expect+0x8>
0x476c seth r12,#0x0
0x4770 add3 r12,r12,#-18028
0x4774 add r12,lr
0x4776 addi sp,#-4
0x4778 ld lr,@(4,sp)
0x477c mv r8,r2
0x477e mv r2,sp
0x4780 bl 46cc <rpc.lto_priv.0>
0x4784 beqz r0,4798 <expect+0x34>
0x4788 ld r0,@sp
```

t_read，bl，0x48d4。
```text
0x48b2 pop lr
0x48b4 pop r12
0x48b6 pop r8
0x48b8 jmp lr
0x48bc ld r4,@(44,r8)
0x48c0 mv r2,sp
0x48c2 ldi r0,#2
0x48c4 ldub r1,@(30,r4)
0x48c8 ldub r4,@(31,r4)
0x48cc slli r1,#0x8
0x48ce add r1,r4
0x48d0 and3 r1,r1,#0xffff
0x48d4 bl 46cc <rpc.lto_priv.0>
0x48d8 beqz r0,4898 <t_read+0x48>
0x48dc ld r6,@sp
```

eng_apply，bl，0x5284。
```text
0x525c ldi r6,#1
0x5260 stb r6,@(2471,r5)
0x5264 bra 5278 <eng_apply+0x928>
0x5268 mv r6,r8
0x526a add r6,r12
0x526c ldi r7,#1
0x5270 stb r7,@(2469,r6)
0x5274 beqz r5,5258 <eng_apply+0x908>
0x5278 add3 r10,sp,#12
0x527c mv r2,r10
0x527e ldi r1,#0
0x5280 ldi r0,#1
0x5284 bl 46cc <rpc.lto_priv.0>
0x5288 bnez r0,529c <eng_apply+0x94c>
0x528c bl a30 <failure>
```

eng_apply，bl，0x5338。
```text
0x5310 bl 944 <b32>
0x5314 srl3 r2,r0,#16
0x5318 mv r5,r0
0x531c st r5,@(80,sp)
0x5320 mv r1,r2
0x5322 ldi r0,#4
0x5324 bl 4764 <expect>
0x5328 ld r5,@(80,sp)
0x532c beqz r0,577c <eng_apply+0xe2c>
0x5330 and3 r1,r5,#0xffff
0x5334 mv r2,r10
0x5336 ldi r0,#2
0x5338 bl 46cc <rpc.lto_priv.0>
0x533c beqz r0,577c <eng_apply+0xe2c>
0x5340 ld r5,@(12,sp)
```

eng_apply，bl，0x5490。
```text
0x5460 bl 48e8 <end>
0x5464 beqz r0,528c <eng_apply+0x93c>
0x5468 beqz r11,528c <eng_apply+0x93c>
0x546c bl 45a8 <fresh>
0x5470 bnez r0,5560 <eng_apply+0xc10>
0x5474 bl a30 <failure>
0x5478 mv r8,r0
0x547c bra 510c <eng_apply+0x7bc>
0x5480 add3 r2,sp,#12
0x5484 and3 r1,r5,#0xfffe
0x5488 st r6,@(76,sp)
0x548c ldi r0,#2
0x5490 bl 46cc <rpc.lto_priv.0>
0x5494 ld r6,@(76,sp)
0x5498 beqz r0,545c <eng_apply+0xb0c>
```


rpc.lto_priv.1

open_read，bl，0x140e。
```text
0x13e8 ldi r4,#0
0x13ec st r4,@(48,r8)
0x13f0 seth r8,#0x1
0x13f4 add3 r8,r8,#-9332
0x13f8 add r8,r12
0x13fc seth r11,#0x1
0x1400 add3 r11,r11,#-9364
0x1404 add r11,r12
0x1406 mv r3,r11
0x1408 mv r2,r8
0x140a ldi r1,#2
0x140c mv r0,r9
0x140e bl 12fc <rpc.lto_priv.1>
0x1410 add3 r4,r0,#-2
0x1414 bnez r4,1430 <open_read+0xb0>
```

close_once，bl，0x14ae。
```text
0x1484 bl 128 <ig_zero>
0x1488 ld24 r4,10040 <n+0x1040>
0x148c seth r3,#0x1
0x1490 add3 r3,r3,#-9460
0x1494 st r4,@r8
0x1498 ld r4,@(12,r9)
0x149c st r10,@(12,r8)
0x14a0 add r3,r12
0x14a4 st r4,@(8,r8)
0x14a8 mv r2,r8
0x14aa ldi r1,#6
0x14ac mv r0,r9
0x14ae bl 12fc <rpc.lto_priv.1>
0x14b0 beqz r0,14c8 <close_once+0x74>
0x14b4 ldi r4,#1
```

transfer，bl，0x1554。
```text
0x152e mv r2,r10
0x1530 st r4,@(8,r11)
0x1534 bl e00 <pn_address>
0x1538 st r0,@(32,r11)
0x153c st r10,@(36,r11)
0x1540 beqz r0,15d8 <transfer+0x104>
0x1544 seth r3,#0x1
0x1548 add3 r3,r3,#-9556
0x154c add r3,r12
0x154e mv r2,r11
0x1550 mv r1,r8
0x1552 mv r0,r9
0x1554 bl 12fc <rpc.lto_priv.1>
0x1558 seth r4,#0x1
0x155c add3 r4,r4,#-9556
```

remove_owned，bl，0x1688。
```text
0x165e mv r2,r11
0x1660 st r4,@(8,r11)
0x1664 ldub r4,@r8
0x1666 ldi r1,#8
0x1668 mv r0,fp
0x166c st r4,@(16,r11)
0x1670 ldub r4,@(1,r8)
0x1674 st r4,@(20,r11)
0x1678 ldub r4,@(2,r8)
0x167c st r10,@(28,r11)
0x1680 st r9,@(48,r11)
0x1684 st r4,@(24,r11)
0x1688 bl 12fc <rpc.lto_priv.1>
0x168c addi sp,#4
0x168e pop lr
```

io_open，bl，0x1814。
```text
0x17ec st r5,@(20,r10)
0x17f0 st r4,@(48,r10)
0x17f4 ldi r4,#240
0x17f8 st r4,@(40,r10)
0x17fc add r11,r12
0x17fe ldi r6,#2
0x1800 st r6,@(16,r10)
0x1804 ldi r5,#4
0x1808 st r5,@(28,r10)
0x180c mv r3,r11
0x180e mv r2,r10
0x1810 mv r0,fp
0x1814 bl 12fc <rpc.lto_priv.1>
0x1818 mv r1,r0
0x181c bnez r0,183c <io_open+0x16c>
```

io_rename，bl，0x1c1c。
```text
0x1bf8 st r7,@(8,r8)
0x1bfc ld r6,@sp
0x1bfe ldi r7,#2
0x1c00 st r7,@(16,r8)
0x1c04 st r10,@(44,r8)
0x1c08 st r6,@(48,r8)
0x1c0c ldi r5,#4
0x1c10 st r5,@(28,r8)
0x1c14 ldi r1,#7
0x1c16 add r3,r12
0x1c18 mv r2,r8
0x1c1a mv r0,r11
0x1c1c bl 12fc <rpc.lto_priv.1>
0x1c20 ld r4,@(8,sp)
0x1c24 mv r1,r0
```


rt_tone.constprop.0

eng_apply，bl，0x4bb4。
```text
0x4b8a add r10,r12
0x4b8c add3 r1,r10,#1994
0x4b90 add3 r0,r10,#1932
0x4b94 add r4,r12
0x4b98 ld r11,@(8,r4)
0x4b9c ld fp,@(12,r4)
0x4ba0 mv r3,r11
0x4ba2 ld r6,@r4
0x4ba4 st r1,@(4,sp)
0x4ba8 st fp,@sp
0x4bac st r6,@(24,sp)
0x4bb0 mv r2,r6
0x4bb4 bl 3bf0 <rt_tone.constprop.0>
0x4bb8 bltz r0,4a10 <eng_apply+0xc0>
0x4bbc ld r2,@(24,sp)
```

eng_apply，bl，0x4bd0。
```text
0x4ba4 st r1,@(4,sp)
0x4ba8 st fp,@sp
0x4bac st r6,@(24,sp)
0x4bb0 mv r2,r6
0x4bb4 bl 3bf0 <rt_tone.constprop.0>
0x4bb8 bltz r0,4a10 <eng_apply+0xc0>
0x4bbc ld r2,@(24,sp)
0x4bc0 add3 r1,r10,#2430
0x4bc4 st r1,@(4,sp)
0x4bc8 add3 r0,r10,#2368
0x4bcc st fp,@sp
0x4bce mv r3,r11
0x4bd0 bl 3bf0 <rt_tone.constprop.0>
0x4bd4 bltz r0,4a10 <eng_apply+0xc0>
0x4bd8 ldub r6,@(1,r9)
```

eng_apply，bl，0x4c08。
```text
0x4be4 ldub r5,@(1,r9)
0x4be8 ldi r4,#16
0x4bea and r4,r5
0x4bec beqz r4,4c10 <eng_apply+0x2c0>
0x4bf0 ld r2,@(24,sp)
0x4bf4 mv r0,r8
0x4bf6 add r0,r12
0x4bf8 add3 r1,r0,#2258
0x4bfc st r1,@(4,sp)
0x4c00 add3 r0,r0,#2196
0x4c04 st fp,@sp
0x4c06 mv r3,r11
0x4c08 bl 3bf0 <rt_tone.constprop.0>
0x4c0c bltz r0,4a10 <eng_apply+0xc0>
0x4c10 ld r4,@(32,sp)
```

eng_apply，bl，0x5164。
```text
0x513a ldi r0,#6
0x513c bl 43c0 <svc.constprop.0>
0x5140 beqz r0,5644 <eng_apply+0xcf4>
0x5144 bnez r8,4a14 <eng_apply+0xc4>
0x5148 bl 9bc <mapped>
0x514c bra 5640 <eng_apply+0xcf0>
0x5150 ld r2,@(24,sp)
0x5154 add3 r1,r10,#2291
0x5158 st r1,@(4,sp)
0x515c add3 r0,r10,#1932
0x5160 st fp,@sp
0x5162 mv r3,r11
0x5164 bl 3bf0 <rt_tone.constprop.0>
0x5168 bltz r0,4a10 <eng_apply+0xc0>
0x516c ld r2,@(24,sp)
```

eng_apply，bl，0x5180。
```text
0x5158 st r1,@(4,sp)
0x515c add3 r0,r10,#1932
0x5160 st fp,@sp
0x5162 mv r3,r11
0x5164 bl 3bf0 <rt_tone.constprop.0>
0x5168 bltz r0,4a10 <eng_apply+0xc0>
0x516c ld r2,@(24,sp)
0x5170 add3 r1,r10,#2324
0x5174 st r1,@(4,sp)
0x5178 add3 r0,r10,#1932
0x517c st fp,@sp
0x517e mv r3,r11
0x5180 bl 3bf0 <rt_tone.constprop.0>
0x5184 bgez r0,4be4 <eng_apply+0x294>
0x5188 bra 4a10 <eng_apply+0xc0>
```


rv_call


rv_unit.constprop.0

ingress，bl，0x7278。
```text
0x724c bl 39e8 <es_range.constprop.0>
0x7250 beqz r0,7294 <ingress+0x2e4>
0x7254 ld fp,@(72,r10)
0x7258 mv r0,r11
0x725c ld r1,@(64,r10)
0x7260 mv r2,fp
0x7264 bl 39e8 <es_range.constprop.0>
0x7268 beqz r0,7294 <ingress+0x2e4>
0x726c ld r4,@(68,r10)
0x7270 cmpu fp,r4
0x7272 bc 7294 <ingress+0x2e4>
0x7274 mv r0,sp
0x7278 bl 6ef0 <rv_unit.constprop.0>
0x727c bnez r0,7294 <ingress+0x2e4>
0x7280 seth r1,#0x2005
```

identity.constprop.0，bl，0x87a4。
```text
0x8782 mv r9,r0
0x8784 beqz r4,8798 <identity.constprop.0+0x40>
0x8788 ldi r0,#0
0x878c addi sp,#12
0x878e pop lr
0x8790 pop r12
0x8792 pop r9
0x8794 pop r8
0x8796 jmp lr
0x8798 bl 3898 <es_session.constprop.0>
0x879c beqz r0,8788 <identity.constprop.0+0x30>
0x87a0 mv r0,sp
0x87a4 bl 6ef0 <rv_unit.constprop.0>
0x87a8 bnez r0,8788 <identity.constprop.0+0x30>
0x87ac ld r5,@(8,r9)
```

rv_call，bl，0x9f3c。
```text
0x9f18 addi r10,#1
0x9f1a lduh r6,@r5
0x9f1c addi r5,#4
0x9f1e add r6,r4
0x9f20 stb r7,@r6
0x9f22 bra 9f04 <rv_call+0x16c4>
0x9f24 add3 r5,r11,#-1
0x9f28 bnez r5,97bc <rv_call+0xf7c>
0x9f2c ld r11,@(20,sp)
0x9f30 addi r11,#-36
0x9f34 bnez r11,97bc <rv_call+0xf7c>
0x9f38 mv r0,sp
0x9f3c bl 6ef0 <rv_unit.constprop.0>
0x9f40 mv r10,r0
0x9f44 mv r0,fp
```


same.constprop.0

rv_call，bl，0x918c。
```text
0x9160 or3 r1,r1,#0x4708
0x9164 st r7,@(16,sp)
0x9168 st r3,@(20,sp)
0x916c ldi r2,#48
0x916e mv r0,r7
0x9170 bl 1e60 <es_memcpy>
0x9174 ld r0,@(20,sp)
0x9178 add3 r1,r9,#440
0x917c ldi r2,#16
0x9180 bl 1e60 <es_memcpy>
0x9184 ld r1,@(20,sp)
0x9188 ld r0,@(16,sp)
0x918c bl 6c84 <same.constprop.0>
0x9190 beqz r0,8ce8 <rv_call+0x4a8>
0x9194 seth r0,#0x1
```

rv_call，bl，0x91f0。
```text
0x91c0 ldi r10,#-6
0x91c4 ld r0,@(36,sp)
0x91c8 bl aec8 <rv_native_close>
0x91cc bnez r0,9320 <rv_call+0xae0>
0x91d0 ld r4,@(28,sp)
0x91d4 bltz r4,91e8 <rv_call+0x9a8>
0x91d8 mv r0,r4
0x91dc bl aec8 <rv_native_close>
0x91e0 beqz r0,91e8 <rv_call+0x9a8>
0x91e4 ldi r10,#-1
0x91e8 ld r1,@(20,sp)
0x91ec ld r0,@(16,sp)
0x91f0 bl 6c84 <same.constprop.0>
0x91f4 beqz r0,8ce8 <rv_call+0x4a8>
0x91f8 bnez r10,8998 <rv_call+0x158>
```

rv_call，bl，0x9310。
```text
0x92e0 mv r2,r8
0x92e4 ld r0,@(32,sp)
0x92e8 bl 1e34 <es_equal>
0x92ec beqz r0,91c0 <rv_call+0x980>
0x92f0 ld r1,@(32,sp)
0x92f4 mv r2,r8
0x92f8 ld r0,@(44,sp)
0x92fc sub r10,r8
0x9300 bl 2320 <gxr2_crc_add>
0x9304 st r0,@(44,sp)
0x9308 ld r1,@(20,sp)
0x930c ld r0,@(16,sp)
0x9310 bl 6c84 <same.constprop.0>
0x9314 bnez r0,9260 <rv_call+0xa20>
0x9318 ldi r10,#-5
```

rv_call，bl，0x932c。
```text
0x9308 ld r1,@(20,sp)
0x930c ld r0,@(16,sp)
0x9310 bl 6c84 <same.constprop.0>
0x9314 bnez r0,9260 <rv_call+0xa20>
0x9318 ldi r10,#-5
0x931a bra 91c4 <rv_call+0x984>
0x931c ldi r10,#-6
0x931e bra 91d0 <rv_call+0x990>
0x9320 ldi r10,#-1
0x9322 bra 91d0 <rv_call+0x990>
0x9324 ld r1,@(20,sp)
0x9328 ld r0,@(16,sp)
0x932c bl 6c84 <same.constprop.0>
0x9330 bnez r0,8960 <rv_call+0x120>
0x9334 bra 8ce8 <rv_call+0x4a8>
```


sd_current.constprop.0

rv_call，bl，0x8a3c。
```text
0x8a10 bc 8aa8 <rv_call+0x268>
0x8a14 beqz r9,8a48 <rv_call+0x208>
0x8a18 add3 r5,r10,#126
0x8a1c slli r5,#0x2
0x8a1e add r5,r8
0x8a20 ldub r5,@r5
0x8a24 st r5,@(16,sp)
0x8a28 ld r5,@(16,sp)
0x8a2c addi r5,#-1
0x8a30 bnez r5,8a48 <rv_call+0x208>
0x8a34 st r4,@(48,sp)
0x8a38 mv r0,r8
0x8a3c bl 6d10 <sd_current.constprop.0>
0x8a40 ld r4,@(48,sp)
0x8a44 beqz r0,8ce8 <rv_call+0x4a8>
```

rv_call，bl，0x8ce0。
```text
0x8cb4 seth r7,#0x100
0x8cb8 or3 r7,r7,#0x1
0x8cbc slli r5,#0x6
0x8cc0 ld r2,@(212,r5)
0x8cc4 bne r4,r7,8d18 <rv_call+0x4d8>
0x8cc8 ldi r4,#64
0x8cca or r4,r2
0x8ccc st r4,@(212,r5)
0x8cd0 beqz r6,8b6c <rv_call+0x32c>
0x8cd4 ldi r10,#-1
0x8cd8 bra 8998 <rv_call+0x158>
0x8cdc mv r0,r8
0x8ce0 bl 6d10 <sd_current.constprop.0>
0x8ce4 bnez r0,8ca4 <rv_call+0x464>
0x8ce8 ldi r10,#-5
```

rv_call，bl，0x8fa0。
```text
0x8f70 bl 3898 <es_session.constprop.0>
0x8f74 beqz r0,8ce8 <rv_call+0x4a8>
0x8f78 ld24 r5,80151c <n+0x7f251c>
0x8f7c ld r7,@(8,fp)
0x8f80 slli r5,#0x6
0x8f84 ld r6,@(52,r5)
0x8f88 bne r7,r6,8ce8 <rv_call+0x4a8>
0x8f8c ld r6,@(16,fp)
0x8f90 addi r6,#-1
0x8f94 bnez r6,a958 <rv_call+0x2118>
0x8f98 st r5,@(60,sp)
0x8f9c mv r0,r8
0x8fa0 bl 6d10 <sd_current.constprop.0>
0x8fa4 ld r5,@(60,sp)
0x8fa8 beqz r0,8ce8 <rv_call+0x4a8>
```

rv_call，bl，0x9380。
```text
0x9354 ld r6,@(44,fp)
0x9358 bnez r6,8ad0 <rv_call+0x290>
0x935c ldi r6,#-5
0x935e and r6,r5
0x9360 addi r6,#-1
0x9364 beqz r6,8ad0 <rv_call+0x290>
0x9368 ld r6,@(48,fp)
0x936c beq r5,r6,8ad0 <rv_call+0x290>
0x9370 mv r0,r9
0x9374 bl aef8 <rv_native_delete>
0x9378 bra a9cc <rv_call+0x218c>
0x937c mv r0,r8
0x9380 bl 6d10 <sd_current.constprop.0>
0x9384 bnez r0,a9e4 <rv_call+0x21a4>
0x9388 bra 8ce8 <rv_call+0x4a8>
```


select_cached

ig_event，bl，0x82b0。
```text
0x8284 bnez r4,830c <ig_event+0x238>
0x8288 ld r5,@(56,r8)
0x828c seth r4,#0x202c
0x8290 or3 r4,r4,#0x2d74
0x8294 beq r5,r4,82a4 <ig_event+0x1d0>
0x8298 seth r4,#0x202c
0x829c or3 r4,r4,#0x2d84
0x82a0 bne r5,r4,830c <ig_event+0x238>
0x82a4 seth r4,#0x2022
0x82a8 or3 r4,r4,#0xf726
0x82ac ldub fp,@r4
0x82ae mv r0,fp
0x82b0 bl 5784 <select_cached>
0x82b4 seth r4,#0x1
0x82b8 add3 r4,r4,#-8748
```

ig_panel_open，bl，0x8440。
```text
0x8422 pop lr
0x8424 pop r12
0x8426 pop r11
0x8428 pop r10
0x842a pop r9
0x842c pop r8
0x842e pop fp
0x8430 jmp lr
0x8434 bl a74 <eng_visible_rows>
0x8438 cmpu r0,r11
0x843c bc 83e0 <ig_panel_open+0xb0>
0x843e mv r0,r11
0x8440 bl 5784 <select_cached>
0x8444 bnez r0,83e0 <ig_panel_open+0xb0>
0x8448 ldub r4,@(550,r8)
```


slot_descriptor

gxr2_parameter，bl，0xd48。
```text
0xd2a push r12
0xd2c push lr
0xd2e bl d30 <gxr2_parameter+0x10>
0xd30 seth r12,#0x0
0xd34 add3 r12,r12,#-3120
0xd38 add r12,lr
0xd3a addi sp,#-8
0xd3c ld lr,@(8,sp)
0xd40 mv fp,r3
0xd42 mv r8,r0
0xd44 mv r10,r1
0xd46 mv r11,r2
0xd48 bl cb0 <slot_descriptor>
0xd4c beqz r0,d68 <gxr2_parameter+0x48>
0xd50 ld r5,@(68,r8)
```

gxr2_expand.constprop.0，bl，0x3a84。
```text
0x3a66 push r8
0x3a68 push r9
0x3a6a push r10
0x3a6c push r11
0x3a6e push r12
0x3a70 push lr
0x3a72 bl 3a74 <gxr2_expand.constprop.0+0x10>
0x3a74 seth r12,#0x0
0x3a78 add3 r12,r12,#-14708
0x3a7c add r12,lr
0x3a7e ld lr,@sp
0x3a80 mv r11,r0
0x3a84 bl cb0 <slot_descriptor>
0x3a88 mv r8,r0
0x3a8c beqz r0,3b84 <gxr2_expand.constprop.0+0x120>
```


snapshot

fresh，bl，0x4600。
```text
0x45e0 add r4,r12
0x45e2 ldi r5,#0
0x45e4 stb r5,@(2465,r4)
0x45e8 bl 968 <disarm>
0x45ec ldi r0,#0
0x45f0 addi sp,#28
0x45f2 pop lr
0x45f4 pop r12
0x45f6 pop r8
0x45f8 jmp lr
0x45fc ldi r1,#0
0x45fe mv r0,sp
0x4600 bl 4460 <snapshot>
0x4604 beqz r0,45d8 <fresh+0x30>
0x4608 ld r4,@(156,r8)
```

ig_init，bl，0x76d0。
```text
0x76a8 ldi r1,#2476
0x76ac add r10,r12
0x76ae mv r0,r10
0x76b0 bl 128 <ig_zero>
0x76b4 seth r1,#0x1
0x76b8 add3 r1,r1,#-7684
0x76bc add r1,r12
0x76be ldi r2,#36
0x76c0 mv r0,r10
0x76c4 bl ae94 <memcpy>
0x76c8 add3 r1,sp,#4
0x76cc add3 r0,sp,#40
0x76d0 bl 4460 <snapshot>
0x76d4 bnez r0,76dc <ig_init+0x38c>
0x76d8 ldi r1,#3
```


sticky_put

ig_bx_unit，bl，0x706。
```text
0x6d8 beqz r8,7a4 <ig_bx_unit+0x108>
0x6dc ldub r5,@(2568,r8)
0x6e0 add3 r0,r8,#2560
0x6e4 beqz r5,6f4 <ig_bx_unit+0x58>
0x6e8 ldub r5,@(2569,r8)
0x6ec beqz r5,6f4 <ig_bx_unit+0x58>
0x6f0 bnez r11,7a4 <ig_bx_unit+0x108>
0x6f4 ld r9,@(16,r4)
0x6f8 seth r1,#0x1
0x6fc add3 r1,r1,#-20704
0x700 ld r10,@(8,r4)
0x704 add r1,r12
0x706 bl 654 <sticky_put>
0x708 stb r11,@(2569,r8)
0x70c ld r1,@(332,r9)
```

ig_bx_apply，bl，0x844。
```text
0x81c ld r10,@(8,r10)
0x820 mv r0,r4
0x822 mv r1,r9
0x824 bl 184 <p32>
0x828 ldub r5,@(2696,r8)
0x82c seth r4,#0x1
0x830 add3 r4,r4,#-20692
0x834 bnez r5,8b8 <ig_bx_apply+0x104>
0x838 add3 r0,r8,#2688
0x83c st r4,@(8,sp)
0x840 mv r1,r4
0x842 add r1,r12
0x844 bl 654 <sticky_put>
0x848 add3 r0,r8,#2700
0x84c mv r1,r9
```

ig_bx_apply，bl，0x8c0。
```text
0x894 add3 r0,r8,#2724
0x898 bl 184 <p32>
0x89c ld r1,@(44,sp)
0x8a0 add3 r0,r8,#2728
0x8a4 bl 184 <p32>
0x8a8 ld r1,@(48,sp)
0x8ac add3 r0,r8,#2732
0x8b0 bl 184 <p32>
0x8b4 ld r4,@(8,sp)
0x8b8 add3 r0,r8,#2816
0x8bc mv r1,r4
0x8be add r1,r12
0x8c0 bl 654 <sticky_put>
0x8c4 add3 r0,r8,#2828
0x8c8 mv r1,r9
```


svc.constprop.0

snapshot，bl，0x44c0。
```text
0x44a0 ld24 fp,1003c <n+0x103c>
0x44a4 st fp,@r8
0x44a6 add r4,r12
0x44a8 st r4,@(8,sp)
0x44ac ldi r4,#0
0x44b0 st r4,@(4,sp)
0x44b4 ldi r4,#60
0x44b6 st r4,@sp
0x44b8 mv r3,r8
0x44ba ldi r2,#0
0x44bc ldi r1,#12
0x44be ldi r0,#9
0x44c0 bl 43c0 <svc.constprop.0>
0x44c4 ld r4,@r8
0x44c8 mv r11,r0
```

snapshot，bl，0x4560。
```text
0x453c seth r4,#0x1
0x4540 add3 r4,r4,#-8840
0x4544 st r8,@r10
0x4548 st r11,@(4,sp)
0x454c add r4,r12
0x4550 st r4,@(8,sp)
0x4554 ldi r4,#36
0x4556 st r4,@sp
0x4558 mv r3,r10
0x455a ldi r2,#0
0x455c ldi r1,#1
0x455e ldi r0,#7
0x4560 bl 43c0 <svc.constprop.0>
0x4564 bnez r0,44d0 <snapshot+0x70>
0x4568 ld r4,@r10
```

rpc.lto_priv.0，bl，0x472c。
```text
0x4704 jmp lr
0x4708 seth r4,#0x1
0x470c add3 r4,r4,#-8872
0x4710 add r4,r12
0x4714 st r4,@(8,sp)
0x4718 ldi r4,#0
0x471c st r4,@(4,sp)
0x4720 st r4,@sp
0x4722 ldi r3,#0
0x4724 mv r2,r10
0x4726 mv r1,r8
0x4728 ldi r0,#4
0x472c bl 43c0 <svc.constprop.0>
0x4730 bnez r0,46f4 <rpc.lto_priv.0+0x28>
0x4734 bl 45a8 <fresh>
```

end，bl，0x4924。
```text
0x4900 add r12,lr
0x4902 addi sp,#-12
0x4904 ld lr,@(12,sp)
0x4908 ldi r8,#0
0x490c st r8,@(4,sp)
0x4910 add r4,r12
0x4914 st r4,@(8,sp)
0x4918 st r8,@sp
0x491a ldi r3,#0
0x491c ldi r2,#0
0x491e ldi r1,#5
0x4920 ldi r0,#4
0x4924 bl 43c0 <svc.constprop.0>
0x4928 beqz r0,494c <end+0x64>
0x492c seth r4,#0x1
```

eng_apply，bl，0x4ee4。
```text
0x4ec4 ld24 fp,10018 <n+0x1018>
0x4ec8 st fp,@r10
0x4eca add r4,r12
0x4ecc st r4,@(8,sp)
0x4ed0 ldi r4,#0
0x4ed4 st r4,@(4,sp)
0x4ed8 ldi r4,#24
0x4eda st r4,@sp
0x4edc mv r3,r10
0x4ede ldi r2,#0
0x4ee0 ldi r1,#1
0x4ee2 ldi r0,#6
0x4ee4 bl 43c0 <svc.constprop.0>
0x4ee8 bl 9bc <mapped>
0x4eec mv r9,r0
```

eng_apply，bl，0x513c。
```text
0x5114 add r4,r12
0x5118 ld r2,@(8,r4)
0x511c seth r4,#0x1
0x5120 add3 r4,r4,#-8960
0x5124 add r4,r12
0x5128 st r4,@(8,sp)
0x512c ldi r4,#0
0x5130 st r4,@(4,sp)
0x5134 st r4,@sp
0x5136 ldi r3,#0
0x5138 ldi r1,#3
0x513a ldi r0,#6
0x513c bl 43c0 <svc.constprop.0>
0x5140 beqz r0,5644 <eng_apply+0xcf4>
0x5144 bnez r8,4a14 <eng_apply+0xc4>
```

eng_apply，bl，0x55b8。
```text
0x5598 ldi r6,#1
0x559c stb r6,@(2468,r5)
0x55a0 st r4,@(4,sp)
0x55a4 mv r5,r10
0x55a6 add r5,r12
0x55a8 st r5,@(8,sp)
0x55ac ldi r4,#80
0x55ae st r4,@sp
0x55b0 add r3,r12
0x55b2 ldi r2,#0
0x55b4 ldi r1,#2
0x55b6 ldi r0,#6
0x55b8 bl 43c0 <svc.constprop.0>
0x55bc bl 9bc <mapped>
0x55c0 bnez r0,5474 <eng_apply+0xb24>
```

eng_apply，bl，0x55f4。
```text
0x55ce ldi r4,#4
0x55d0 add r11,r12
0x55d4 stb r4,@(2474,r11)
0x55d8 add r10,r12
0x55dc st r10,@(8,sp)
0x55e0 ldi r4,#0
0x55e4 st r4,@(4,sp)
0x55e8 st r4,@sp
0x55ea ldi r3,#0
0x55ec ldi r2,#0
0x55ee ldi r1,#1
0x55f0 ldi r0,#5
0x55f4 bl 43c0 <svc.constprop.0>
0x55f8 bl 9bc <mapped>
0x55fc mv fp,r0
```

eng_apply，bl，0x562c。
```text
0x5604 bl 45a8 <fresh>
0x5608 beqz r0,5474 <eng_apply+0xb24>
0x560c seth r4,#0x1
0x5610 add3 r4,r4,#-8928
0x5614 add r4,r12
0x5618 ld r2,@(8,r4)
0x561c st r10,@(8,sp)
0x5620 st fp,@(4,sp)
0x5624 ldi r3,#0
0x5626 ldi r1,#3
0x5628 st fp,@sp
0x562a ldi r0,#6
0x562c bl 43c0 <svc.constprop.0>
0x5630 bl 9bc <mapped>
0x5634 mv r10,r0
```


t_read

eng_apply，bl，0x52ac。
```text
0x5280 ldi r0,#1
0x5284 bl 46cc <rpc.lto_priv.0>
0x5288 bnez r0,529c <eng_apply+0x94c>
0x528c bl a30 <failure>
0x5290 mv r8,r0
0x5294 beqz r0,546c <eng_apply+0xb1c>
0x5298 bra 510c <eng_apply+0x7bc>
0x529c mv r5,r8
0x529e add r5,r12
0x52a0 ldi r6,#1
0x52a4 stb r6,@(2474,r5)
0x52a8 st r5,@(80,sp)
0x52ac bl 4850 <t_read>
0x52b0 cmpui r11,#1
0x52b4 mvfc r6,cbr
```

eng_apply，bl，0x5414。
```text
0x53e8 addi r5,#12
0x53ec st r5,@(32,sp)
0x53f0 beqz r11,545c <eng_apply+0xb0c>
0x53f4 ld r5,@(24,sp)
0x53f8 addi r5,#-9
0x53fc bnez r5,5394 <eng_apply+0xa44>
0x5400 ld r3,@(28,sp)
0x5404 beqz r3,5460 <eng_apply+0xb10>
0x5408 ld r4,@(44,sp)
0x540c ldi r5,#1
0x540e add r4,r12
0x5410 stb r5,@(2474,r4)
0x5414 bl 4850 <t_read>
0x5418 addi r0,#-2
0x541c bnez r0,545c <eng_apply+0xb0c>
```


t_store

eng_apply，bl，0x52e4。
```text
0x52b4 mvfc r6,cbr
0x52b8 ld r5,@(80,sp)
0x52bc slli r6,#0x1
0x52c0 beq r6,r0,52d4 <eng_apply+0x984>
0x52c4 ldi r4,#257
0x52c8 sth r4,@(2470,r5)
0x52cc bl 48e8 <end>
0x52d0 bra 5108 <eng_apply+0x7b8>
0x52d4 ldi r6,#0
0x52d8 stb r6,@(2471,r5)
0x52dc beqz r11,5390 <eng_apply+0xa40>
0x52e0 ldi r0,#2
0x52e4 bl 47fc <t_store>
0x52e8 ldi r4,#0
0x52ec cmpu r4,r0
```

eng_apply，bl，0x5420。
```text
0x53f4 ld r5,@(24,sp)
0x53f8 addi r5,#-9
0x53fc bnez r5,5394 <eng_apply+0xa44>
0x5400 ld r3,@(28,sp)
0x5404 beqz r3,5460 <eng_apply+0xb10>
0x5408 ld r4,@(44,sp)
0x540c ldi r5,#1
0x540e add r4,r12
0x5410 stb r5,@(2474,r4)
0x5414 bl 4850 <t_read>
0x5418 addi r0,#-2
0x541c bnez r0,545c <eng_apply+0xb0c>
0x5420 bl 47fc <t_store>
0x5424 ldi r5,#0
0x5428 cmpu r5,r0
```


transfer

io_read，bl，0x1948。
```text
0x1924 add3 r4,sp,#8
0x1928 ld r0,@r0
0x192c st r4,@(4,sp)
0x1930 ldi r4,#256
0x1934 add3 r3,r0,#36
0x1938 sub r4,r6
0x193a cmpu r5,r4
0x193c bnc 1940 <io_read+0x84>
0x193e mv r4,r5
0x1940 mv r2,r1
0x1942 st r4,@sp
0x1944 ldi r1,#4
0x1948 bl 14d4 <transfer>
0x194c ldi r11,#1
0x1950 cmpu r11,r0
```

io_write，bl，0x1a2c。
```text
0x1a06 bc 1a4c <io_write+0x8c>
0x1a08 ld r0,@r0
0x1a0a mv r2,r3
0x1a0c addi r0,#36
0x1a10 bl 13c <ig_copy>
0x1a14 ld r4,@(28,sp)
0x1a18 ldi r1,#5
0x1a1a ld r0,@r8
0x1a1c mv r2,r10
0x1a20 st r4,@(4,sp)
0x1a24 st r9,@sp
0x1a28 add3 r3,r0,#36
0x1a2c bl 14d4 <transfer>
0x1a30 mv r1,r0
0x1a34 mv r0,r8
```


ui_call.constprop.0

pn_ui_render.constprop.0，bl，0x40a0。
```text
0x407c st r5,@(1344,r8)
0x4080 ld r5,@(1324,r8)
0x4084 bnez r5,408c <pn_ui_render.constprop.0+0x248>
0x4088 ldi r0,#-3
0x408a bra 3e94 <pn_ui_render.constprop.0+0x50>
0x408c beqz r0,4088 <pn_ui_render.constprop.0+0x244>
0x4090 add3 r2,r8,#1316
0x4094 st r7,@(28,sp)
0x4098 st r3,@sp
0x409a ldi r1,#1
0x409c ldi r3,#40
0x409e ldi r0,#11
0x40a0 bl 3d9c <ui_call.constprop.0>
0x40a4 ld r7,@(28,sp)
0x40a8 bnez r0,3e94 <pn_ui_render.constprop.0+0x50>
```

pn_ui_render.constprop.0，bl，0x41f4。
```text
0x41cc st r7,@(1280,r11)
0x41d0 ldi r4,#0
0x41d4 st r4,@(1272,r11)
0x41d8 st r4,@(1276,r11)
0x41dc ldi r7,#33
0x41e0 st r7,@(1284,r11)
0x41e4 ldi r5,#1
0x41e8 stb r5,@(560,r11)
0x41ec st r4,@sp
0x41ee ldi r3,#48
0x41f0 ldi r1,#1
0x41f2 ldi r0,#12
0x41f4 bl 3d9c <ui_call.constprop.0>
0x41f8 bnez r0,3e94 <pn_ui_render.constprop.0+0x50>
0x41fc ld r4,@(1276,r11)
```

pn_ui_render.constprop.0，bl，0x426c。
```text
0x4244 stb r4,@(559,r5)
0x4248 add r9,r12
0x424c ldub r4,@(562,r9)
0x4250 bnez r4,3e90 <pn_ui_render.constprop.0+0x4c>
0x4254 add3 r2,r9,#1228
0x4258 ldi r4,#1
0x425c stb r4,@(558,r9)
0x4260 ldi r8,#11
0x4262 st r8,@sp
0x4264 ldi r3,#40
0x4266 ldi r1,#1
0x4268 ldi r0,#10
0x426c bl 3d9c <ui_call.constprop.0>
0x4270 bnez r0,3e94 <pn_ui_render.constprop.0+0x50>
0x4274 ldub r4,@(562,r9)
```

pn_ui_render.constprop.0，bl，0x4288。
```text
0x4264 ldi r3,#40
0x4266 ldi r1,#1
0x4268 ldi r0,#10
0x426c bl 3d9c <ui_call.constprop.0>
0x4270 bnez r0,3e94 <pn_ui_render.constprop.0+0x50>
0x4274 ldub r4,@(562,r9)
0x4278 bnez r4,3e90 <pn_ui_render.constprop.0+0x4c>
0x427c add3 r2,r9,#1228
0x4280 st r8,@sp
0x4282 ldi r3,#40
0x4284 ldi r1,#2
0x4286 ldi r0,#10
0x4288 bl 3d9c <ui_call.constprop.0>
0x428c bnez r0,3e94 <pn_ui_render.constprop.0+0x50>
0x4290 ldub r4,@(562,r9)
```

pn_ui_render.constprop.0，bl，0x42b0。
```text
0x4288 bl 3d9c <ui_call.constprop.0>
0x428c bnez r0,3e94 <pn_ui_render.constprop.0+0x50>
0x4290 ldub r4,@(562,r9)
0x4294 bnez r4,3e90 <pn_ui_render.constprop.0+0x4c>
0x4298 seth r2,#0x1
0x429c add3 r2,r2,#-4352
0x42a0 add r2,r12
0x42a4 add3 r2,r2,#1228
0x42a8 st r8,@sp
0x42aa ldi r3,#40
0x42ac ldi r1,#3
0x42ae ldi r0,#10
0x42b0 bl 3d9c <ui_call.constprop.0>
0x42b4 bra 3e94 <pn_ui_render.constprop.0+0x50>
0x42b8 ldi r0,#-4
```


ui_finish

ig_apply，bl，0x8070。
```text
0x8040 add3 r4,r4,#-4352
0x8044 add r4,r12
0x8048 ldub r5,@(2072,r4)
0x804c beqz r5,80d0 <ig_apply+0xb8>
0x8050 ldi r5,#1
0x8054 stb r5,@(2082,r4)
0x8058 ldub r4,@(550,r4)
0x805c beqz r4,8080 <ig_apply+0x68>
0x8060 ld r0,@(40,r9)
0x8064 bl 42c8 <a4_move>
0x8068 mv r1,r0
0x806c mv r0,r8
0x8070 bl 1280 <ui_finish>
0x8074 pop lr
0x8076 pop r12
```

ig_event，bl，0x81b4。
```text
0x818c mv r6,r4
0x818e xor r6,r5
0x8190 cmpui r6,#1
0x8194 mvfc r4,cbr
0x8198 seth r5,#0x1
0x819c add3 r5,r5,#-6828
0x81a0 add r5,r12
0x81a4 ldub r5,@(2468,r5)
0x81a8 beqz r5,81c4 <ig_event+0xf0>
0x81ac ldi r8,#3
0x81b0 mv r1,r8
0x81b2 mv r0,r10
0x81b4 bl 1280 <ui_finish>
0x81b8 bra 82f8 <ig_event+0x224>
0x81bc ldi r4,#0
```

ig_panel_open，bl，0x83c8。
```text
0x839a and r4,r5
0x839c stb r4,@(549,r9)
0x83a0 add r4,r9
0x83a4 ldub r4,@(519,r4)
0x83a8 add r4,r9
0x83ac ldub r4,@(511,r4)
0x83b0 addi r4,#5
0x83b4 stb r4,@(553,r9)
0x83b8 bl 3e44 <pn_ui_render.constprop.0>
0x83bc beqz r0,85e4 <ig_panel_open+0x2b4>
0x83c0 ldi r1,#3
0x83c4 mv r0,r10
0x83c8 bl 1280 <ui_finish>
0x83cc bra 8420 <ig_panel_open+0xf0>
0x83d0 seth r4,#0x2022
```

ig_panel_event，bl，0x8640。
```text
0x8610 beqz r0,8650 <ig_panel_event+0x60>
0x8614 seth r4,#0x1
0x8618 add3 r4,r4,#-4352
0x861c add r4,r12
0x8620 ldub r5,@(2072,r4)
0x8624 beqz r5,8650 <ig_panel_event+0x60>
0x8628 ldi r5,#1
0x862c stb r5,@(2082,r4)
0x8630 ld r0,@(40,r9)
0x8634 bl 42c8 <a4_move>
0x8638 mv r1,r0
0x863c mv r0,r8
0x8640 bl 1280 <ui_finish>
0x8644 pop lr
0x8646 pop r12
```

ig_panel_abort，bl，0x86b0。
```text
0x8680 ldub r4,@(550,r5)
0x8684 beqz r4,86bc <ig_panel_abort+0x68>
0x8688 seth r4,#0x1
0x868c add3 r4,r4,#-6828
0x8690 add r4,r12
0x8694 ldub r6,@(2468,r4)
0x8698 bnez r6,86c0 <ig_panel_abort+0x6c>
0x869c sth r6,@(550,r5)
0x86a0 ldi r5,#0
0x86a4 stb r5,@(805,r4)
0x86a8 ldi r1,#2
0x86ac mv r0,r8
0x86b0 bl 1280 <ui_finish>
0x86b4 pop lr
0x86b6 pop r12
```


ui_prepare.constprop.0

rv_call，bl，0xa228。
```text
0xa1fc cmpu r8,r5
0xa1fe bc a24c <rv_call+0x1a0c>
0xa200 add3 r5,r11,#-1
0xa204 beqz r5,a228 <rv_call+0x19e8>
0xa208 ld24 r5,80151c <n+0x7f251c>
0xa20c ld r6,@(8,r9)
0xa210 slli r5,#0x6
0xa214 ld r5,@(32,r5)
0xa218 bne r6,r5,97a4 <rv_call+0xf64>
0xa21c ld r6,@(484,r10)
0xa220 ld r5,@(12,r9)
0xa224 bne r6,r5,97a4 <rv_call+0xf64>
0xa228 bl 6dfc <ui_prepare.constprop.0>
0xa22c mv r8,r0
0xa230 beqz r0,9bc8 <rv_call+0x1388>
```

rv_call，bl，0xa58c。
```text
0xa564 or3 r5,r5,#0x2794
0xa568 slli r8,#0x3
0xa56a add r5,r8
0xa56c ldub r6,@r5
0xa570 ld r5,@(40,r9)
0xa574 bne r6,r5,97a4 <rv_call+0xf64>
0xa578 seth r6,#0x205a
0xa57c or3 r6,r6,#0x2798
0xa580 ld r5,@(44,r9)
0xa584 add r8,r6
0xa586 ld r6,@r8
0xa588 bne r6,r5,97a4 <rv_call+0xf64>
0xa58c bl 6dfc <ui_prepare.constprop.0>
0xa590 mv r10,r0
0xa594 beqz r0,9bc8 <rv_call+0x1388>
```


ui_seed.constprop.0

rv_call，bl，0xa2d8。
```text
0xa2ae addi r5,#1
0xa2b0 beqz r2,a2c0 <rv_call+0x1a80>
0xa2b4 add3 r2,r5,#-96
0xa2b8 bnez r2,a280 <rv_call+0x1a40>
0xa2bc bra 9e7c <rv_call+0x163c>
0xa2c0 ld r6,@(32,sp)
0xa2c4 addi r8,#1
0xa2c6 st r5,@+r6
0xa2c8 st r6,@(32,sp)
0xa2cc bra a1f8 <rv_call+0x19b8>
0xa2d0 ld r1,@(12,r9)
0xa2d4 mv r0,r8
0xa2d8 bl 34dc <ui_seed.constprop.0>
0xa2dc beqz r0,a404 <rv_call+0x1bc4>
0xa2e0 ld24 r7,80151c <n+0x7f251c>
```

rv_call，bl，0xa5c8。
```text
0xa598 bl b010 <rv_irq_save>
0xa59c mv r11,r0
0xa5a0 bl 3418 <es_ui_capture.constprop.0>
0xa5a4 bnez r0,a5b0 <rv_call+0x1d70>
0xa5a8 mv r0,r11
0xa5ac bra 9e40 <rv_call+0x1600>
0xa5b0 ld24 r5,80151c <n+0x7f251c>
0xa5b4 slli r5,#0x6
0xa5b8 ld r5,@(180,r5)
0xa5bc bnez r5,a5d4 <rv_call+0x1d94>
0xa5c0 ld r1,@(20,r9)
0xa5c4 mv r0,r10
0xa5c8 bl 34dc <ui_seed.constprop.0>
0xa5cc bnez r0,a5d4 <rv_call+0x1d94>
0xa5d0 mv r0,r11
```


unit_equal.lto_priv.0

gxr2_semantic_validate，bl，0x2464。
```text
0x243c slli r5,#0x8
0x243e or r4,r5
0x2440 addi r4,#-2
0x2444 bnez r4,320c <gxr2_semantic_validate+0xe84>
0x2448 ldub r5,@(6,r8)
0x244c ldub r4,@(7,r8)
0x2450 slli r5,#0x8
0x2452 or r4,r5
0x2454 add3 r4,r4,#-152
0x2458 bnez r4,320c <gxr2_semantic_validate+0xe84>
0x245c add3 r1,r10,#-16
0x2460 add3 r0,r8,#8
0x2464 bl c10 <unit_equal.lto_priv.0>
0x2468 beqz r0,320c <gxr2_semantic_validate+0xe84>
0x246c ldub r5,@(20,r8)
```

gate_validate.constprop.0，bl，0x6104。
```text
0x60dc add r5,r12
0x60e0 add3 r4,r5,#380
0x60e4 st r5,@(16,sp)
0x60e8 add3 r5,r9,#20
0x60ec st r4,@(64,sp)
0x60f0 add r3,r8
0x60f2 add r5,r8
0x60f4 st r5,@(44,sp)
0x60f8 st r3,@sp
0x60fa mv r10,r3
0x60fc ld r1,@(28,sp)
0x6100 mv r0,r10
0x6104 bl c10 <unit_equal.lto_priv.0>
0x6108 beqz r0,5c40 <gate_validate.constprop.0+0x220>
0x610c ldub r5,@(31,r10)
```


unit_equal.lto_priv.1

gxr2_semantic_validate，bl，0x2464。
```text
0x243c slli r5,#0x8
0x243e or r4,r5
0x2440 addi r4,#-2
0x2444 bnez r4,320c <gxr2_semantic_validate+0xe84>
0x2448 ldub r5,@(6,r8)
0x244c ldub r4,@(7,r8)
0x2450 slli r5,#0x8
0x2452 or r4,r5
0x2454 add3 r4,r4,#-152
0x2458 bnez r4,320c <gxr2_semantic_validate+0xe84>
0x245c add3 r1,r10,#-16
0x2460 add3 r0,r8,#8
0x2464 bl c10 <unit_equal.lto_priv.0>
0x2468 beqz r0,320c <gxr2_semantic_validate+0xe84>
0x246c ldub r5,@(20,r8)
```

gate_validate.constprop.0，bl，0x6104。
```text
0x60dc add r5,r12
0x60e0 add3 r4,r5,#380
0x60e4 st r5,@(16,sp)
0x60e8 add3 r5,r9,#20
0x60ec st r4,@(64,sp)
0x60f0 add r3,r8
0x60f2 add r5,r8
0x60f4 st r5,@(44,sp)
0x60f8 st r3,@sp
0x60fa mv r10,r3
0x60fc ld r1,@(28,sp)
0x6100 mv r0,r10
0x6104 bl c10 <unit_equal.lto_priv.0>
0x6108 beqz r0,5c40 <gate_validate.constprop.0+0x220>
0x610c ldub r5,@(31,r10)
```


verify

地址引用：{"pc": "0x7d88", "kind": "encoded GOTOFF function address", "target": "verify", "owner": "ig_menu"}

warp

rt_tone.constprop.0，bl，0x3d58。
```text
0x3d38 ldi fp,#32
0x3d3a bra 3cf0 <rt_tone.constprop.0+0x100>
0x3d3c mv lr,r8
0x3d3e add lr,r5
0x3d40 ldub r2,@r7
0x3d42 mv r3,r10
0x3d44 ldub r1,@r8
0x3d46 ldub r0,@lr
0x3d48 st r4,@(12,sp)
0x3d4c st r5,@(4,sp)
0x3d50 st r6,@(8,sp)
0x3d54 st r7,@(16,sp)
0x3d58 bl 1cd0 <warp>
0x3d5c ld r5,@(4,sp)
0x3d60 mv r2,r11
```

rt_tone.constprop.0，bl，0x3d8c。
```text
0x3d64 stb r0,@r2
0x3d68 ld r7,@(16,sp)
0x3d6c addi r5,#1
0x3d70 ld r6,@(8,sp)
0x3d74 ld r4,@(12,sp)
0x3d78 bra 3d24 <rt_tone.constprop.0+0x134>
0x3d7c ldub r2,@(32,r8)
0x3d80 mv r4,r8
0x3d82 add r4,r9
0x3d84 ldub r0,@r4
0x3d86 ldub r1,@r10
0x3d88 ld r3,@sp
0x3d8c bl 1cd0 <warp>
0x3d90 mv r4,r11
0x3d94 add r4,r9
```


workspace_close

finish，bl，0x1210。
```text
0x11f0 ldub r1,@(2474,r4)
0x11f4 mv r4,r9
0x11f6 add r4,r12
0x11f8 add r4,r5
0x11fa ld r4,@r4
0x11fc ldi r3,#0
0x11fe mv r2,r8
0x1200 ldi r0,#5
0x1204 st r4,@(4,sp)
0x1208 ldi r4,#0
0x120a st r4,@sp
0x120c bl 208 <ig_bx_event>
0x1210 bl 10f8 <workspace_close>
0x1214 beqz r0,121c <finish+0x78>
0x1218 ldi r8,#5
```

ui_finish，bl，0x12b4。
```text
0x1290 push r11
0x1294 add3 r11,r1,#-3
0x1298 push r12
0x129a push lr
0x129c bl 12a0 <ui_finish+0x20>
0x12a0 seth r12,#0x0
0x12a4 add3 r12,r12,#-4512
0x12a8 add r12,lr
0x12aa ld lr,@sp
0x12ac mv r10,r0
0x12ae mv r9,r1
0x12b0 bnez r11,12d0 <ui_finish+0x50>
0x12b4 bl 10f8 <workspace_close>
0x12b8 beqz r0,12c4 <ui_finish+0x44>
0x12bc ldi r4,#-11
```

ig_stop，bl，0x871c。
```text
0x86f4 add3 r4,r4,#-6828
0x86f8 add r5,r12
0x86fc ldub r6,@(550,r5)
0x8700 beqz r6,8714 <ig_stop+0x4c>
0x8704 mv r6,r4
0x8706 add r6,r12
0x8708 ldub r6,@(2468,r6)
0x870c bnez r6,873c <ig_stop+0x74>
0x8710 sth r6,@(550,r5)
0x8714 add r4,r12
0x8716 ldi r5,#0
0x8718 stb r5,@(805,r4)
0x871c bl 10f8 <workspace_close>
0x8720 bnez r0,8750 <ig_stop+0x88>
0x8724 ldi r1,#0
```


write_word

t_store，bl，0x4812。
```text
0x47fc push r8
0x47fe push r12
0x4800 push lr
0x4802 bl 4804 <t_store+0x8>
0x4804 seth r12,#0x0
0x4808 add3 r12,r12,#-18180
0x480c add r12,lr
0x480e ld lr,@sp
0x4810 mv r8,r0
0x4812 bl 47a4 <write_word>
0x4814 beqz r0,4848 <t_store+0x4c>
0x4818 seth r4,#0x1
```

eng_apply，bl，0x5528。
```text
0x5504 ldi r6,#0
0x5506 bra 54cc <eng_apply+0xb7c>
0x5508 add3 r2,r6,#1
0x550c beqz r2,5548 <eng_apply+0xbf8>
0x5510 ldub r7,@r8
0x5512 slli r7,#0x8
0x5514 cmp r2,r5
0x5516 bnc 554c <eng_apply+0xbfc>
0x5518 ldub r0,@(1,r8)
0x551c st r5,@(80,sp)
0x5520 st r6,@(76,sp)
0x5524 or r0,r7
0x5528 bl 47a4 <write_word>
0x552c ld r5,@(80,sp)
0x5530 addi r8,#2
```


