"""Seal original identities and unpack the exact installed MOUNT records, read-only."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C


def main():
    C.admit('inventory')
    C.numerical()
    C.sys.addaudithook(C.fence)
    assert C.sha(C.DAT) == C.DAT_SHA
    D = C.module('lunch_dat_format', C.ROOT / 'research/v39_g153/dat_format.py')
    raw = C.DAT.read_bytes()
    sections = D.sections(raw)
    fx = D.strict_effects(raw)
    assert D.u32(raw, 28) == 157
    bank = []
    def add(name, kind, entry, extra=None):
        slug = ''.join(c if c.isascii() and c.isalnum() else '_' for c in name)
        p = C.LOCAL / 'records' / (slug + '.record552')
        p.parent.mkdir(exist_ok=True)
        assert len(entry) == 552 and D.refresh_entry(entry) == entry
        p.write_bytes(entry)
        bank.append(dict(name=name, kind=kind, record=str(p), sha256=C.sha(p),
                         slot=entry[0], flags=entry[1], **(extra or {})))
    names = ('01 GRPos', '02 GRNeg', '03 HC BW', '04 Std', '05 F-CC', '06 F-CN', '07 L-Chr', '08 L-Viv')
    for slot, name in enumerate(names, 1):
        add(name, 'builtin', D.expand(raw, 2, slot))
    area, _ = D.effect_area(raw)
    for i in range(D.u16(raw, area + 10)):
        desc = raw[area+32+i*32:area+64+i*32]
        if desc[18] & 4:
            add(desc[20:32].split(b'\0')[0].decode('ascii'), 'look', D.expand_effect(raw, i), dict(descriptor_index=i))
    # Users are knob requests on base records, decoded with the same frozen kv3 table.
    sys.path.insert(0, str(C.SNAP))
    from gxr_studio.camdata import knob_table
    from gxr_studio.engine import menu, knobs
    meta_at, meta_len = sections[6]
    tail = raw[meta_at:meta_at+meta_len]
    ext = tail[1408:1408+1984]
    assert ext[:8] == b'GXUI124\0'
    kv3 = tail[1408+1984:]
    assert len(kv3) == 7904
    table = knob_table.read(kv3, menu.load(), mount_knobs_from_50mm=True)
    users = []
    for i in range(D.u16(ext, 24)):
        at = 1216 + i*24
        base = ext[at]
        name = ext[at+2:at+10].split(b'\0')[0].decode('ascii')
        levels = list(C.struct.unpack_from('11b', ext, at+10))
        rec = next(r for r in table['recipes'] if r['unit'] == 2 and r['slot'] == base)
        items = table['items'][rec['first_item']:rec['first_item']+rec['item_count']]
        values = [it['default_level'] for it in items]
        controls = {table['controls'][it['control']]['name']:j for j, it in enumerate(items)}
        for k, v in zip(('contrast', 'highlight', 'shadow', 'saturation'), levels[:4]):
            if k in controls:
                values[controls[k]] = v
        request = menu.request(table, 2, base, values)
        entry, _ = knobs.apply(D.expand(raw, 2, 4), D.expand(raw, 2, base), request)
        add('user:' + name, 'user', bytes(entry), dict(base=base, levels=levels))
        users.append(dict(name=name, base=base, levels=levels))
    C.dump('bank.json', dict(dat_sha256=C.DAT_SHA, generation=157, unit='MOUNT', records=bank, users=users))
    metadata = C.metadata_reader()
    inventory = []
    for p in sorted(C.PHOTOS.glob('*.DNG')):
        jpg = p.with_suffix('.JPG')
        assert not p.is_symlink() and not jpg.is_symlink() and jpg.is_file()
        dm, jm = metadata(p), metadata(jpg)
        pair_keys = ('when', 'iso', 'exposure', 'unit', 'selector', 'color_raw13')
        assert all(dm.get(k) == jm.get(k) and dm.get(k) is not None for k in pair_keys), p.stem
        dng = C.Dng(p)
        dm.update(exposure_program=dng.exif.get('program'), exposure_bias=dng.exif.get('bias_ev'))
        dng.release()
        number = int(p.stem[1:])
        group = 'lunch' if number >= 8052063 else 'morning' if number >= 8052052 else 'previous_day'
        inventory.append(dict(id=p.stem, group=group, path=str(p), jpeg=str(jpg), metadata=dm,
                              jpeg_metadata=jm, raw_sha256=C.sha(p), jpeg_sha256=C.sha(jpg),
                              raw_stat=[p.stat().st_size, p.stat().st_mtime_ns],
                              jpeg_stat=[jpg.stat().st_size, jpg.stat().st_mtime_ns]))
    assert len(inventory) == 57
    assert sum(r['group'] == 'lunch' for r in inventory) == 44
    assert sum(r['group'] == 'morning' for r in inventory) == 11
    C.dump('inventory.json', inventory)
    inputs = [C.DAT, C.ROOT / 'research/model_c040_r1/local/calibration/input-map-mount-a12.json',
              C.ROOT / 'research/module_adapt/local/official_parameters.json',
              C.ROOT / 'research/module_adapt/c040.py',
              C.ROOT / 'research/hue_ring/local/ring_model_v2.json',
              C.ROOT / 'research/hue_ring/local/ring_model_v2_iso1600.json',
              C.ROOT / 'artifacts/firmware/gxr-1.51/jlaunch3',
              C.ROOT / 'artifacts/firmware/gxr-1.51/l08firm3',
              C.ROOT / 'research/recipe_redo_r1/inventory.py',
              C.ROOT / 'research/v39_g153/dat_format.py',
              C.ROOT / 'research/color_references/colour_math.py']
    inputs += sorted((C.SNAP / 'gxr_studio/engine').glob('*.py'))
    inputs += sorted((C.SNAP / 'gxr_studio/raw').glob('*.py'))
    inputs += sorted((C.SNAP / 'gxr_studio/lut').glob('*.py'))
    C.dump('inputs.json', dict(created_utc=C.utc(), files=[dict(path=str(p), sha256=C.sha(p)) for p in inputs],
                              photo_files=114, metadata_whitelist_excludes_GPS=True, native_c040=True))
    C.decision('inputs', '冻结 57 对照片和 g157 MOUNT 实际记录',
               '当天 55 对用于分析；昨天两对只核验完整性', 'local/inventory.json; local/bank.json',
               f'{len(bank)} candidate records; 44 lunch + 11 morning')
    from collections import Counter
    today = [r for r in inventory if r['group'] != 'previous_day']
    print(C.json.dumps(dict(pairs=57, candidates=[r['name'] for r in bank], users=users,
                            iso=dict(Counter(r['metadata']['iso'] for r in today)),
                            programs=dict(Counter(r['metadata']['exposure_program'] for r in today)),
                            wb=dict(Counter(r['metadata']['wb_mode'] for r in today)),
                            color_controls=len({tuple(r['metadata']['color_raw13']) for r in today})), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
