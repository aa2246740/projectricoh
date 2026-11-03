#!/usr/bin/python3 -I
"""Strict prototype link for the next body update (measure only, never imaged).

Usage: proto_strict.py <variant_dir> [name=0xaddr ...]
Copied from research/body_next_plan/prototype/r2 (body-next-steps): RV_EXTRA_CFLAGS
appends C flags for flag experiments only. Same flags and object order as the v3.8 constrained link, the variant's own
resident.ld with the real root at 0x20054700, --no-undefined and
--orphan-handling=error. After linking it checks the section list, the
.forbidden and relocation sections, root/pins sizes, and that the planning
margin is defined exactly once (in resident.ld) and nowhere else.
"""
import hashlib, json, os, re, subprocess, sys
from pathlib import Path

R = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
GCC = R / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
LD = R / 'research/tooling_m32r_asm/prefix/bin/m32r-elf-ld'
OBJCOPY = R / 'research/tooling_m32r_asm/prefix/bin/m32r-elf-objcopy'
OBJDUMP = R / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
FLAGS = ['-std=c11', '-Os', '-fomit-frame-pointer', '-ffreestanding', '-fno-builtin',
         '-fno-stack-protector', '-fno-common', '-fno-pic', '-m32r', '-mmodel=large',
         '-msdata=none', '-G0', '-Wall', '-Wextra', '-Werror', '-fno-unwind-tables',
         '-fno-asynchronous-unwind-tables', '-fstack-usage', '-ffunction-sections',
         '-fdata-sections']
ORDER = ['resident', 'loader', 'shared', 'hooks', 'runtime', 'validate_envelope.inc',
         'bridges', 'trust', 'linked_hooks']
DEFSYM = {
    'rv_skip_target_01': 0x202870a8, 'rv_skip_target_02': 0x20287118,
    'rv_skip_target_05': 0x201febec, 'rv_skip_target_06': 0x202be6a8,
    'rv_skip_target_08': 0x202bcf58, 'rv_resume_01': 0x202870a4,
    'rv_resume_02': 0x202870ac, 'rv_resume_05': 0x201febec,
    'rv_resume_06': 0x202be250, 'rv_resume_07': 0x202871dc,
    'rv_resume_08': 0x202bb96c, 'rv_resume_09': 0x20170990,
}
ALLOWED = {'.resident', '.root', '.root_pins'}


def run(argv, cwd, check=True):
    p = subprocess.run(['nice', '-n', '10'] + [str(a) for a in argv], cwd=cwd,
                       capture_output=True, text=True)
    if check and p.returncode:
        sys.stderr.write(p.stdout + p.stderr)
        raise SystemExit(f'failed: {Path(str(argv[0])).name}')
    return p


def main():
    v = Path(sys.argv[1]).resolve()
    extra = {k: int(x, 0) for k, x in (a.split('=') for a in sys.argv[2:])}
    out = v / 'build'
    out.mkdir(exist_ok=True)
    for u in ORDER:
        src = v / (u + ('.S' if u in ('bridges', 'linked_hooks') else '.c'))
        model = [] if src.suffix == '.S' else ['-mmodel=medium'] + os.environ.get('RV_EXTRA_CFLAGS', '').split()
        run([GCC] + FLAGS + model + ['-I', v, '-c', src, '-o', out / f'{u}.o'], v)
    ld = (v / 'resident.ld').read_text()
    defs = re.findall(r'RV_PLANNING_MARGIN\s*=\s*(\d+)\s*;', ld)
    others = [p.name for p in v.iterdir() if p.suffix in ('.c', '.h', '.S', '.py')
              and re.search(r'RV_PLANNING_MARGIN\s*=|margin below', p.read_text())]
    syms = dict(DEFSYM)
    syms.update(extra)
    argv = [LD, '--gc-sections', '--no-undefined', '--orphan-handling=error']
    argv += [f'--defsym={k}=0x{x:08x}' for k, x in syms.items()]
    argv += ['-T', v / 'resident.ld', f'-Map={out}/resident.map', '-o', out / 'resident.elf']
    argv += [out / f'{u}.o' for u in ORDER]
    link = run(argv, v, check=False)
    result = {'variant': v.name, 'link_ok': link.returncode == 0,
              'link_messages': (link.stdout + link.stderr).strip().splitlines()[-3:],
              'margin_definitions_in_ld': defs, 'margin_definitions_elsewhere': others}
    if link.returncode == 0:
        run([OBJCOPY, '-O', 'binary', '-j', '.resident', out / 'resident.elf', out / 'resident.bin'], v)
        raw = (out / 'resident.bin').read_bytes()
        heads = run([OBJDUMP, '-h', out / 'resident.elf'], v).stdout
        sections = {}
        for line in heads.splitlines():
            m = re.match(r'\s*\d+\s+(\S+)\s+([0-9a-f]+)\s+([0-9a-f]+)', line)
            if m:
                sections[m.group(1)] = (int(m.group(2), 16), int(m.group(3), 16))
        symbols = {}
        for line in run([OBJDUMP, '-t', out / 'resident.elf'], v).stdout.splitlines():
            parts = line.split()
            if len(parts) >= 6 and parts[-3] == '.resident' and int(parts[-2], 16):
                symbols[parts[-1]] = int(parts[-2], 16)
        stack = {}
        for su in out.glob('*.su'):
            for line in su.read_text().splitlines():
                name, size = line.split('\t')[:2]
                stack[name.split(':')[-1]] = int(size)
        end = 0x2005276c + len(raw)
        extra_sections = sorted(set(k for k, (size, _) in sections.items() if size) - ALLOWED)
        result.update({
            'code_bytes': len(raw), 'code_end': f'0x{end:08x}',
            'bytes_to_root': 0x20054700 - end,
            'free_above_24B_gate': 0x200546e8 - end,
            'root': sections.get('.root', (0, 0))[0], 'root_pins': sections.get('.root_pins', (0, 0))[0],
            'root_vma': f"0x{sections.get('.root', (0, 0))[1]:08x}",
            'nonempty_sections_outside_allowed': extra_sections,
            'sha256': hashlib.sha256(raw).hexdigest(), 'symbols': symbols, 'stack_frames': stack})
    else:
        m = re.search(r'0x([0-9a-f]+)\s+__resident_code_end = \.', (out / 'resident.map').read_text())
        if m:
            end = int(m.group(1), 16)
            result.update({'code_bytes': end - 0x2005276c, 'code_end': f'0x{end:08x}',
                           'over_24B_gate': end - 0x200546e8})
    (out / 'strict.json').write_text(json.dumps(result, indent=1, sort_keys=True))
    keys = ('variant', 'link_ok', 'code_bytes', 'code_end', 'bytes_to_root', 'free_above_24B_gate',
            'root', 'root_pins', 'root_vma', 'nonempty_sections_outside_allowed',
            'margin_definitions_in_ld', 'margin_definitions_elsewhere', 'over_24B_gate', 'link_messages')
    print(json.dumps({k: result.get(k) for k in keys}))


if __name__ == '__main__':
    main()
