#!/usr/bin/env python3
"""Audit packaged bytes, independent data2 validation and source-copy diffs."""
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pi_audit_support', HERE / 'support.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


def main():
    s.preflight()
    out = s.LOCAL / 'audit'
    out.mkdir(exist_ok=True)
    upstream = s.UPSTREAM / 'card_container_v2'
    # The legacy standalone data2 validator has a separate 10 KiB code gate.
    # Only this copied gate changes to the resident's 48 KiB code ceiling.
    gate = out / 'gate.c'
    gate.write_text((upstream / 'gate.c').read_text().replace('v.sections[0].length>10240', 'v.sections[0].length>49152'))
    binary = out / 'data2-validate'
    sources = [upstream / n for n in ('validate.c', 'common.c', 'sha256.c', 'semantic.c', 'api.c')]
    s.run(['clang', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
           '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-I', upstream,
           gate, *sources, '-o', binary], 'data2-validator-compile')
    results = {}
    for name in ('life', 'notice', 'view', 'life-256', 'life-32768'):
        directory = s.LOCAL / ('witness-tiers' if '-' in name else 'candidates') / name
        path = directory / 'GXRCE.DAT'
        raw = path.read_bytes()
        manifest = json.loads((directory / 'manifest.json').read_text())
        assert len(raw) == manifest['file_bytes'] <= 32768
        assert hashlib.sha256(raw).hexdigest() == manifest['sha256']
        assert raw[256:256 + manifest['engine_bytes']] == (s.LOCAL / 'build' / name / 'engine.bin').read_bytes()
        assert struct.unpack_from('>I', raw, 116)[0] == 0
        outputs = {}
        for unit in ('jlaunch', 'qlaunch', 'l08firm'):
            outputs[unit] = s.run([binary, path, directory / 'trust.bin', unit], name + '-data2-' + unit).stdout.strip()
        results[name] = dict(bytes=len(raw), sha256=manifest['sha256'], full_data2_semantics=outputs)
    diffs = {}
    for adapted, original in [('engine.c', 'probes_v2/engine.c'), ('probes.h', 'probes_v2/probes.h'),
                              ('entry.S', 'probes_v2/entry.S'), ('runtime.c', 'probes_v2/runtime.c'),
                              ('decode.py', 'probes_v2/decode.py'), ('pack_model.py', 'card_container_v2/pack.py')]:
        text = ''.join(difflib.unified_diff((s.UPSTREAM / original).read_text().splitlines(True),
                                          (HERE / adapted).read_text().splitlines(True),
                                          fromfile=original, tofile='probes_int/' + adapted))
        (out / (adapted + '.diff')).write_text(text)
        diffs[adapted] = dict(original=original, changed=bool(text), diff='local/audit/' + adapted + '.diff')
    (out / 'gate.c.diff').write_text(''.join(difflib.unified_diff(
        (upstream / 'gate.c').read_text().splitlines(True), gate.read_text().splitlines(True),
        fromfile='card_container_v2/gate.c', tofile='local/audit/gate.c')))
    drift = []
    for item in json.loads((s.LOCAL / 'inputs.json').read_text()):
        current = s.sha(s.ROOT / item['source'])
        if current != item['sha256']:
            drift.append(dict(source=item['source'], frozen_sha256=item['sha256'], live_sha256=current))
    s.save(out / 'commands.json', s.COMMANDS)
    s.save(out / 'summary.json', dict(status='PASS', containers=results, source_diffs=diffs,
                                     legacy_validator_code_limit_relaxed_only_in_local_copy=True,
                                     upstream_drift=drift, camera_acceptance=False))
    print(f'PASS: 5 files, 15 full data2 validations; live input drift={len(drift)}')


if __name__ == '__main__':
    main()
