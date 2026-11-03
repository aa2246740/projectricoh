"""Retain declared persistent-block variants and test cold record admission."""
import argparse
import json
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from repro_flow import phase
from runtime import sha


def source(case, prefix, override=None):
    name = 'g155c-mount-builtin-exit1-final-S-persistent.bin'
    if case == 'dat-change':
        name = 'repro-g155b-exits-ok-exit-S-persistent.bin'
    elif case == 'zero':
        name = 'g155c-mount-builtin-choose-final-S-persistent.bin'
    original = override.resolve() if override else HERE/'local'/name
    block = bytearray(original.read_bytes())
    if case!='dat-change':
        current=(ROOT/'firmware/package_v310_g155c_test/GXRCE.DAT').read_bytes()
        assert block[0xfd4+28:0xfd4+36]==current[20:28], 'a same-final-DAT manual source is required'
    edits = []
    if case == 'bad-crc':
        block[0xffb] ^= 1
        edits = ['0xffb: record CRC low bit changed']
    elif case == 'not-standard':
        block[0x36e] = 3
        edits = ['0x36e: declared persistent native BW selector 3']
    struct.pack_into('>I', block, 0xffc, sum(struct.unpack('>2046H', block[:0xffc])) & 0xffffffff)
    target = HERE/'local'/(prefix+'-S.bin')
    assert not target.exists()
    target.write_bytes(block)
    row = dict(case=case, source=str(original.relative_to(ROOT)), source_sha256=sha(original.read_bytes()),
        path=str(target.relative_to(ROOT)), sha256=sha(block), edits=edits,
        record=block[0xfd4:0xffc].hex(), unit='28mm' if case == 'cross-unit' else 'mount',
        native_state_presets=[], checksum_only_without_declared_edits=True)
    (HERE/'evidence'/(prefix+'-source.json')).write_text(json.dumps(row, indent=2)+'\n')
    return target


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', choices=('bad-crc', 'cross-unit', 'not-standard', 'dat-change', 'zero'), required=True)
    p.add_argument('--name')
    p.add_argument('--settings-source',type=Path)
    a = p.parse_args()
    prefix = a.name or 'gate-'+a.case
    unit = '28mm' if a.case == 'cross-unit' else 'mount'
    rows = []
    settings = source(a.case, prefix,a.settings_source)
    phase('cold_run.py', ['--name', prefix, '--unit', unit, '--dat', ROOT/'firmware/package_v310_g155c_test/GXRCE.DAT',
        '--settings-source', settings, '--budget', '650000000', '--timeout', '14400'], prefix+'-run', rows)
    detail = json.loads((HERE/'evidence'/(prefix+'-detail.json')).read_text())
    calls = [x for x in detail['calls'] if x['op'] == 257]
    assert len(calls) == 1 and calls[0]['result'] == 1
    outcome = int(calls[0]['reply'][-8:], 16)
    if a.case != 'zero':
        assert outcome == 2 and detail['all_boot_settings_writes'] == []
        assert detail['dirty_settings_writes'] == [] and detail['final']['rpc_state'].get('overlay', {}) == {}
    else:
        assert outcome == 1
        engine = ROOT/'firmware/engine_v67_g155c'
        phase('accept.py', ['--source', HERE/'local'/(prefix+'-session.pkl.z'), '--name', prefix+'-accept',
            '--engine', engine, '--elf', engine/'candidate/local/boot-on/engine.elf'], prefix+'-accept-run', rows)
    result = dict(status='PASS', layer='模拟器实测', case=a.case, phases=rows,
        dat_sha256=detail['dat_sha256'],
        boot_detail=outcome, S_writes=len(detail['all_boot_settings_writes']), native_state_presets=[],
        unit_overlay_bytes=len(detail['final']['rpc_state'].get('overlay', {})))
    (HERE/'evidence'/(prefix+'-result.json')).write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
