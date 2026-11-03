"""Scoped I/O and frozen, run-local copies of the existing read-only chain."""
import sys
sys.dont_write_bytecode = True
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNS = HERE / 'local/runs'
UUID = '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
SEALED = ('make_chart.py', 'verify_chart.py', 'patches.json', 'CHART_READY.json',
          'SHA256SUMS', 'SHOOT_LIST.md', 'README.md', 'REPORT.md', '.gitignore')
SOURCES = (
    'research/hue_ring/analyze_ring.py', 'research/hue_ring/sector_model.py',
    'research/hue_ring/pilplot.py', 'research/hue_ring/patches.json',
    'research/t1_probe/probe2/calibration_geometry.py',
    'research/stage2d_verification/analyze.py',
    'research/stage2e_verification/analyze_2e.py',
    'research/color_calibration/analyze_capture.py',
    'research/color_table_fit/matrix_model.py', 'research/color_table_fit/fit_sectors.py',
    'research/color_table_fit/dng_scene.py', 'research/fuji_phase2/fit_fuji.py',
    'firmware/stage2j/tools/deep_sources.py', 'firmware/stage2j/tools/make_recipes.py',
    'research/color_references/colour_math.py',
    'research/closed_loop/common.py', 'research/closed_loop/model.py',
    'research/closed_loop/targets.py', 'research/closed_loop/measure.py',
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def input_path(value):
    p = Path(os.path.abspath(Path(value).expanduser()))
    # Reject a foreign volume before resolving or stat-ing anything on it.
    def allowed(q):
        require(not str(q).startswith('/Volumes/') or q.is_relative_to('/Volumes/Workspace'),
                f'禁止访问其他 /Volumes 路径: {q}')
    allowed(p)
    # Resolve one component at a time so a symlink to a card is rejected before
    # any filesystem lookup on its target. Missing output components are fine.
    current, pending, links = Path('/'), list(p.parts[1:]), 0
    while pending:
        candidate = current / pending.pop(0)
        allowed(candidate)
        if candidate.is_symlink():
            links += 1
            require(links <= 40, '路径符号链接循环')
            target = Path(os.readlink(candidate))
            target = target if target.is_absolute() else candidate.parent / target
            target = Path(os.path.normpath(target))
            allowed(target)
            pending = list(target.parts[1:]) + pending
            current = Path('/')
        else:
            current = candidate
    return current


def mount_guard():
    p = Path('/Volumes/Workspace')
    info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', str(p)]))
    require(p.is_mount() and info.get('MountPoint') == str(p), 'Workspace 未挂载')
    require(info.get('FilesystemType') == 'apfs' and info.get('VolumeUUID', '').upper() == UUID,
            'Workspace APFS/UUID 不符')
    require(all(info.get(k) for k in ('Writable', 'WritableMedia', 'WritableVolume')),
            'Workspace 不可写')
    require(not (HERE / 'local').is_symlink(), 'local/ 不得是符号链接')
    subprocess.run(['git', 'check-ignore', '-q', str(HERE / 'local/analyzer_guard')],
                   cwd=ROOT, check=True)
    return {'uuid': UUID, 'filesystem': 'apfs', 'writable': True}


def run_path(value):
    require(not RUNS.is_symlink(), 'local/runs/ 不得是符号链接')
    p = input_path(value)
    require(p.is_relative_to(RUNS) and p != RUNS,
            '输出必须位于 research/chart_v2/local/runs/<name>/')
    require(not p.exists(), f'输出目录已存在，换一个 run 名称: {p}')
    return p


def sha(path):
    h = hashlib.sha256()
    with input_path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def jsonable(v):
    import numpy as np
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    if isinstance(v, np.ndarray):
        return jsonable(v.tolist())
    if isinstance(v, np.generic):
        return jsonable(v.item())
    if isinstance(v, float) and not np.isfinite(v):
        return None
    if isinstance(v, Path):
        return str(v)
    return v


def dump(path, value):
    p = Path(path).resolve()
    require(p.is_relative_to((HERE / 'local').resolve()), '数值输出只能写本目录 local/')
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(jsonable(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


class Provenance:
    def __init__(self):
        self.before = {}

    def add(self, path):
        p = input_path(path)
        h = sha(p)
        if str(p) in self.before:
            require(self.before[str(p)] == h, f'输入运行中变化: {p}')
        self.before[str(p)] = h
        return p

    def sealed(self):
        for p in [*(HERE / f for f in SEALED), *sorted((HERE / 'pages').glob('*.png'))]:
            self.add(p)

    def finish(self):
        result = {p: {'sha256': h, 'unchanged': sha(p) == h} for p, h in self.before.items()}
        require(all(x['unchanged'] for x in result.values()), '输入发生变化，本次结果不可用')
        return result


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


class Chain:
    """Freeze upstream source, redirect derived writes, never execute upstream CLIs."""
    def __init__(self, out, provenance):
        self.out, self.p = Path(out), provenance
        self.vendor = self.out / 'vendor'
        self.freeze()
        self.common = load('common', self.vendor / 'research/closed_loop/common.py')
        self.common.HERE, self.common.ROOT = HERE, ROOT
        self.common.LOCAL, self.common.SCRATCH = self.out, self.out / 'tmp'
        self.common.Provenance = Provenance
        # common.output_path confines caches to this run; the source .gitignore
        # contains /local/ whereas the old guard expects the spelling local/.
        self.common.mount_guard = mount_guard
        self.ar, self.dng = (self.common.helper(k) for k in ('ar', 'dng'))
        self.physical = self.common.helper('physical')
        self.model = load('model', self.vendor / 'research/closed_loop/model.py')
        self.targets = load('targets', self.vendor / 'research/closed_loop/targets.py')
        self.measure = load('chart_v2_frozen_measure', self.vendor / 'research/closed_loop/measure.py')

    def freeze(self):
        self.vendor.mkdir(parents=True, exist_ok=True)
        sources = {}
        for rel in SOURCES:
            src = self.p.add(ROOT / rel)
            sources[str(src)] = sha(src)
            dst = self.vendor / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.suffix == '.json':
                dst.write_bytes(src.read_bytes())
                continue
            code = src.read_text()
            code = re.sub(r'^ROOT\s*=.*$', f'ROOT = Path({str(ROOT)!r})', code, flags=re.M)
            code = re.sub(r'ROOT\s*/\s*([\'\"])([^\'\"]+\.py)\1',
                          lambda m: f'Path({str(self.vendor / m[2])!r})', code)
            code = re.sub(r'^HUE\s*=.*$', f'HUE = Path({str(self.vendor / "research/hue_ring")!r})',
                          code, flags=re.M)
            dst.write_text(code)
        for rel, cls, dst, extra in (
            ('research/hue_ring/local/calibration_20261020/followup_v2/code/ring_model_v2.py',
             'PreTable', 'pretable.py', 'from scipy.optimize import brentq\n'),
            ('research/color_fit_v2/05_classic_chrome/round4/fit_round4.py', 'Safety', 'safety.py', ''),
        ):
            src = self.p.add(ROOT / rel)
            sources[str(src)] = sha(src)
            code = src.read_text()
            node = next(n for n in ast.parse(code).body if isinstance(n, ast.ClassDef) and n.name == cls)
            (self.vendor / dst).write_text('import numpy as np\nimport math\n' + extra
                                          + ast.get_source_segment(code, node) + '\n')
        parts = []
        for rel, names in (
            ('research/gr4_modes/core.py', ('_blk', 'blocks')),
            ('research/gr4_modes/gr4io.py', ('dng_tags_for_colour',)),
            ('research/color_table_fit/bw_mix.py', ('blk_any', 'gr4_blocks')),
        ):
            src = self.p.add(ROOT / rel)
            sources[str(src)] = sha(src)
            code = src.read_text()
            for n in ast.parse(code).body:
                if isinstance(n, ast.FunctionDef) and n.name in names:
                    parts.append(ast.get_source_segment(code, n))
        (self.vendor / 'bw_helpers.py').write_text('import numpy as np\n' + '\n\n'.join(parts) + '\n')
        copies = {str(p.relative_to(self.out)): sha(p) for p in sorted(self.vendor.rglob('*')) if p.is_file()}
        dump(self.out / 'vendor_manifest.json', {'sources_sha256': sources, 'copies_sha256': copies,
             'adaptation': 'ROOT and code-import paths redirected; PreTable, Safety and BW helpers extracted by AST. '
                           'common LOCAL is rebound to this run before use; upstream CLI entrypoints are never called.'})


def write_sums(out):
    out = Path(out)
    paths = sorted(p for p in out.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
    (out / 'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.relative_to(out)}\n' for p in paths))
