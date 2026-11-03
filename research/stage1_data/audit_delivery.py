#!/usr/bin/env python3
"""Check report links, address mappings and delivered artifact provenance."""
import hashlib
import json
from pathlib import Path
import re
import struct

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    data = (ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3').read_bytes()
    secs = [struct.unpack_from('>IIIII', data, 32 + 20 * i) for i in range(16)]

    def file_offset(va):
        for source, load, length, _, _ in secs:
            if load <= va < load + length:
                return 512 + source + va - load
        raise ValueError(f'unmapped {va:#x}')

    checked_links = 0
    checked_addresses = 0
    for p in [HERE / 'REPORT.md', ROOT / 'firmware/recipe_v1/README.md']:
        content = p.read_text()
        for target in re.findall(r'\]\(([^)]+)\)', content):
            if '://' in target:
                continue
            path, _, fragment = target.partition('#')
            dest = p.parent / path
            if not dest.exists():
                raise ValueError(f'missing link: {p.name}: {target}')
            if fragment.startswith('L'):
                n = int(fragment[1:])
                if not dest.is_file() or not 1 <= n <= len(dest.read_text().splitlines()):
                    raise ValueError(f'invalid line: {target}')
            checked_links += 1
        for first, last, off_first, off_last in re.findall(
                r'(0x[0-9a-fA-F]{8})\.\.(0x[0-9a-fA-F]{8})\s*/\s*文件'
                r'(0x[0-9a-fA-F]+)\.\.(0x[0-9a-fA-F]+)', content):
            if file_offset(int(first, 16)) != int(off_first, 16) or file_offset(int(last, 16)) != int(off_last, 16):
                raise ValueError(f'wrong range mapping: {first}..{last}')
            checked_addresses += 2
        for va, off in re.findall(r'(?<!\.)(0x[0-9a-fA-F]{8})\s*/(?:\s*文件)?\s*(0x[0-9a-fA-F]+)', content):
            if file_offset(int(va, 16)) != int(off, 16):
                raise ValueError(f'wrong mapping: {va}/{off}')
            checked_addresses += 1
    core = ROOT / 'firmware/recipe_v1'
    verification = json.loads((core / 'build/verification.json').read_text())
    assert verification['status'] == 'PASS'
    assert [t['passed_cases'] for t in verification['host_tests']] == [31, 31]
    for rel, expected in verification['source_sha256'].items():
        if sha(ROOT / rel) != expected:
            raise ValueError(f'verification is stale: {rel}')
    artifact = ROOT / verification['m32r']['artifact']
    assert sha(artifact) == verification['m32r']['artifact_sha256']
    protected = json.loads((core / 'protected-inputs.json').read_text())
    for rel, expected in protected.items():
        if sha(ROOT / rel) != expected:
            raise ValueError(f'protected input changed: {rel}')
    result = {'status': 'PASS', 'checked_local_links': checked_links,
              'checked_address_offset_pairs': checked_addresses,
              'firmware_instruction_lines_checked': json.loads((HERE / 'evidence.json').read_text())['verified_instruction_lines'],
              'host_cases_per_mode': 31, 'm32r_text': verification['m32r']['sections']['.text'],
              'm32r_rodata': verification['m32r']['sections']['.rodata'],
              'protected_inputs_unchanged': True,
              'deliverables': {str(p.relative_to(ROOT)): sha(p) for p in [HERE / 'REPORT.md', core / 'README.md', artifact, core / 'build/verification.json']},
              'limits': 'Link and offset checks do not establish firmware runtime or physical camera acceptance.'}
    (HERE / 'delivery-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
