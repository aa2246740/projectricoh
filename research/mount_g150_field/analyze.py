"""Offline MOUNT g150 measurements. Run one command at a time with nice -n 10.

Only this directory, the named scratch directory, and compare*.jpg in the
capture directory are writable. No subprocesses or network calls are allowed.
"""
import sys
sys.dont_write_bytecode = True
import os
from pathlib import Path
import hashlib
import importlib.util
import json
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAP = ROOT / 'captures/mount-g150-20261101'
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/mount-g150')
for key in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
os.environ['TMPDIR'] = str(TMP)
INPUTS = {}
_checking = False


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def writable(path):
    p = Path(os.path.abspath(path)).resolve()
    return (p.is_relative_to(HERE) or p.is_relative_to(TMP)
            or (p.parent == CAP and p.name.startswith('compare') and p.suffix == '.jpg'))


def audit(event, args):
    global _checking
    if event.startswith('socket.') or event in ('subprocess.Popen', 'os.system', 'os.posix_spawn'):
        raise PermissionError('Offline analysis: process and network calls disabled')
    if event == 'open' and isinstance(args[0], (str, bytes, Path)):
        p = Path(os.path.abspath(os.fsdecode(args[0])))
        if str(p).startswith('/Volumes/') and not p.is_relative_to(Path('/Volumes/Workspace')):
            raise PermissionError('Volume outside allowed input area')
        p = p.resolve()
        if str(p).startswith('/Volumes/') and not p.is_relative_to(Path('/Volumes/Workspace')):
            raise PermissionError('Resolved volume outside allowed input area')
        mode, flags = args[1:3]
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+'))
        writing |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing and not writable(p):
            raise PermissionError('Write outside task area: ' + str(p))
        if not writing and not _checking and p.is_relative_to(ROOT) and not writable(p) and p.is_file():
            rel = str(p.relative_to(ROOT))
            if rel not in INPUTS:
                _checking = True
                try:
                    INPUTS[rel] = sha(p)
                finally:
                    _checking = False
    if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename'):
        for p in args[:2 if event == 'os.rename' else 1]:
            if isinstance(p, (str, bytes, Path)) and not writable(os.fsdecode(p)):
                raise PermissionError('Mutation outside task area: ' + str(p))


sys.addaudithook(audit)
HERE.mkdir(exist_ok=True)
TMP.mkdir(parents=True, exist_ok=True)
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
Image.MAX_IMAGE_PIXELS = None


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def plain(v):
    if isinstance(v, dict): return {str(k): plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)): return [plain(x) for x in v]
    if isinstance(v, np.ndarray): return plain(v.tolist())
    if isinstance(v, np.generic): return plain(v.item())
    if isinstance(v, Path): return str(v)
    if isinstance(v, float) and not np.isfinite(v): return None
    return v


def dump(name, v):
    p = HERE / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plain(v), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def finish(stage):
    changed = [p for p, h in INPUTS.items() if sha(ROOT / p) != h]
    assert not changed, changed
    dump('provenance/' + stage + '.json', dict(inputs=INPUTS, all_inputs_unchanged=True,
         python=sys.version, executable=sys.executable, numpy=np.__version__,
         offline=True, subprocesses=False, write_scope_checked=True))


_models = None


def models():
    global _models
    if _models is not None: return _models
    sys.path.insert(0, str(ROOT / 'research/recipe_iso_unit_drift'))
    import mount_model as mm
    for key in ('OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'OMP_NUM_THREADS'):
        os.environ[key] = '1'
    os.environ['TMPDIR'] = str(TMP)
    new = mm.g137_modules('firmware/package_v38_g150_test/local/SD_ROOT/GXRCE.DAT')
    old = mm.g137_modules()
    m = mm.UnitModel('mount', iso=200)
    fifty = mm.UnitModel('50mm', iso=200)
    cal = json.loads((ROOT / 'research/mount_calib_r1/local/folds/full/calibration.json').read_text())
    _models = dict(mm=mm, m=m, fifty=fifty, cal=cal, new=new, old=old,
                   mount=mm.entries448(new['l08firm']),
                   oldmount=mm.entries448(old['l08firm']),
                   e50=mm.entries448(new['jlaunch']))
    users = HERE / 'user_rows.json'
    if users.exists():
        import struct
        for name, item in json.loads(users.read_text())['entries'].items():
            p = (HERE / item['file']).read_bytes()
            rows = tuple(p[o:o+n] for o, n in zip(mm.SRC.ROW_OFFSETS, mm.SRC.ROW_BYTES))
            unit_kind = 'e50' if item.get('unit') == '50mm' else 'mount'
            stock = _models[unit_kind]['04']['rows']
            ent = dict(slot=p[0], mask=p[1], rows=rows,
                       control=struct.unpack_from('>H', p, mm.SRC.CONTROL_OFFSET)[0],
                       written=tuple(rows[r] if not bit or p[1] & bit else stock[r]
                                     for r, bit in enumerate(mm.SRC.ROW_BITS)))
            _models['user:' + name] = {**_models[unit_kind], f'{p[0]:02d}': ent}
    return _models


def predict(slot, x, kind='mount'):
    b = models()
    m = b['fifty'] if kind == 'e50' or kind.endswith('@50mm') else b['m']
    m.base.entries = b[kind]
    if slot == '03':
        row = m.mm.MatrixRow.from_bytes(m.base.entries[slot]['written'][3][:28])
        return np.clip(np.repeat(row.apply(m.pre(slot, x))[0][:, None], 3, 1), 0, 255)
    return m.predict(slot, x)


def lab(rgb): return models()['m'].fs.lab_from_codes(np.asarray(rgb, float).reshape(-1, 3))
def de(a, b): return models()['m'].fs.delta_e00(lab(a), lab(b))
def hue(L): return np.degrees(np.arctan2(L[:, 2], L[:, 1])) % 360
def chroma(L): return np.hypot(L[:, 1], L[:, 2])
def dh(a, b): return (a - b + 180) % 360 - 180


def metrics(observed, predicted, mask=None):
    if mask is None: mask = np.ones(len(observed), bool)
    a, b = lab(observed)[mask], lab(predicted)[mask]
    if not len(a): return dict(n=0)
    e = models()['m'].fs.delta_e00(a, b)
    goodh = (chroma(a) > 8) & (chroma(b) > 8)
    return dict(n=len(a), de00_median=np.median(e), de00_p90=np.percentile(e, 90),
                dL_median=np.median(a[:, 0] - b[:, 0]),
                dC_median=np.median(chroma(a) - chroma(b)),
                dhue_median=np.median(dh(hue(a)[goodh], hue(b)[goodh])) if goodh.any() else None,
                hue_n=goodh.sum())


_dng = None


def dng_module():
    global _dng
    if _dng is None:
        _dng = load('field_dng', 'research/color_table_fit/dng_scene.py')
        sess = load('field_session', 'research/chart_session_20261024/session_runtime.py')
        sess.patch_tiff(_dng.analyze_capture().Tiff)
    return _dng


def open_frame(stem):
    dm = dng_module()
    d = dm.Dng(CAP / (stem + '.DNG'))
    jpg = CAP / (stem + '.JPG')
    with Image.open(jpg) as im:
        rgb = np.asarray(im.convert('RGB'))
        orientation = im.getexif().get(274, 1)
        ex = im.getexif().get_ifd(34665)
    t = dm.analyze_capture().Tiff(d.data)
    root = t.ifd(t.root)
    exif = t.ifd(root[34665]['value'][0])
    note = t.ifd(exif[37500]['offset'] + 8, '>')
    rec = note[0x1001]['raw']
    meta = dict(frame=stem, iso=ex.get(34855), shutter_s=float(ex.get(33434)),
                white_balance=ex.get(41987), date=str(ex.get(36867)),
                iso_code=rec[0x27], selector=rec[0x28], raw13=list(rec[0x31:0x34] + rec[0x78:0x82]),
                as_shot_neutral=d.as_shot_neutral, orientation=orientation,
                raw_size=[d.width, d.height], jpeg_size=list(rgb.shape[1::-1]),
                color_space=ex.get(40961), maker_record_hex=rec.hex())
    h, w = rgb.shape[:2]
    mapping = dm.RawMap(d, (w, h), orientation)
    ver = dm.verify_mapping(d, rgb, mapping)
    if ver.get('ok') and max(abs(v) for v in ver['suggested_integer_offset_xy']) <= 8:
        mapping = dm.RawMap(d, (w, h), orientation, ver['suggested_integer_offset_xy'])
    meta['mapping'] = {k: v for k, v in ver.items() if k != 'tiles'}
    return rgb, d, mapping, meta


def sample_blocks(rgb, d, mapping, centers, half=6):
    yy, xx = np.meshgrid(np.arange(-half, half), np.arange(-half, half), indexing='ij')
    xs = centers[:, 0, None] + xx.ravel()
    ys = centers[:, 1, None] + yy.ravel()
    blocks = rgb[ys, xs].astype(float)
    observed, sd = blocks.mean(1), blocks.std(1)
    cy, cx = mapping.pixels(ys, xs)
    y0, x0, _, _ = d.crop_window()
    px = d.normalised_at(cy + y0, cx + x0)
    cfa = d.cfa_at(cy + y0, cx + x0)
    raw = np.column_stack([np.sum(np.where(cfa == k, px, 0), 1) / np.maximum(np.sum(cfa == k, 1), 1) for k in range(3)])
    rawsd = np.column_stack([np.sqrt(np.sum(np.where(cfa == k, (px - raw[:, k, None]) ** 2, 0), 1) / np.maximum(np.sum(cfa == k, 1), 1)) for k in range(3)])
    rawmax = np.column_stack([np.max(np.where(cfa == k, px, -1), 1) for k in range(3)])
    wb = raw / d.as_shot_neutral
    b = models()
    x = b['mm'].calibrate.apply_calibration(wb, b['cal'])
    valid = ((rawmax < .98).all(1) & (raw > .0005).all(1) & (observed > 3).all(1)
             & (observed < 252).all(1) & (sd.max(1) < 10) & (rawsd.max(1) < .025))
    return dict(x=x, jpeg=observed, raw=raw, raw_wb=wb, valid=valid, rawsd=rawsd,
                rawmax=rawmax, jsd=sd, centers=centers, size=np.array(rgb.shape[1::-1]))


def inventory():
    expected = {}
    for line in (CAP / 'SHA256SUMS').read_text().splitlines():
        h, name = line.split(None, 1)
        p = CAP / Path(name.strip().lstrip('*')).name
        expected[p.name] = dict(expected=h, actual=sha(p))
    assert len(expected) == 32 and all(v['actual'] == v['expected'] for v in expected.values())
    b = models()
    rawhash = sha(ROOT / 'firmware/package_v38_g150_test/local/SD_ROOT/GXRCE.DAT')
    assert rawhash == '68418fe71744c0fabd8dde7fcb88782631a71767521804b0cf580ebcbd4252c8'
    rows = {}
    for slot in range(1, 9):
        a = b['new']['l08firm']['entries'][slot]
        c = b['new']['jlaunch']['entries'][slot]
        rows[f'{slot:02d}'] = dict(identical_entry=a == c,
             differing_offsets=[i for i, (x, y) in enumerate(zip(a, c)) if x != y],
             written_row_hashes=[hashlib.sha256(x).hexdigest() for x in b['mount'][f'{slot:02d}']['written']],
             mask=a[1], control=int.from_bytes(a[445:447], 'big'))
    names = {}
    for n, m in b['new'].items():
        names[n] = dict(bindings=m['bindings'], records=[dict(slot=r[0], enabled=r[1], label=r[4:4+r[2]].decode('ascii', 'replace')) for r in m['records']])
    dump('inventory.json', dict(photos=expected, dat_sha256=rawhash, rows=rows, modules=names))
    print('32 photo hashes verified; DAT', rawhash, flush=True)
    finish('inventory')


def frames(stems):
    (HERE / 'samples').mkdir(exist_ok=True)
    path = HERE / 'frame_scores.json'
    allr = json.loads(path.read_text()) if path.exists() else {}
    slots = ('04', '01', '02', '03', '05', '06', '07', '08')
    for stem in stems:
        rgb, d, mapping, meta = open_frame(stem)
        h, w = rgb.shape[:2]
        xx, yy = np.meshgrid(np.linspace(48, w-49, 40).astype(int), np.linspace(48, h-49, 28).astype(int))
        a = sample_blocks(rgb, d, mapping, np.column_stack([xx.ravel(), yy.ravel()]))
        v = a['valid']
        scores = {s: metrics(a['jpeg'][v], predict(s, a['x'][v])) for s in slots}
        oldscores = {s: metrics(a['jpeg'][v], predict(s, a['x'][v], 'oldmount')) for s in slots}
        rank = sorted(slots, key=lambda s: scores[s]['de00_median'])
        allr[stem] = dict(meta=meta, scores=scores, old_g137_scores=oldscores, best=rank[0], second=rank[1],
                          margin=scores[rank[1]]['de00_median']-scores[rank[0]]['de00_median'])
        np.savez_compressed(HERE / 'samples' / (stem + '.npz'), **a)
        dump('frame_scores.json', allr)
        print(stem, 'sel', meta['selector'], 'raw13', meta['raw13'], 'WB', meta['white_balance'],
              'best', rank[0], 'n', int(v.sum()), [(s, round(scores[s]['de00_median'], 3), round(scores[s]['dL_median'], 3)) for s in rank], flush=True)
    finish('frames-' + stems[0] + '-' + stems[-1])


def charts(stems):
    sys.path.insert(0, str(ROOT / 'research/chart_v2'))
    import analyzer_geometry as geometry
    import analyze_chart_v2 as analyzer
    ar = load('field_ring', 'research/hue_ring/analyze_ring.py')
    dm = dng_module()
    from types import SimpleNamespace
    chain = SimpleNamespace(ar=ar, dng=dm)
    layout = json.loads((ROOT / 'research/chart_v2/patches.json').read_text())
    for stem in stems:
        rgb, d, mapping, meta = open_frame(stem)
        ds = SimpleNamespace(dng=d, map=mapping, verify=meta['mapping'])
        ds.stats = lambda region: dm.cfa_stats(d, *dm.roi_pixels(mapping, region))
        geo, ident = geometry.locate(rgb, layout, ar)
        patches = analyzer.chart_patches(rgb, geo, ident['page'], layout, ds, chain)
        dump('charts/' + stem + '.json', dict(meta=meta, geometry=geo, identification=ident, patches=patches))
        analyzer.overlay(rgb, patches, stem + ' page ' + str(ident['page']), HERE / 'charts' / (stem + '-overlay.jpg'))
        print(stem, 'page', ident['page'], ident['confidence'], 'patches', len(patches),
              'valid', sum(p['valid'] for p in patches), 'flags', {f:sum(f in p['flags'] for p in patches) for f in sorted({f for p in patches for f in p['flags']})}, flush=True)
    finish('charts-' + stems[0] + '-' + stems[-1])


def rescore():
    allr = json.loads((HERE / 'frame_scores.json').read_text())
    users = {k:v for k,v in json.loads((HERE / 'user_rows.json').read_text())['entries'].items() if v.get('unit','mount') == 'mount'}
    for stem, r in allr.items():
        a = np.load(HERE / 'samples' / (stem + '.npz'))
        v = a['valid']
        r['user_scores'] = {name: metrics(a['jpeg'][v], predict(f"{u['base']:02d}", a['x'][v], 'user:' + name))
                            for name, u in users.items()}
        scores = {**r['scores'], **r['user_scores']}
        rank = sorted(scores, key=lambda s: scores[s]['de00_median'])
        r['all_best'], r['all_second'] = rank[:2]
        r['all_margin'] = scores[rank[1]]['de00_median'] - scores[rank[0]]['de00_median']
        print(stem, [(s, round(scores[s]['de00_median'], 3), round(scores[s]['dL_median'], 3)) for s in rank[:4]], flush=True)
    dump('frame_scores.json', allr)
    finish('rescore-users')


if __name__ == '__main__':
    stage = sys.argv[1]
    stems = sys.argv[2:] or [f'R805{n}' for n in range(1691, 1707)]
    if stage == 'inventory': inventory()
    elif stage == 'frames': frames(stems)
    elif stage == 'charts': charts(sys.argv[2:] or [f'R805{n}' for n in range(1693, 1702)])
    elif stage == 'rescore': rescore()
    else: raise ValueError(stage)
