#!/usr/bin/python3 -I -B
"""Build one restricted, non-distributed MAIN research copy."""
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

o = sys.modules['__main__']
LD = o.ROOT / 'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld'

YUV = '''
    ld r1,@(40,sp)
    ld r0,@(32,sp)
    sub r1,r0
    srl3 r10,r1,#1
    add r0,r10
    mv r8,r0
    ldi r0,#1
    bne r11,r0,move_window
    ld24 r11,#0x8080
    add3 r9,r12,#344
    lduh fp,@(352,r12)
    push r11
    push r10
    ld r0,@(52,sp)
    push r0
    ld r4,@r9
    mv r5,fp
    ldi r6,#0
    ldi r7,#0
    bl rectangle_fill
    addi sp,#12
    ld r4,@r9
    mv r5,fp
    mv r0,fp
    mul r0,r8
    add r4,r0
    push r11
    push r10
    ld r0,@(52,sp)
    push r0
    ldi r6,#0
    ldi r7,#0
    bl rectangle_fill
    addi sp,#12
move_window:
    ld r0,@(44,sp)
    ld r1,@(36,sp)
    sub r0,r1
    lduh r1,@(352,r12)
    mul r10,r1
    ld r1,@(344,r12)
    add r10,r1
    add r10,r0
    st r10,@(344,r12)
    bra yuv_end
.set rectangle_fill,0x20121074
.set yuv_end,0x201867c4
'''

RAW = '''
    ldub r1,@(5,r0)
    ldi r2,#18
    beq r1,r2,large_raw
    ldi r2,#20
    beq r1,r2,large_raw
    ldi r1,#4304
    ldi r2,#2430
    ldi r3,#0
    ldi r4,#216
    bra raw_values
large_raw:
    ldi r1,#4176
    ldi r2,#1550
    ldi r3,#64
    ldi r4,#656
raw_values:
    st r1,@(552,r0)
    st r2,@(556,r0)
    st r3,@(544,r0)
    st r4,@(548,r0)
    addi r1,#-16
    st r1,@(568,r0)
    add3 r4,r2,#-14
    bra raw_end
.set raw_end,0x2018b7fc
'''

DISPLAY = '''
    seth r0,#0x2043
    or3 r0,r0,#0x7845
    ldub r1,@r0
    ldi r0,#18
    beq r1,r0,large_view
    ldi r0,#20
    beq r1,r0,large_view
    seth r2,#0x2038
    or3 r2,r2,#0xb2ac
    ld r0,@(12,r2)
    addi r0,#1
    ldi r1,#5
    mul r0,r1
    srli r0,#6
    bra vertical_view
large_view:
    seth r2,#0x2038
    or3 r2,r2,#0xb2ac
    ld r0,@(4,r2)
    ld r1,@r2
    sub r0,r1
    addi r0,#1
    ldi r3,#67
    divu r0,r3
    add r1,r0
    st r1,@r2
    ld r1,@(4,r2)
    sub r1,r0
    st r1,@(4,r2)
    ld r0,@(12,r2)
    ld r1,@(8,r2)
    sub r0,r1
    addi r0,#1
    ldi r1,#41
    mul r0,r1
    ldi r1,#178
    divu r0,r1
vertical_view:
    ld r1,@(8,r2)
    add r1,r0
    st r1,@(8,r2)
    ld r1,@(12,r2)
    sub r1,r0
    st r1,@(12,r2)
    bra display_end
.set display_end,0x2012588c
'''


def assemble(label, start, source, capacity):
    base = o.LOCAL / 'assembly' / label
    targets = re.findall(r'^\.set (\w+),(0x[0-9a-f]+)$', source, re.M)
    source = re.sub(r'^\.set (\w+),(0x[0-9a-f]+)$', r'.global \1', source, flags=re.M)
    o.put(base.with_suffix('.s'), '.text\n.global _start\n_start:\n'+source)
    commands = [
        [str(o.AS), '-EB', '-o', str(base.with_suffix('.o')), str(base.with_suffix('.s'))],
        [str(LD), '-Ttext', hex(start), '-e', '_start',
         *[f'--defsym={name}={value}' for name, value in targets], '-o', str(base.with_suffix('.elf')),
         str(base.with_suffix('.o'))],
        [str(o.OBJCOPY), '-O', 'binary', '-j', '.text', str(base.with_suffix('.elf')),
         str(base.with_suffix('.bin'))],
    ]
    for cmd in commands:
        run = subprocess.run(cmd, capture_output=True, text=True)
        if run.returncode:
            raise RuntimeError(run.stdout+run.stderr)
    data = base.with_suffix('.bin').read_bytes()
    assert len(data) <= capacity, (label, len(data), capacity)
    return data


def build():
    o.verify_inputs()
    source = o.official()
    data = bytearray(source)
    sites = [
        ('large_width', 0x201a2ed8, '    ldi r0,#4160\n', 4, 'Only L category 2 width'),
        ('large_height', 0x201a2ee8, '    ldi r0,#1536\n', 4, 'Only L category 2 height'),
        ('source_x', 0x201a2fd8, '    ldi r1,#64\n    st r1,@r0\n', 4,
         'Separate X value after the earlier zero store'),
        ('source_y', 0x201a2fe4, '    ldi r1,#656\n', 4, 'Category 2 source Y'),
        ('yuv_window', 0x201866fc, YUV, 0x98,
         'Keep original row clearing and add centered horizontal movement'),
        ('raw_scope', 0x2018b790, RAW, 0x6c,
         'Use new RAW values only for internal size 18 or 20'),
        ('display_window', 0x201256ac, DISPLAY, 0x138,
         'Project two axes from assumed full active image; physical mapping is OPEN'),
    ]
    rows = []
    for label, start, text, capacity, purpose in sites:
        code = assemble(label, start, text, capacity)
        f = o.offset(source, start)
        data[f:f+len(code)] = code
        rows.append(dict(label=label, vma=hex(start), file=hex(f), length=len(code),
                         maximum_length=capacity, purpose=purpose,
                         before_sha256=o.sha(source[f:f+len(code)]), after_sha256=o.sha(code)))
    struct.pack_into('>I', data, 0x16c, o.weighted(data))
    rows.append(dict(label='weighted_value', file='0x16c', length=4,
                     purpose='Recompute the official content weighted value'))
    assert len(data) == len(source)
    assert data[:0x16c] == source[:0x16c]
    assert data[0x170:0x200] == source[0x170:0x200]
    o.put(o.LOCAL / 'candidate/jlaunch3', bytes(data))
    o.record('change-map.json', rows)
    for row in rows[:-1]:
        start = int(row['vma'], 16)
        o.evidence(row['label']+'-before', start, start+row['length'], source)
        o.evidence(row['label']+'-after', start, start+row['length'], data)
    o.log('candidate', '生成有未闭合项的研究副本', '保留具体差异供离线审查',
          'local/change-map.json', 'INCOMPLETE')
    print('Research copy', o.sha(data), 'weighted value', hex(o.weighted(data)))
    print('Assembly lengths', [(r['label'], r['length']) for r in rows])


def main(args):
    build()
