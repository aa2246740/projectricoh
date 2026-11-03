#!/usr/bin/env python3
"""Read frozen code or SHA-checked local checkpoint state without executing it."""
import argparse
import hashlib
import json
from pathlib import Path
import pickle
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'tools/gxr_emulator'))
from image import Image
from conformance import disassemble


def number(text):
    return int(text, 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    code = commands.add_parser('code')
    code.add_argument('address', type=number)
    code.add_argument('size', type=number)
    memory = commands.add_parser('memory')
    memory.add_argument('checkpoint')
    memory.add_argument('address', type=number)
    memory.add_argument('size', type=number)
    args = parser.parse_args()
    if args.command == 'code':
        image = Image()
        start = image.offset(args.address, args.size)
        if start is None:
            raise ValueError('code is outside frozen image')
        text = '\n'.join(f'{address:08x} {assembly}' for address, _, assembly in
                         disassemble(image.raw[start:start+args.size], args.address))+'\n'
        output = HERE/'local'/f'code-{args.address:08x}-{args.size:x}.txt'
        if output.exists() and output.read_text() != text:
            raise ValueError('static evidence changed')
        output.write_text(text)
        print(text)
    else:
        path = HERE/'local'/args.checkpoint
        meta = json.loads(path.with_suffix('.json').read_text())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == meta['sha256']
        state = pickle.loads(path.read_bytes())
        print('steps', state['steps'])
        print({key: hex(value) for key, value in state['registers'].items()})
        for base, data, _ in state['regions']:
            if base <= args.address and args.address+args.size <= base+len(data):
                data = data[args.address-base:args.address-base+args.size]
                for offset in range(0, len(data), 16):
                    print(f'{args.address+offset:08x}', ' '.join(
                        f'{int.from_bytes(data[j:j+4], "big"):08x}'
                        for j in range(offset, min(len(data), offset+16), 4)))
                return
        raise ValueError('memory is outside checkpoint RAM')


if __name__ == '__main__':
    main()
