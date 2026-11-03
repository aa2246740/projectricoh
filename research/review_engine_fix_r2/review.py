"""Incremental read-only audit. Writes are confined to this review directory."""
from pathlib import Path
import argparse
import difflib
import hashlib
import importlib.util
import json
import os
import plistlib
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
PRIOR = Path('firmware/engine_fix_r1')
CURRENT = Path('firmware/engine_fix_r2')
REVISION_CASES = (
    'review-free-preload', 'review-free-save', 'review-free-repeat', 'r3-workspace-release',
    'r3-install-free-work', 'r3-install-free-raw', 'r3-install-free-alloc',
    'review-hidden-engine', 'r3-hidden-engine-B', 'r3-newer-generation', 'r3-target-exists',
    'r3-rename-preserves', 'r3-rename-source-loss', 'r3-both-unknown',
    'review-hidden-tweak', 'r3-hidden-tweak-B', 'r3-sticky-read', 'r3-sticky-open',
    'r3-sticky-save-read', 'r3-sticky-save-open', 'r3-gxts-rename-preserves',
    'r3-gxts-source-loss', 'r3-empty-gxts', 'r3-gxts-persistent-minus1',
)


def load_base():
    v = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert v['MountPoint'] == '/Volumes/Workspace' and v['FilesystemType'] == 'apfs'
    assert v['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert v['WritableVolume'] and v['WritableMedia']
    assert ROOT == Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
    assert not HERE.is_symlink() and not LOCAL.is_symlink()
    original = LOCAL / 'frozen/research/review_engine_fix_r1/review.py'
    if not original.is_file():
        original = ROOT / 'research/review_engine_fix_r1/review.py'
    text = original.read_text()
    replacements = {
        "NEW = Path('firmware/engine_fix_r1')": "NEW = Path('firmware/engine_fix_r2')",
        'review_engine_fix_r1/.gitignore:1:local/': 'review_engine_fix_r2/.gitignore:1:local/',
        'full-r2': 'full-r3',
        '6ba63d294e86a591e5752d7c237cf7b88aeda1f3b0b51064439709b5feed9cc0':
            '0f49317ac8b2609cb268a7951ec263959e8a2fedef818c7d9dd8e530796c7885',
        'len(blob) == 59328': 'len(blob) == 59704',
        '== 11392': '== 11172',
        '(1104,7504,6144,256,608,1968,652,8)': '(1104,7504,6144,256,608,1968,656,8)',
        'LAYOUT M32R temporary=652 bytes;': 'LAYOUT M32R PnGxts=656 workspace=912 bytes;',
        "('full_r2',final)": "('full_r3',final)",
    }
    for before, after in replacements.items():
        assert before in text, before
        text = text.replace(before, after)
    adapted = LOCAL / 'reused-r1.py'
    adapted.write_text(text)
    (LOCAL / 'reuse.patch').write_text(''.join(difflib.unified_diff(
        original.read_text().splitlines(True), text.splitlines(True),
        fromfile=str(original.relative_to(ROOT)), tofile='local/reused-r1.py')))
    spec = importlib.util.spec_from_file_location('audit_base', adapted)
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    base.HERE, base.ROOT, base.LOCAL, base.FROZEN = HERE, ROOT, LOCAL, LOCAL / 'frozen'
    base.OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
    base.guard()
    return base


def freeze(b):
    original_inputs = b.inputs
    def inputs():
        paths = set(original_inputs())
        for base in (PRIOR, CURRENT):
            for folder, dirs, files in os.walk(ROOT / base):
                dirs[:] = [x for x in dirs if x not in ('local', 'build', '__pycache__', '.git')]
                paths.update(Path(folder) / x for x in files)
        for base, variant in ((PRIOR, 'full-r2'), (CURRENT, 'full-r3'), (CURRENT, 'full-r3-prev')):
            paths.update(p for p in (ROOT / base / 'local/product/candidates' / variant).rglob('*') if p.is_file())
        for rel in (
            'research/review_engine_fix_r1/review.py', 'research/review_engine_fix_r1/REPORT.md',
            'research/review_engine_fix_r1/local/review_cases.inc.c',
            'research/review_engine_fix_r1/local/adversarial-results.json',
            'firmware/engine_fix_r2/local/product/resident-trust.c',
            'firmware/engine_fix_r2/local/artifact-inspection.json',
            'firmware/engine_fix_r2/local/test-summary.json',
            'firmware/engine_fix_r2/local/revision-acceptance.json',
            'firmware/engine_fix_r2/local/remaining-risk.json',
        ):
            paths.add(ROOT / rel)
        return sorted(p for p in paths if p.is_file() and not p.is_symlink())
    b.inputs = inputs
    b.freeze()


def diff(b):
    before, after = b.FROZEN / PRIOR, b.FROZEN / CURRENT
    rows, patch = [], []
    for sub in ('engine_services', 'containers/product'):
        a, c = before / sub, after / sub
        names = sorted({p.relative_to(a) for p in a.rglob('*') if p.is_file()} |
                       {p.relative_to(c) for p in c.rglob('*') if p.is_file()})
        for name in names:
            x, y = a / name, c / name
            if x.is_file() and y.is_file() and x.read_bytes() == y.read_bytes():
                continue
            rows.append(dict(path=str(Path(sub) / name), before=b.sha(x) if x.exists() else None,
                             after=b.sha(y) if y.exists() else None))
            patch.extend(difflib.unified_diff(x.read_text().splitlines(True) if x.exists() else [],
                y.read_text().splitlines(True) if y.exists() else [],
                fromfile=str(PRIOR / sub / name), tofile=str(CURRENT / sub / name)))
    b.save('source-differences.json', rows)
    (LOCAL / 'source-differences.patch').write_text(''.join(patch))
    print('DIFF', len(rows), 'files')


def revisions(b):
    host = LOCAL / 'host-r2/host'
    assert host.is_file(), 'Run suite first'
    folder = b.FROZEN / CURRENT / 'local/product/candidates'
    rows = []
    for case in REVISION_CASES:
        for unit in range(3):
            a, c = folder / 'full-r3-prev', folder / 'full-r3'
            label = f'revision-{case}-{unit}'
            p = b.run([host, case, unit, a / 'GXRCE.DAT', c / 'GXRCE.DAT', c / 'trust.bin',
                       a / 'effective-rows.bin', c / 'effective-rows.bin'], label)
            rows.append(dict(case=case, unit=unit, returncode=p.returncode,
                             log='logs/' + label + '.log', limitation=case == 'r3-gxts-persistent-minus1'))
    b.save('revision-results.json', rows)
    print('REVISION', len(rows), 'cases; failures', sum(x['returncode'] != 0 for x in rows))
    assert all(x['returncode'] == 0 for x in rows)


def driver(b):
    product = b.FROZEN / CURRENT / 'containers/product'
    text = (product / 'host_checks.c').read_text()
    text = text.replace('#include "../../local/product/entries.h"',
                        '#include "' + str(b.FROZEN / CURRENT / 'local/product/entries.h') + '"')
    text = text.replace('#include "revision_checks.inc.c"',
                        '#include "revision_checks.inc.c"\n#include "' + str(LOCAL / 'review_cases.inc.c') + '"')
    text = text.replace('if(revision_checks()){}else', 'if(audit_cases()){}else if(revision_checks()){}else')
    path = LOCAL / 'audit-host.c'
    path.write_text(text)
    (LOCAL / 'audit-driver.patch').write_text(''.join(difflib.unified_diff(
        (product / 'host_checks.c').read_text().splitlines(True), text.splitlines(True),
        fromfile='frozen/product/host_checks.c', tofile='local/audit-host.c')))
    return b.compile_host(driver=path, label='audit')


def audit(b):
    host = driver(b)
    cases = json.loads((LOCAL / 'audit-cases.json').read_text())
    folder = b.FROZEN / CURRENT / 'local/product/candidates'
    a, c = folder / 'full-r3-prev', folder / 'full-r3'
    rows = []
    for case in cases:
        for unit in range(3):
            label = f'audit-{case}-{unit}'
            old = b.FROZEN / PRIOR / 'local/product/candidates/full-r2' if 'equal' in case else a
            p = b.run([host, case, unit, old / 'GXRCE.DAT', c / 'GXRCE.DAT', c / 'trust.bin',
                       old / 'effective-rows.bin', c / 'effective-rows.bin'], label)
            rows.append(dict(case=case, unit=unit, returncode=p.returncode, log='logs/' + label + '.log',
                             output=p.stdout + p.stderr))
    b.save('audit-results.json', rows)
    print('AUDIT', len(rows), 'cases; harness failures', sum(x['returncode'] != 0 for x in rows))
    assert all(x['returncode'] == 0 for x in rows)


def data(b):
    b.data()
    final = b.FROZEN / CURRENT / 'local/product/candidates/full-r3'
    prior = b.FROZEN / PRIOR / 'local/product/candidates/full-r2'
    p = b.run([LOCAL / 'data/frozen-v32', prior / 'GXRCE.DAT', prior / 'trust.bin'], 'prior-full-r2-vectors', 0)
    q = b.run([LOCAL / 'data/frozen-v32', final / 'GXRCE.DAT', final / 'trust.bin'], 'current-full-r3-vectors', 0)
    assert p.stdout == q.stdout
    b.save('incremental-data.json', dict(entries_equal=48, GXTS_bindings_equal=48, GXTS_default_wire_equal=48))
    print('DATA incremental full-r2/full-r3: all 48 entries, bindings and GXTS bytes identical')


def static(b):
    import re
    import struct
    import zlib
    reader = b.module(b.FROZEN / 'firmware/stage2l_switch/tools/build.py', 'review_elf_reader')
    checks = {}
    for label, elfpath, section in (
        ('engine', b.FROZEN / CURRENT / 'local/product/candidates/full-r3/engine.elf', '.engine'),
        ('resident', b.FROZEN / b.OLD / 'local/resident/build/resident.elf', '.payload'),
        ('stage2l', b.FROZEN / 'firmware/stage2l_switch/build/payload.elf', '.payload'),
    ):
        elf = reader.Elf(elfpath)
        sec = next(s for s in elf.sections if s['name'] == section)
        raw, covered, lines = elf.content(sec), set(), 0
        for line in (LOCAL / 'logs' / (label + '-disassembly.log')).read_text().splitlines():
            m = re.match(r'^\s*([0-9a-f]+):\t((?:[0-9a-f]{2} ){1,8})\s*\t', line)
            if not m: continue
            address, encoded = int(m[1], 16), bytes.fromhex(m[2])
            off = address - sec['va']
            if off < 0 or off + len(encoded) > len(raw): continue
            assert raw[off:off + len(encoded)] == encoded, (label, line)
            covered.update(range(off, off + len(encoded)))
            lines += 1
        checks[label] = dict(instruction_lines=lines, bytes_matched=len(covered),
                             section_bytes=len(raw), all_listed_bytes_equal=True)
    b.save('disassembly-byte-checks.json', checks)
    log = (LOCAL / 'logs/engine-disassembly.log').read_text().splitlines()
    for label, start, end in (('release', 0x1670, 0x1754), ('session-work-free', 0xae38, 0xaf04),
                              ('install-release', 0x625c, 0x628c)):
        selected = []
        for line in log:
            m = re.match(r'^\s*([0-9a-f]+):', line)
            if m and start <= int(m[1], 16) < end: selected.append(line)
        (LOCAL / 'logs' / ('m32r-' + label + '.log')).write_text('\n'.join(selected) + '\n')
    rb = b.module(b.FROZEN / b.OLD / 'resident/build.py', 'target_flags')
    gcc = ROOT / 'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'
    source, obj = LOCAL / 'actual-workspace-layout.c', LOCAL / 'actual-workspace-layout.o'
    source.write_text('#include "' + str(b.FROZEN / CURRENT / 'containers/product/adapter.c') +
        '"\nconst uint32_t actual_layout[]={sizeof(SessionWork),sizeof(PnGxts),sizeof(Integrated),'
        'offsetof(Integrated,panel),offsetof(Integrated,glyph),offsetof(Integrated,labels),'
        'offsetof(Integrated,refs),offsetof(Integrated,details),offsetof(Integrated,workspace),sizeof(PnPanel)};\n')
    b.run([gcc, *rb.FLAGS, '-mmodel=medium', '-DPN_CORE_HEADER="../core/eng_core.h"',
           '-I', b.FROZEN / b.OLD / 'resident', '-c', source, '-o', obj], 'actual-workspace-layout', 0)
    values = struct.unpack('>10I', b.symbol(reader.Elf(obj), 'actual_layout'))
    assert values[:3] == (912, 656, 3700)
    b.save('actual-workspace-layout.json', dict(zip(('SessionWork', 'PnGxts', 'Integrated',
        'panel_offset', 'glyph_offset', 'labels_offset', 'refs_offset', 'details_offset',
        'workspace_info_offset', 'PnPanel'), values)))
    out = LOCAL / 'fixtures'
    out.mkdir(exist_ok=True)
    fixtures = []
    for label, variant, generation in (
        ('newer-valid-106', CURRENT / 'local/product/candidates/full-r3', 106),
        ('equal-different-valid-105', PRIOR / 'local/product/candidates/full-r2', 105),
    ):
        blob = bytearray((b.FROZEN / variant / 'GXRCE.DAT').read_bytes())
        blob[28:32] = generation.to_bytes(4, 'big')
        blob[20:24] = bytes(4)
        blob[20:24] = (zlib.crc32(blob[:256]) & 0xffffffff).to_bytes(4, 'big')
        path = out / (label + '.DAT')
        path.write_bytes(blob)
        for unit in ('jlaunch', 'qlaunch', 'l08firm'):
            b.run([LOCAL / 'data/validate-frozen-v32', path, b.FROZEN / CURRENT /
                   'local/product/candidates/full-r3/trust.bin', unit], label + '-' + unit, 0)
        fixtures.append(dict(label=label, sha256=b.sha(path), generation=generation,
                             full_frozen_validator_units=3, generated_not_camera_readback=True))
    b.save('counterexample-fixtures.json', fixtures)
    print('STATIC actual M32R workspace=912; disassembly bytes match; 6 frozen-validator fixture checks pass')


def finalize(b):
    b.scope()
    text = (HERE / 'REPORT.md').read_text()
    assert text.splitlines()[0] in ('可以上卡试用', '修改后可以', '不可以')
    import re
    links = re.findall(r'\]\(([^)]+)\)', text)
    assert all(x in ('SHA256SUMS', 'local/delivery-validation.json') or
               (HERE / x.split('#')[0]).is_file() for x in links)
    groups = {}
    for name in ('suite', 'revision', 'audit'):
        rows = json.loads((LOCAL / (name + '-results.json')).read_text())
        assert all(x['returncode'] == 0 for x in rows)
        groups[name] = len(rows)
    audit_rows = json.loads((LOCAL / 'audit-results.json').read_text())
    counterexamples = [x for x in audit_rows if 'COUNTEREXAMPLE' in x['output']]
    revision_rows = json.loads((LOCAL / 'revision-results.json').read_text())
    limitations = [x for x in revision_rows if x['limitation']]
    safe = groups['suite'] + groups['revision'] - len(limitations) + groups['audit'] - len(counterexamples)
    assert len(counterexamples) == 15 and len(limitations) == 3 and safe == 345
    b.save('delivery-validation.json', dict(verdict=text.splitlines()[0], groups=groups,
           links_valid=len(links), camera_acceptance=False, source_mutations=False,
           behavioral_safety_passes=safe, engine_counterexamples=len(counterexamples),
           accepted_GXTS_limitations=len(limitations)))
    files = sorted(p for p in HERE.rglob('*') if p.is_file() and p != HERE / 'SHA256SUMS')
    assert not any(p.is_symlink() for p in files)
    manifest = HERE / 'SHA256SUMS'
    manifest.write_text(''.join(b.sha(p) + '  ' + str(p.relative_to(HERE)) + '\n' for p in files))
    for line in manifest.read_text().splitlines():
        digest, name = line.split('  ', 1)
        assert b.sha(HERE / name) == digest
    assert all((HERE / x.split('#')[0]).is_file() for x in links)
    print('DELIVERY', len(files), 'hashes checked')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('freeze', 'inspect', 'layout', 'suite', 'revisions', 'audit', 'data', 'recovery', 'static', 'scope', 'finalize'))
    args = parser.parse_args()
    b = load_base()
    if args.action == 'freeze': freeze(b)
    elif args.action == 'inspect': diff(b); b.artifacts()
    elif args.action == 'layout': b.layout()
    elif args.action == 'suite': b.suite()
    elif args.action == 'revisions': revisions(b)
    elif args.action == 'audit': audit(b)
    elif args.action == 'data': data(b)
    elif args.action == 'recovery': b.recovery()
    elif args.action == 'static': static(b)
    elif args.action == 'scope': b.scope()
    elif args.action == 'finalize': finalize(b)
