"""Render the 35 target definitions for one unit, including all 18 shipped Looks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from entry_codec import predict
import argparse
import hashlib
import types
import zipfile
import signal
from gxr_studio.lut.cube import Cube
from gxr_studio.lut.spaces import Target, matrix, encode, xyz_to_encoded

rt.upstream = types.SimpleNamespace(matrix=matrix, encode=encode, Cube=Cube)
builtin = rt.module('redo_builtin_targets', rt.SOURCE/'research/look_ceiling_r1/prepare_builtin.py')

ALIASES = {'QianXi A': '千禧回声 A', 'QianXi B': '千禧回声 B',
           'Y2K Plady': 'Y2K Plady', 'ARRI 709': 'ARRI Classic709'}
NAMES = {1: 'GRPos', 2: 'GRNeg', 3: 'HC BW', 4: 'Std', 5: 'F-CC', 6: 'F-CN', 7: 'L-Chr', 8: 'L-Viv'}
GROUPS = ('train', 'synthetic', 'photo_iso200', 'photo_other_iso')


def official():
    archive = rt.ROOT/'artifacts/downloads/fuji-luts/gfx-eterna-55-3d-lut-v110.zip'
    result = {}
    with zipfile.ZipFile(archive) as z:
        for slot, style in ((5, 'CLASSIC-CHROME'), (6, 'CLASSIC-Neg.')):
            for variant, folder, size in (('historical', 'F-Log2', 65), ('flog2c', 'F-Log2C', 33)):
                member = next(n for n in z.namelist() if f'/{size}Grid/{folder}/' in n
                    and f'_to_{style}_{size}grid_' in n and n.endswith('.cube'))
                raw = z.read(member)
                digest = hashlib.sha256(raw).hexdigest()
                result[slot, variant] = (Cube.parse(raw.decode('utf-8-sig'), digest),
                    dict(archive=str(archive), archive_sha256=rt.sha(archive), member=member, sha256=digest))
    return result


def fg_input(xyz, c=False):
    # Explicit manufacturer F-Gamut-C primary specification, used only for the
    # separately named C control. Main built-ins retain historical F-Gamut.
    if c:
        constant_file = rt.LOCAL/'target_constants.json'
        if not constant_file.exists():
            import ast
            source = rt.source_copy('research/vlog_alchemy_eval/measure.py')
            definition = next(node for node in ast.parse(source.read_text()).body
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'FGC' for t in node.targets))
            rt.dump(constant_file, dict(fgamut_c_primaries=ast.literal_eval(definition.value),
                source=str(source.relative_to(rt.HERE)), source_sha256=rt.sha(source)))
        xy = np.asarray(rt.read(constant_file)['fgamut_c_primaries'])
        xyzp = np.stack([xy[:, 0]/xy[:, 1], np.ones(3), (1-xy.sum(1))/xy[:, 1]])
        white = np.array([.3127/.3290, 1, (1-.3127-.3290)/.3290])
        mat = xyzp*np.linalg.solve(xyzp, white)[None, :]
    else:
        mat = matrix('rec2020')
    return encode(xyz@np.linalg.inv(mat).T, 'flog2')


def inverse_cache(unit, group, values):
    path = rt.LOCAL/'targets'/unit/('s1rii_'+group+'.npz')
    source = rt.ROOT/'research/huzi_luts/local/artifacts/downloads/vlog-alchemy-20261024/Luts/Panasonic-Standard/Conversion/S1RIIS2V.cube'
    input_sha256 = hashlib.sha256(values['xyz'].tobytes()).hexdigest()
    if path.exists():
        receipt = rt.read(path.with_suffix('.json'))
        assert receipt['input_xyz_sha256'] == input_sha256, 'Stale S1RII cache'
        assert receipt['source_sha256'] == rt.sha(source), 'S1RII source changed'
        if 'cache_sha256' in receipt:
            assert receipt['cache_sha256'] == rt.sha(path), 'S1RII cache bytes changed'
        else:
            receipt.update(cache_sha256=rt.sha(path), cache_first_sealed_utc=rt.utc())
            rt.dump(path.with_suffix('.json'), receipt)
        arrays = rt.arrays(path)
        assert arrays['rgb'].shape == values['xyz'].shape
        assert len(arrays['residual']) == len(values['x'])
        assert all(np.isfinite(v).all() for v in arrays.values())
        return arrays
    inverse_mod = rt.module('redo_s1rii_inverse', rt.source_copy('research/huzi_luts/panasonic.py'))
    inverse = inverse_mod.StandardInverse(Cube.read(source))
    rows, errors = [], []
    for start in range(0, len(values['x']), 512):
        rgb, error = inverse.invert(xyz_to_encoded(values['xyz'][start:start+512], 'vlog'))
        rows.append(rgb*255)
        errors.append(error)
    arrays = dict(rgb=np.vstack(rows) if rows else np.empty((0, 3)),
                  residual=np.concatenate(errors) if errors else np.empty(0))
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)
    rt.dump(path.with_suffix('.json'), dict(source=str(source), source_sha256=rt.sha(source),
        cache_sha256=rt.sha(path),
        group=group, samples=len(values['x']), residual=rt.stats(arrays['residual']),
        input_xyz_sha256=input_sha256,
        unsupported_fraction=float((arrays['residual']>1e-3).mean()) if len(values['x']) else None,
        included_without_filtering_by_residual=True))
    print('S1RII inverse', unit, group, len(values['x']), flush=True)
    return arrays


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--unit', choices=('a12-50', 'a12-28', 'mount-a12'), required=True)
    ap.add_argument('--indices', default='0:35')
    ap.add_argument('--inverse-only', choices=GROUPS)
    args = ap.parse_args()
    ui = ('a12-50', 'a12-28', 'mount-a12').index(args.unit)
    lo, hi = map(int, args.indices.split(':'))
    groups = {key: rt.arrays(rt.LOCAL/'inputs'/args.unit/(key+'.npz')) for key in GROUPS}
    output = rt.LOCAL/'targets'/args.unit
    output.mkdir(parents=True, exist_ok=True)
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('Target preparation exceeded 25 minute budget')))
    signal.alarm(1500)
    if args.inverse_only:
        inverse_cache(args.unit, args.inverse_only, groups[args.inverse_only])
        return
    camera = rt.Camera(ui)
    stock = rt.release_dat().entry_of(ui, 4)
    baseline = {key: predict(stock, values['x'], ui, round_output=False) for key, values in groups.items()}
    transferred = rt.camera_model(ui, transferred=True)
    official_cubes = official() if hi > 31 else {}
    dense = {slot: builtin.DenseTarget(slot) for slot in (1, 2)} if hi > 27 else {}
    inverse = {key: inverse_cache(args.unit, key, values) for key, values in groups.items()} if hi > 33 else {}
    original = rt.ROOT/'artifacts/downloads/huzi-panasonic-std-luts-20261024/original'
    leica = {slot: Cube.read(original/name) for slot, name in ((7, 'Leica Chrome.cube'), (8, 'Leica VIVID.cube'))} if hi > 33 else {}
    shipped = {ALIASES.get(look.name, look.name): look for look in rt.release_dat().looks}
    definitions = []
    for index in range(lo, hi):
        if index < 27:
            old = rt.read(rt.ROOT/f'research/look_ceiling_r1/local/target_{index:02d}.json')
            source = rt.ROOT/old['source']
            assert rt.sha(source) == old['source_sha256']
            target = Target(Cube.read(source), old['input'], old['output'])
            look = shipped.get(old['name'])
            template = look.entry if look else bytes.fromhex(old['entry_hex'])
            meta = dict(index=index, name=old['name'], kind='look', source=str(source),
                source_sha256=old['source_sha256'], input=old['input'], output=old['output'],
                interpretation=old.get('interpretation', 'declared'),
                shipped_in_g154_looks18=look is not None, shipped_name=look.name if look else None,
                current_row_scope='g154 looks18 published row' if look else 'look-ceiling evaluated reference; not in g154 looks18',
                target_scope='original look-ceiling target function')
        else:
            slot = index - 26
            template = rt.release_dat().entry_of(ui, slot)
            meta = dict(index=index, name=f'{slot:02d} {NAMES[slot]}', kind='builtin', builtin_slot=slot,
                shipped_in_g154_looks18=False, current_row_scope='g154 looks18 built-in published row',
                target_scope='historical F-Log2/F-Gamut 65-grid' if slot in (5, 6) else 'look-ceiling declared target')
        meta.update(unit=args.unit, camera_ui=ui, template_hex=template.hex(), template_sha256=hashlib.sha256(template).hexdigest(),
            release_dat_sha256=rt.sha(rt.SOURCE/'firmware/package_v39_g154_looks18_test/local/SD_ROOT/GXRCE.DAT'),
            main_level=0 if ui == 2 else 1, S_mode='04 Standard',
            retained_current_row_for_comparison=True, no_dat_built=True,
            input_file_sha256={key: rt.sha(rt.LOCAL/'inputs'/args.unit/(key+'.npz')) for key in GROUPS})
        scores, coverage = {}, {}
        for group, values in groups.items():
            if not len(values['x']):
                coverage[group] = dict(total=0, supported=0)
                scores[group] = None
                continue
            x, xyz, raw = values['x'], values['xyz'], values['raw_codes']
            base = baseline[group]
            valid = np.ones(len(x), bool)
            details = {}
            if index < 27:
                if meta['interpretation'] == 'scene':
                    want = np.clip(target.cube.apply(xyz_to_encoded(xyz, 'srgb')), 0, 1)*255
                else:
                    want = target.render(base, xyz)
            elif slot in (1, 2):
                want, valid, details = dense[slot](raw, xyz, base)
            elif slot == 3:
                want, valid, details = builtin.hc_target(raw, xyz, base)
            elif slot == 4:
                want = base.copy()
            elif slot in (5, 6):
                cube, info = official_cubes[slot, 'historical']
                want = cube.apply(fg_input(xyz))*255
                meta['official_lut'] = info
                c_cube, c_info = official_cubes[slot, 'flog2c']
                control = c_cube.apply(fg_input(xyz, True))*255
                np.savez_compressed(output/f'{index:02d}_{group}_flog2c_control.npz', want=control[valid])
                meta['flog2c_control_lut'] = c_info
            else:
                ib = inverse[group]['rgb']
                want = np.clip(.3*ib+.7*leica[slot].apply(ib/255)*255, 0, 255)
                details['inverse_residual'] = rt.stats(inverse[group]['residual'])
            current = predict(template, x, ui)
            old_pred = np.rint(transferred.predict(template, raw, bw_chroma='zero'))
            values_out = {k: v[valid] for k, v in values.items()}
            values_out.update(base=base[valid], want=want[valid], current=current[valid], legacy_transferred=old_pred[valid])
            assert np.isfinite(want).all()
            np.savez_compressed(output/f'{index:02d}_{group}.npz', **values_out)
            scores[group] = dict(current=rt.score(base[valid], current[valid], want[valid]),
                legacy_transferred_same_target=rt.score(base[valid], old_pred[valid], want[valid]))
            coverage[group] = dict(total=len(x), supported=int(valid.sum()), support_mask_fixed_before_fit=True, **details)
        meta.update(scores=scores, coverage=coverage)
        rt.dump(output/f'{index:02d}.json', meta)
        definitions.append({k: v for k, v in meta.items() if k not in ('template_hex', 'scores')})
        print('target', args.unit, index, meta['name'], 'photo ISO200', coverage['photo_iso200'], flush=True)
    rt.dump(output/f'manifest_{lo:02d}_{hi:02d}.json', definitions)


if __name__ == '__main__':
    main()
