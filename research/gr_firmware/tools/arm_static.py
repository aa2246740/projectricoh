"""Small A32 listing decoder for inspecting enum conversions. No execution."""
import argparse
import pathlib
import struct

CONDITIONS = ['eq', 'ne', 'cs', 'cc', 'mi', 'pl', 'vs', 'vc', 'hi', 'ls', 'ge', 'lt', 'gt', 'le', '', 'nv']
OPS = ['and', 'eor', 'sub', 'rsb', 'add', 'adc', 'sbc', 'rsc', 'tst', 'teq', 'cmp', 'cmn', 'orr', 'mov', 'bic', 'mvn']


def listing(data, start, end, delta):
    lines = []
    for address in range(start, end, 4):
        word = struct.unpack_from('<I', data, address - delta)[0]
        cond, rd, rn = CONDITIONS[word >> 28], (word >> 12) & 15, (word >> 16) & 15
        if 0x53000000 <= word < 0x56000000 and word % 4 == 0:
            op, args = '.word', f'{word:#x} ; address candidate, not decoded as code'
        elif word & 0x0FF00000 in (0x03000000, 0x03400000):
            op = ('movw' if word & 0x0FF00000 == 0x03000000 else 'movt') + cond
            args = f'r{rd}, #{((word & 0xfff) | ((word >> 4) & 0xf000)):#x}'
        elif word & 0x0E000000 == 0x0A000000:
            offset = word & 0xFFFFFF
            if offset & 0x800000:
                offset -= 0x1000000
            op, args = ('bl' if word & 0x1000000 else 'b') + cond, f'{address + 8 + offset * 4:#x}'
        elif word & 0x0FFFFFF0 == 0x012FFF10:
            op, args = 'bx' + cond, f'r{word & 15}'
        elif word & 0x0FFF0FF0 == 0x016F0F10:
            op, args = 'clz' + cond, f'r{rd}, r{word & 15}'
        elif word & 0x0FC000F0 == 0x00000090:
            accumulate = bool(word & (1 << 21))
            op = ('mla' if accumulate else 'mul') + cond
            args = f'r{rn}, r{word & 15}, r{(word >> 8) & 15}' + (f', r{rd}' if accumulate else '')
        elif word & 0x0E000090 == 0x00000090:
            op, args = '.word', f'{word:#x} ; halfword/multiply extension not decoded'
        elif word & 0x0C000000 == 0:
            opcode = (word >> 21) & 15
            operand = word & 0xFFF
            if word & 0x02000000:
                value, rotation = operand & 255, ((operand >> 8) & 15) * 2
                value = ((value >> rotation) | (value << (32 - rotation))) & 0xFFFFFFFF if rotation else value
                last = f'#{value:#x}'
            else:
                last = f'r{operand & 15}'
                if operand & 0xFF0:
                    last += f',shift={operand >> 4:#x}'
            op = OPS[opcode] + cond
            args = f'r{rn}, {last}' if opcode in (8, 9, 10, 11) else f'r{rd}, {last}' if opcode in (13, 15) else f'r{rd}, r{rn}, {last}'
        elif word & 0x0C000000 == 0x04000000:
            op = ('ldr' if word & (1 << 20) else 'str') + ('b' if word & (1 << 22) else '') + cond
            last = f'register({word & 0xfff:#x})' if word & 0x02000000 else f'{"+" if word & 0x800000 else "-"}{word & 0xfff:#x}'
            args = f'r{rd}, [r{rn}, {last}]'
        elif word & 0x0E000000 == 0x08000000:
            op, args = ('ldm' if word & (1 << 20) else 'stm') + cond, f'r{rn}, registers={word & 0xffff:#x}'
        else:
            op, args = '.word', f'{word:#x}'
        lines.append(f'{address:08x}  {word:08x}  {op:8s} {args}')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('input')
    for key in ['start', 'end', 'delta']:
        p.add_argument('--' + key, type=lambda x: int(x, 0), required=True)
    a = p.parse_args()
    print(listing(pathlib.Path(a.input).read_bytes(), a.start, a.end, a.delta), end='')
