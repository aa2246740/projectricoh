"""Score observed JPEGs against preregistered targets, retaining both target conventions."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import types
import zipfile

ALIASES = {'QianXi A': '千禧回声 A', 'QianXi B': '千禧回声 B', 'ARRI 709': 'ARRI Classic709'}


class Targets:
    def __init__(self):
        self.old = {}
        self.cache = {}
        self.provenance = {}
        self.films = {r['name']: r for r in C.read(C.ROOT / 'research/film_looks_r2/local/catalog.json')['films']}
        for index in range(27):
            row = C.read(C.ROOT / 'research/look_ceiling_r1/local' / f'target_{index:02d}.json')
            self.old[row['name']] = row
        # Reuse only pure target definitions, without importing historical load1 gates.
        source = C.ROOT / 'research/recipe_redo_r1/local/source/research/look_ceiling_r1/prepare_builtin.py'
        tree = C.ast.parse(source.read_text())
        nodes = [n for n in tree.body if isinstance(n, (C.ast.ClassDef, C.ast.FunctionDef)) and n.name in
                 ('arrays', 'lab_to_rgb', 'relative', 'DenseTarget', 'hc_target')]
        from scipy.interpolate import LinearNDInterpolator
        from scipy.spatial import cKDTree
        from gxr_studio.lut.spaces import encode, matrix
        rt = types.SimpleNamespace(read=C.read, lab_from_codes=C.fs.lab_from_codes)
        scope = dict(np=C.np, ROOT=C.ROOT, rt=rt, upstream=types.SimpleNamespace(encode=encode, matrix=matrix),
                     LinearNDInterpolator=LinearNDInterpolator, cKDTree=cKDTree)
        exec(compile(C.ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), scope)
        self.builtin = types.SimpleNamespace(**scope)
        self.matrix = matrix
        self.encode = encode

    def cube(self, path, digest=None):
        path = Path(path)
        if not path.is_absolute():
            path = C.ROOT / path
        key = str(path)
        if key not in self.cache:
            if digest:
                assert C.sha(path) == digest, 'Target source drift: ' + str(path)
            self.cache[key] = C.Cube.read(path)
            self.provenance[key] = C.sha(path)
        return self.cache[key]

    def fuji(self, style):
        key = 'fuji:' + style
        if key not in self.cache:
            archive = C.ROOT / 'artifacts/downloads/fuji-luts/gfx-eterna-55-3d-lut-v110.zip'
            with zipfile.ZipFile(archive) as z:
                member = next(n for n in z.namelist() if '/65Grid/F-Log2/' in n and
                              f'_to_{style}_65grid_' in n and n.endswith('.cube'))
                raw = z.read(member)
            self.cache[key] = C.Cube.parse(raw.decode('utf-8-sig'), C.hashlib.sha256(raw).hexdigest())
            self.provenance[str(archive) + ':' + member] = C.hashlib.sha256(raw).hexdigest()
        return self.cache[key]

    def fg(self, xyz):
        return self.encode(xyz @ C.np.linalg.inv(self.matrix('rec2020')).T, 'flog2')

    def old_target(self, name, raw, xyz, base):
        np = C.np
        name = ALIASES.get(name, name)
        valid = np.ones(len(raw), bool)
        details = {}
        if name.startswith('user:'):
            return None, valid, dict(reason='user knob variant has no separately frozen style target')
        if name[:2].isdigit() and len(name) > 2 and name[2] == ' ':
            slot = int(name[:2])
            if slot in (1, 2):
                key = 'dense:' + str(slot)
                if key not in self.cache:
                    self.cache[key] = self.builtin.DenseTarget(slot)
                want, valid, details = self.cache[key](raw, xyz, base)
                self.provenance[str(self.cache[key].source)] = C.sha(self.cache[key].source)
            elif slot == 3:
                want, valid, details = self.builtin.hc_target(raw, xyz, base)
            elif slot == 4:
                want = base.copy()
            elif slot in (5, 6):
                style = 'CLASSIC-CHROME' if slot == 5 else 'CLASSIC-Neg.'
                want = self.fuji(style).apply(self.fg(xyz))*255
            else:
                key = 's1rii-inverse'
                if key not in self.cache:
                    p = C.ROOT / 'research/recipe_redo_r1/local/source/research/huzi_luts/panasonic.py'
                    m = C.module('lunch_s1rii_inverse', p)
                    path = C.ROOT / 'research/huzi_luts/local/artifacts/downloads/vlog-alchemy-20261024/Luts/Panasonic-Standard/Conversion/S1RIIS2V.cube'
                    self.cache[key] = m.StandardInverse(self.cube(path))
                ib, residual = self.cache[key].invert(C.xyz_to_encoded(xyz, 'vlog'))
                ib *= 255
                p = C.ROOT / 'artifacts/downloads/huzi-panasonic-std-luts-20261024/original' / ('Leica Chrome.cube' if slot == 7 else 'Leica VIVID.cube')
                want = np.clip(.3*ib + .7*self.cube(p).apply(ib/255)*255, 0, 255)
                details = dict(inverse_residual=C.stats(residual), residuals_not_used_to_drop_samples=True)
            return want, valid, details
        old = self.old[name]
        cube = self.cube(old['source'], old['source_sha256'])
        if old.get('interpretation') == 'scene':
            want = np.clip(cube.apply(C.xyz_to_encoded(xyz, 'srgb')), 0, 1)*255
        else:
            want = C.Target(cube, old['input'], old['output']).render(base, xyz)
        return want, valid, dict(target_name=name, interpretation=old.get('interpretation'))

    def current_target(self, name, raw, xyz, base, old):
        np = C.np
        name = ALIASES.get(name, name)
        if name in self.films:
            film = self.films[name]
            cube = self.cube(film['scene']['file'], film['scene']['sha256'])
            want = np.clip(cube.apply(C.xyz_to_encoded(xyz, film['scene_space'])), 0, 1)*255
            return want, dict(target_name=name, interpretation='scene', provider=film['provider'])
        if name == 'Acros':
            return self.fuji('ACROS').apply(self.fg(xyz))*255, dict(target_name='Acros official', interpretation='scene')
        return old, dict(target_name=name, interpretation='unchanged g157 digital target')


def score(actual, predicted, base, want, mask):
    if want is None or not mask.any():
        return None, {}
    a = C.de(actual[mask], want[mask], 'D65')
    p = C.de(predicted[mask], want[mask], 'D65')
    den = C.de(base[mask], want[mask], 'D65')
    median = float(C.np.median(den))
    return dict(actual_target=C.stats(a), predicted_target=C.stats(p), baseline_target=C.stats(den),
                actual_similarity=None if median < .25 else 100*(1-float(C.np.median(a))/median),
                model_similarity=None if median < .25 else 100*(1-float(C.np.median(p))/median),
                denominator_small=median < .25), dict(actual_target=a, predicted_target=p, baseline_target=den)


def main(pid):
    C.admit('targets-' + pid)
    C.numerical()
    C.sys.addaudithook(C.fence)
    np = C.np
    frame = C.LOCAL / 'frames' / pid
    result = C.read(frame / 'result.json')
    with np.load(frame / 'samples.npz', allow_pickle=False) as z:
        v = dict(z)
    bank = C.read(C.LOCAL / 'bank.json')['records']
    target = Targets()
    i04 = next(i for i, r in enumerate(bank) if r['name'] == '04 Std')
    # Targets use held parity only; no target changes / WB fitting / exposure fitting.
    ix = np.flatnonzero(v['held'])
    raw, xyz, base = v['raw_codes'][ix], v['xyz'][ix], v['predictions'][i04, ix]
    actual = v['observed'][ix]
    scores = []
    arrays = {}
    for tag, j in (('best', result['best_index']), ('second', result['second_index'])):
        name = bank[j]['name']
        old, valid, detail = target.old_target(name, raw, xyz, base)
        new, detail2 = target.current_target(name, raw, xyz, base, old)
        pred = v['predictions'][j, ix]
        s0, a0 = score(actual, pred, base, old, valid)
        s1, a1 = score(actual, pred, base, new, valid)
        row = dict(tag=tag, name=name, g157_original_target=s0, film_r2_target=s1,
                   target_details=detail, film_r2_details=detail2,
                   support=dict(total=len(ix), supported=int(valid.sum())))
        scores.append(row)
        for k, a in a0.items():
            arrays[tag + '_old_' + k] = a
        for k, a in a1.items():
            arrays[tag + '_r2_' + k] = a
        if old is not None:
            arrays[tag + '_old_want'] = old
        if new is not None:
            arrays[tag + '_r2_want'] = new
        arrays[tag + '_supported'] = valid
    arrays['held_indices'] = ix
    np.savez_compressed(frame / 'targets.npz', **arrays)
    C.dump(frame / 'targets.json', dict(id=pid, scores=scores, sources=target.provenance,
        metric='D65 CIEDE2000; 100*(1-median(actual,target)/median(predicted04,target))',
        target_sources_fixed_before_this_photo=True, created_utc=C.utc()))
    print(pid, result['best'], scores[0]['film_r2_target'], flush=True)


if __name__ == '__main__':
    main(sys.argv[1])
