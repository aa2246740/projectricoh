#!/usr/bin/python3 -I
"""Require a future resident/body rebuild to differ only in declared identity bytes."""
from pathlib import Path
import argparse
import json
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from static_check import BASE, Elf, checksum, offset, sha


def compare(old_elf, new_elf, old_body, new_body):
    old, new = Elf(old_elf), Elf(new_elf)
    old_raw, new_raw = old.sections['.resident']['data'], new.sections['.resident']['data']
    assert old.symbols['rv_trust'] == new.symbols['rv_trust']
    trust, size = old.symbols['rv_trust']
    assert size == 80
    begin, end = trust - BASE + 32, trust - BASE + 80
    assert len(old_raw) == len(new_raw) == 8040
    assert old_raw[:begin] == new_raw[:begin] and old_raw[end:] == new_raw[end:]
    assert old.sections.keys() == new.sections.keys()
    for name in old.sections:
        left, right = old.sections[name], new.sections[name]
        if left['flags'] & 2:
            assert (left['address'], left['bytes'], left['flags'], left['type']) == (
                right['address'], right['bytes'], right['flags'], right['type'])
            if name != '.resident':
                assert left['data'] == right['data']
    symbols = [name for name in old.symbols if name.startswith('rv_hook_') or name.startswith('rv_skip_')]
    assert all(old.symbols[name] == new.symbols[name] for name in symbols)
    left, right = old_body.read_bytes(), new_body.read_bytes()
    assert len(left) == len(right) == 3993340
    first, last = offset(trust + 32), offset(trust + 80)
    different = [i for i, (a, b) in enumerate(zip(left, right)) if a != b]
    allowed = set(range(first, last)) | set(range(0x16c, 0x170))
    assert not set(different) - allowed
    assert left[offset(BASE):offset(BASE) + len(old_raw)] == old_raw
    assert right[offset(BASE):offset(BASE) + len(new_raw)] == new_raw
    for data in (left, right):
        assert struct.unpack_from('>I', data, 0x16c)[0] == checksum(data)
    return {'status': 'PASS', 'old_resident_sha256': sha(old_raw), 'new_resident_sha256': sha(new_raw),
            'old_body_sha256': sha(left), 'new_body_sha256': sha(right),
            'resident_identity_file_range': [hex(begin), hex(end)],
            'body_identity_file_range': [hex(first), hex(last)],
            'changed_body_bytes': len(different), 'outside_identity_and_checksum': [],
            'build_id_changed': old_raw[begin:begin + 32] != new_raw[begin:begin + 32],
            'abi_id_changed': old_raw[begin + 32:end] != new_raw[begin + 32:end]}


def main():
    parser = argparse.ArgumentParser()
    for name in ('old-elf', 'new-elf', 'old-body', 'new-body', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    result = compare(args.old_elf, args.new_elf, args.old_body, args.new_body)
    destination = args.output.resolve()
    allowed = (Path(__file__).resolve().parents[1],
               Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-body-v39'))
    assert any(destination.is_relative_to(base) for base in allowed)
    destination.write_text(json.dumps(result, indent=1) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
