"""Read real first-menu snapshots and compare the retained values byte for byte."""
import argparse
import json
from pathlib import Path
import struct
import sys
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from runtime import load_snapshot, snapshot_dat, layout, symbols, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', default='cache-check')
    parser.add_argument('--prefix')
    options = parser.parse_args()
    rows = []
    skipped = []
    profiles = {
        sha((ROOT/'firmware'/package/'GXRCE.DAT').read_bytes()):tree
        for package,tree in [('package_v310_g155b_test','engine_v66_g155b'),
            ('package_v310_g155c_test','engine_v67_g155c'),
            ('package_v310_g155c','engine_v67_g155c')]}
    profiles[sha((ROOT/'firmware/package_v39_g154_test/local/SD_ROOT/GXRCE.DAT').read_bytes())]='engine_v63_g154'
    paths = [HERE/'local/repro-g154-first-menu-first-menu.pkl.z',
        HERE/'local/repro-g155b-first-menu-first-menu.pkl.z',
        *sorted((HERE/'local').glob('*-menu*-first-menu.pkl.z'))]
    paths = sorted(set(paths))
    if options.prefix:paths=[p for p in paths if p.name.startswith(options.prefix)]
    offsets = {}
    for path in paths:
        saved = load_snapshot(path)
        dat = snapshot_dat(saved)
        assert sha(dat) == saved['dat_sha256']
        def raw(at,n):
            for base,data,_ in saved['cpu']['regions']:
                if base<=at and at+n<=base+len(data):return data[at-base:at-base+n]
            raise ValueError(hex(at))
        S=int.from_bytes(raw(0x200c0dac,4),'big')
        retained=raw(S+0xfd4,40)
        unit={'50mm':0,'28mm':1,'mount':2}[saved['unit']]
        if (retained[:4]!=b'GXR2' or retained[4] not in (1,3) or retained[6]!=unit or retained[7]!=1
                or retained[28:36]!=dat[20:28] or zlib.crc32(retained[:36])!=int.from_bytes(retained[36:],'big')):
            skipped.append(dict(snapshot=str(path.relative_to(ROOT)),reason='No valid same-DAT record; this snapshot is not a restored-value case'))
            continue
        if sha(dat) not in profiles:
            skipped.append(dict(snapshot=str(path.relative_to(ROOT)),reason='Archived pre-mode-fix candidate; final cache audit selects only the final SHA'))
            continue
        tree = profiles[sha(dat)]
        engine = ROOT/'firmware'/tree
        release=sha(dat)==sha((ROOT/'firmware/package_v310_g155c/GXRCE.DAT').read_bytes())
        elf = engine/('candidate/local/full-r13/engine.elf' if tree == 'engine_v63_g154' else
            'candidate/local/boot-off/engine.elf' if release else 'candidate/local/boot-on/engine.elf')
        if tree not in offsets:
            offsets[tree] = layout(engine), symbols(elf)
        off, sym = offsets[tree]
        def mem(at, n):
            for base, raw, _ in saved['cpu']['regions']:
                if base <= at and at+n <= base+len(raw):
                    return raw[at-base:at-base+n]
            raise ValueError(hex(at))
        def u(at, n=4):
            return int.from_bytes(mem(at, n), 'big')
        base = u(0x20054770)-int.from_bytes(dat[132:136], 'big')
        def field(name, n):
            return mem(base+sym['n']+off[name], n)
        record = mem(u(0x200c0dac)+0xfd4, 40)
        code = record[5]
        observed = field('n.values', 160)[20*(code-1):20*code] if 1 <= code <= 8 else field('n.ui.saved', 640)[20*(code-0x80):20*(code-0x80+1)] if code >= 0x80 else field('n.ui.levels', 20)
        assert observed == record[8:28]
        if tree != 'engine_v63_g154':
            assert field('n.ui.levels', 20) == record[8:28]
        rows.append(dict(snapshot=str(path.relative_to(ROOT)), sha256=sha(path.read_bytes()),
            dat_sha256=sha(dat), category_code=code, record_levels=list(struct.unpack('>10h', record[8:28])),
            cached_levels=list(struct.unpack('>10h', observed)), exact_20_bytes_equal=True,
            legacy_preselection_only=tree == 'engine_v63_g154'))
    result = dict(status='PASS', layer='模拟器实测快照的只读缓存核对', rows=rows, skipped=skipped, native_state_presets=[])
    target = HERE/'evidence'/(options.name+'.json')
    assert not target.exists()
    target.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(status='PASS', snapshots=len(rows))))


if __name__ == '__main__':
    main()
