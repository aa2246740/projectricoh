"""Session-local adapters. Upstream and captures remain read-only."""
import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import textwrap
import types

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
CHART = ROOT / 'research/chart_v2'
TABLE = ROOT / 'artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8/candidate/SD_ROOT/DEEPTBL0.DAT'
TABLE_SHA = '44a0ff9e3b584f62dafb76aa90ba05c2bb75c2b74f78f23853345930804e6f05'
CAPTURES = ROOT / 'captures/a12-50/2026-10-24/chart-v2-R8051229-1311'


def guard():
    v = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', '/Volumes/Workspace']))
    assert Path('/Volumes/Workspace').is_mount() and v['MountPoint'] == '/Volumes/Workspace'
    assert v['FilesystemType'] == 'apfs' and v['VolumeUUID'].upper() == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert all(v[k] for k in ('Writable', 'WritableMedia', 'WritableVolume'))
    assert not HERE.is_symlink() and not LOCAL.is_symlink()
    subprocess.run(['git', 'check-ignore', '-q', str(LOCAL / 'guard')], cwd=ROOT, check=True)
    assert sha(TABLE) == TABLE_SHA
    return {'uuid': v['VolumeUUID'], 'filesystem': v['FilesystemType'], 'writable': True}


def audit(event, args):
    if event != 'open' or not isinstance(args[0], (str, bytes, Path)):
        return
    path = Path(os.fsdecode(args[0])).absolute().resolve()
    if str(path).startswith('/Volumes/') and not path.is_relative_to(Path('/Volumes/Workspace')):
        raise PermissionError('foreign volume: ' + str(path))
    mode, flags = args[1:3]
    writing = isinstance(mode, str) and any(c in mode for c in 'wax+')
    writing |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
    if writing and not path.is_relative_to(HERE):
        raise PermissionError('write outside chart_session: ' + str(path))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def plain(value):
    import numpy as np
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, np.generic):
        return plain(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def dump(path, value):
    path = Path(path).resolve()
    assert path.is_relative_to(LOCAL)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plain(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def patch_tiff(cls):
    if getattr(cls, '_session_safe_rationals', False):
        return
    original = cls.ifd
    tree = ast.parse(textwrap.dedent(inspect.getsource(original)))
    class Rational(ast.NodeTransformer):
        def visit_BinOp(self, node):
            if isinstance(node.op, ast.Div):
                return ast.copy_location(ast.Call(func=ast.Name(id='_session_ratio', ctx=ast.Load()),
                    args=[ast.Name(id='tag', ctx=ast.Load()), node.left, node.right], keywords=[]), node)
            return self.generic_visit(node)
    tree = ast.fix_missing_locations(Rational().visit(tree))
    def ratio(tag, numerator, denominator):
        if denominator == 0 and tag in (33437, 37386, 50736):
            return None
        return numerator / denominator
    namespace = dict(original.__globals__, _session_ratio=ratio)
    exec(compile(tree, str(HERE / 'session_runtime.py'), 'exec'), namespace)
    cls.ifd = namespace['ifd']
    cls._session_safe_rationals = True


def patch_engine(module):
    import numpy as np
    original = module.Engine
    class T1Engine(original):
        def predict(self, slot, x, row=None, A=None, B=None, unclipped=False):
            e = self.entries[slot]
            if not e['mask'] & 6:
                return super().predict(slot, x, row, A, B, unclipped)
            assert e['mask'] & 6 == 6 and e['control'] == 0
            rows = e['written']
            xs, gy = self.src.unpack_tone(rows[0], rows[1])
            ys = (list(rows[6][:33]), gy, list(rows[6][33:]))
            curves = [self.mm.Curve.from_rows(xs, y, name=slot) for y in ys]
            pre = np.column_stack([c(np.asarray(x)[:, i]) for i, c in enumerate(curves)])
            base_row, aa, bb = self.parameters(slot)
            row = base_row if row is None else row
            A, B = aa if A is None else A, bb if B is None else B
            y, ci = row.apply(pre)
            co = self.table.forward(ci, self.fs.Z_of_words(A, B, self.ctx))[0]
            rgb = self.mm.rgb_from_ycc(y, co)
            return rgb if unclipped else np.clip(rgb, 0, 255)
        def description(self):
            d = super().description()
            d['session_T1_adapter'] = 'absolute RGB curves R=C, G=B5, B=D; no other forward-model change'
            return d
    module.Engine = T1Engine


def setup(out, freeze=True):
    guard()
    LOCAL.mkdir(exist_ok=True)
    sys.addaudithook(audit)
    sys.path.insert(0, str(CHART))
    import analyzer_runtime as rt
    import analyze_chart_v2 as analyzer
    rt.dump = dump
    analyzer.dump = dump
    p = rt.Provenance()
    p.sealed()
    p.add(HERE / 'session_runtime.py')
    p.add(TABLE)
    p.add(CAPTURES / 'SHA256SUMS')
    if not freeze:
        # Reuse the byte-for-byte frozen sources from extraction, without rewriting them.
        class Existing(rt.Chain):
            def freeze(self):
                value = json.loads((self.out / 'vendor_manifest.json').read_text())
                for rel, digest in value['copies_sha256'].items():
                    assert sha(self.out / rel) == digest
                for source, digest in value['sources_sha256'].items():
                    assert sha(source) == digest
                    self.p.add(source)
        chain = Existing(out, p)
    else:
        chain = rt.Chain(out, p)
    patch_tiff(chain.ar.s2d().Tiff)
    patch_tiff(chain.dng.analyze_capture().Tiff)
    original_lens = analyzer.lens_meta
    def lens_meta(path):
        from PIL import Image
        try:
            return original_lens(path)
        except ZeroDivisionError:
            with Image.open(path) as im:
                e = im.getexif()
                ex = e.get_ifd(34665)
                model, lens = e.get(272), ex.get(42036)
                return {'model': str(model).strip('\x00 '), 'lens_model': lens, 'focal_length_mm': None}
    analyzer.lens_meta = lens_meta
    patch_engine(chain.model)
    return analyzer, chain, p
