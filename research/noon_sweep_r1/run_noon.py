#!/usr/bin/env -S /Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio/.venv/bin/python -I -B
"""Read-only photo intake, g156 reference predictions, and local evidence.

Run: nice -n 15 studio/.venv/bin/python -I -B research/noon_sweep_r1/run_noon.py PHOTO_DIR
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = HERE / 'local'
for _k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS'):
    os.environ[_k] = '1'
if not sys.flags.isolated:
    raise SystemExit('必须加 -I；见 README.md 的完整命令')
if os.getpriority(os.PRIO_PROCESS, 0) < 15:
    os.nice(15-os.getpriority(os.PRIO_PROCESS, 0))

import argparse
import ast
import csv
import datetime as dt
import fcntl
import hashlib
import importlib.util
import json
import math
import plistlib
import re
import struct
import subprocess
import time

sys.path.insert(0, str(HERE))
import numpy as np
from PIL import Image, ImageDraw
from geometry import project, homography, locate_grid, quick_samples, identify_page, page_identity, grid_patches

DAT = ROOT/'firmware/package_v310_g156_test/GXRCE.DAT'
DAT_SHA = '0f4f26d4cd3669915b41ce8e38260a61c60c590e2c581cb72e93f52a2ac631f7'
SETTINGS = ['04 Std', '05 F-CC', '06 F-CN', 'M9 STD', 'HNCS HiCon', 'Kodachrome25', 'HNCS LowSat', 'Vision3 500T']
DEFAULT_SEQUENCE = SETTINGS.copy()
SETTINGS = SETTINGS + ['03 HC BW']
FRACTIONS = (.30, .40, .50)
UUID = '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def source_identity():
    return {str(p.relative_to(ROOT)):sha(p) for p in [*sorted(HERE.glob('*.py')),
        HERE/'roi_editor.html', HERE/'render_synthetic.mjs',
        ROOT/'research/probe_pack_r1/field_20261103.py', ROOT/'research/probe_pack_r1/ramp_field_20261103.py',
        ROOT/'research/probe_pack_r2/probe2_field.py', ROOT/'research/probe_pack_r3/field/local/analyze_probe3.py',
        ROOT/'research/color_references/colour_math.py', ROOT/'research/color_references/screen_chart.json',
        ROOT/'research/ui_bug_audit/capture_analysis.py', *sorted((LOCAL/'header-templates').glob('*.png'))]}


def plain(x):
    if isinstance(x, dict):
        return {str(k): plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [plain(v) for v in x]
    if isinstance(x, np.ndarray):
        return plain(x.tolist())
    if isinstance(x, np.generic):
        return plain(x.item())
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, Path):
        return str(x)
    return x


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(plain(value), ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    tmp.replace(path)


def read(path):
    return json.loads(Path(path).read_text())


def setup():
    volume = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil', 'info', '-plist', '/Volumes/Workspace']))
    if not (Path('/Volumes/Workspace').is_mount() and volume['VolumeUUID'] == UUID
            and volume['FilesystemType'] == 'apfs' and volume['WritableVolume']):
        raise RuntimeError('Workspace 卷身份或可写检查失败')
    if HERE.is_symlink() or LOCAL.is_symlink():
        raise RuntimeError('拒绝 symlink 输出目录')
    LOCAL.mkdir(exist_ok=True)
    # One invocation owns all task output; no worker pool or hidden subprocesses.
    lock = (LOCAL/'run.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('已有 noon 分析在运行；本任务只运行一个计算进程') from None
    return lock


def guard(event, args):
    if event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo', 'subprocess.Popen', 'os.system', 'os.posix_spawn'):
        raise PermissionError('noon 流程禁止网络与子进程')
    mutations = []
    if event == 'open':
        p, mode, flags = args
        if not isinstance(p, (str, bytes, os.PathLike)):
            return
        target = Path(os.fsdecode(p)).resolve()
        if str(target).startswith('/dev/') and str(target) not in ('/dev/null', '/dev/urandom', '/dev/random'):
            raise PermissionError('禁止设备访问: '+str(target))
        if str(target).startswith('/Volumes/') and not target.is_relative_to('/Volumes/Workspace'):
            raise PermissionError('禁止其它挂载卷: '+str(target))
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)):
            mutations = [target]
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.truncate', 'os.utime'):
        mutations = [args[0]]
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        mutations = list(args[:2])
    for p in mutations:
        if not isinstance(p, (str, bytes, os.PathLike)):
            continue
        target = Path(os.fsdecode(p)).resolve()
        public_report = target.parent == HERE and target.name.startswith('REPORT_') and target.suffix == '.md'
        if not (target.is_relative_to(LOCAL) or public_report):
            raise PermissionError('noon 范围外写入: '+str(target))


def loaders():
    field = module(ROOT/'research/probe_pack_r1/field_20261103.py', 'noon_raw_reference')
    # Importing the old reader changes TMPDIR; keep all new scratch inside local/.
    os.environ.update(TMPDIR=str(LOCAL/'tmp'), MPLCONFIGDIR=str(LOCAL/'tmp/mpl'))
    (LOCAL/'tmp').mkdir(exist_ok=True)
    code = ast.parse((ROOT/'research/probe_pack_r1/ramp_field_20261103.py').read_text())
    node = next(n for n in code.body if isinstance(n, ast.FunctionDef) and n.name == 'sample_patch')
    ns = dict(np=np, project=project)
    exec(compile(ast.Module(body=[node], type_ignores=[]), 'sealed-probe3-raw-sampler', 'exec'), ns)
    spectral = ast.parse((ROOT/'research/ui_bug_audit/capture_analysis.py').read_text())
    periodic_node = next(n for n in spectral.body if isinstance(n, ast.FunctionDef) and n.name == 'periodic')
    exec(compile(ast.Module(body=[periodic_node], type_ignores=[]), 'existing-screen-periodicity-diagnostic', 'exec'), ns)
    cm = module(ROOT/'research/color_references/colour_math.py', 'noon_colour_math')
    return field, ns['sample_patch'], cm, ns['periodic']


class Reference:
    """Existing scalar Python model, actual g156 records, no accelerated backend."""
    def __init__(self, display=None, *, geometry=None):
        sys.path.insert(0, str(ROOT/'research/module_adapt'))
        from c040 import geometry_mode, module_spec
        self.geometry = geometry_mode(geometry)
        df_path = ROOT/'research/v39_g153/dat_format.py'
        D = module(df_path, 'noon_dat_reader')
        if sha(DAT) != DAT_SHA:
            raise ValueError('g156 test DAT SHA 不符；停止预测')
        data = DAT.read_bytes()
        D.sections(data)
        D.strict_effects(data)
        if D.u32(data, 28) != 156:
            raise ValueError('DAT generation 不符')
        self.entries = {'04 Std': D.expand(data, 2, 4), '05 F-CC': D.expand(data, 2, 5),
                        '06 F-CN': D.expand(data, 2, 6), '03 HC BW': D.expand(data, 2, 3)}
        area, _ = D.effect_area(data)
        for i in range(D.u16(data, area+10)):
            desc = data[area+32+i*32:area+64+i*32]
            name = desc[20:32].split(b'\0')[0].decode('ascii')
            if desc[18] & 4 and name in SETTINGS:
                if name in self.entries:
                    raise ValueError('MOUNT 配方重名: '+name)
                self.entries[name] = D.expand_effect(data, i)
        if set(self.entries) != set(SETTINGS):
            raise ValueError('g156 缺指定 MOUNT 配方')
        snap = ROOT/'research/recipe_redo_r1/local/source/studio_snapshot/src'
        sys.path.insert(0, str(snap))
        from gxr_studio.engine.model import Model
        from gxr_studio.engine import matrix_model as mm, colour as fs
        self.mm, self.fs = mm, fs
        official_path = ROOT/'research/module_adapt/local/official_parameters.json'
        ring_path = ROOT/'research/hue_ring/local/ring_model_v2.json'
        official = read(official_path)['units']['mount']
        if display is None:
            display_path = ROOT/'research/stage2e_verification/local/measurements.json'
            display = read(display_path)['frames']['R8051160']['meta']['display']
            d0, d1 = np.zeros(24), np.zeros(24)
            for i, colour in enumerate(('orange', 'green', 'blue', 'red', 'magenta')):
                selected = np.array([bool(int(official['mask'][i]) & (1 << j)) for j in range(24)])
                level = int(display[colour+'_hue'])-1
                d0[selected] = np.asarray(official['d0_levels'])[level, selected]
                d1[selected] = np.asarray(official['d1_levels'])[level, selected]
        else:
            if len(display) != 13 or any(v is None for v in display):
                raise ValueError('不能解析 04 滑杆，拒绝猜测模型条件')
            d0, d1 = np.zeros(24), np.zeros(24)
            for i in range(5):
                selected = np.array([bool(int(official['mask'][i]) & (1 << j)) for j in range(24)])
                d0[selected] = np.asarray(official['d0_levels'])[display[8+i]-1, selected]
                d1[selected] = np.asarray(official['d1_levels'])[display[8+i]-1, selected]
                sat = np.asarray(official['sat_levels'])[display[3+i]-1]
                if not np.all(np.broadcast_to(sat, (24,))[selected] == 100):
                    raise ValueError('非默认五色饱和度，现行参考适配未验证')
            if official['vividness_levels'][display[2]-1] != 100:
                raise ValueError('非默认 vividness，现行参考适配未验证')
        b = self.entries['04 Std']
        stock = np.array([fs.decode_word(b[115+i*4:119+i*4]) for i in range(24)])
        self.model = Model(stock, d0, d1, module_spec(read(ring_path), 'mount-a12', self.geometry))
        self.row = mm.MatrixRow.from_bytes(b[216:244])
        basis = mm.rgb_from_ycc(np.array([1., 0., 0.]), np.array([0., 1., 1j]))
        self.inverse_output = np.linalg.inv(basis)
        self.xs = np.r_[0, struct.unpack_from('>31H', b, 20), 4095]
        self.ys = [np.array(list(b[82:115]))]*3
        if b[1] & 4:
            self.ys = [np.array(list(b[379:412])), np.array(list(b[82:115])), np.array(list(b[412:445]))]
        sources = [df_path, official_path, ring_path, ROOT/'research/module_adapt/c040.py',
                   *(snap/'gxr_studio/engine').glob('*.py')]
        if self.geometry == 'native':
            sources += [ROOT/'artifacts/firmware/gxr-1.51'/name for name in ('jlaunch3', 'l08firm3')]
        self.provenance = dict(dat_sha256=DAT_SHA, generation=156, unit='MOUNT', backend='Python reference Model.predict, quantize=False',
            records={k:hashlib.sha256(v).hexdigest() for k, v in self.entries.items()},
            inputs={str(p.relative_to(ROOT)):sha(p) for p in sources}, transferred_50mm_model=True,
            c040_geometry=self.geometry, anchors_require_model_specific_inverse=True,
            full_recipe_camera_accuracy_validated=False,
            bw_chroma='discard for native 03; reference Model.predict explicit mode')

    def predict(self, setting, x):
        return self.model.predict(self.entries[setting], np.asarray(x, float), quantize=False,
                                  bw_chroma='discard' if setting == '03 HC BW' else 'conditional')

    def inverse04(self, rgb):
        # Invert the reference's actual output matrix. The rounded BT.601
        # ycbcr helper is close, but is not the exact inverse of rgb_from_ycc.
        q = np.asarray(rgb, float) @ self.inverse_output
        y, co = q[:, 0], q[:, 1]+1j*q[:, 2]
        ci, _ = self.model.engine.table.inverse_stock(co)
        pre = self.row.invert(y, ci)
        xx = []
        for c in range(3):
            keep = np.r_[True, np.diff(self.ys[c]) > 0]
            xx.append(np.interp(pre[:, c], self.ys[c][keep], self.xs[keep]))
        x = np.column_stack(xx)
        residual = np.linalg.norm(self.predict('04 Std', x)-rgb, axis=1)
        return x, residual


def ycc(rgb):
    rgb = np.asarray(rgb, float)
    return rgb @ np.array([[.299, -.168736, .5], [.587, -.331264, -.418688], [.114, .5, -.081312]]) + [0, 128, 128]


def discover(folder, recursive=False):
    paths = folder.rglob('*') if recursive else folder.iterdir()
    images = [p for p in paths if p.is_file() and p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.dng')]
    pairs = {}
    for p in images:
        key = (str(p.parent), p.stem.casefold())
        row = pairs.setdefault(key, {})
        kind = 'dng' if p.suffix.lower() == '.dng' else 'jpeg'
        if kind in row:
            if row[kind] != p:
                raise ValueError('同目录重名照片，无法配对: '+str(p))
        row[kind] = p
    selected = [v for v in pairs.values() if 'jpeg' in v and ('dng' in v or v['jpeg'].suffix.lower() == '.png')]
    if len({v['jpeg'].stem.casefold() for v in selected}) != len(selected):
        raise ValueError('不同子目录有重复照片名；分批运行，避免覆盖逐帧证据')
    return sorted(selected,
                  key=lambda v: (str(v['jpeg'].parent), [int(q) if q.isdigit() else q.lower() for q in re.split(r'(\d+)', v['jpeg'].stem)]))


def bbox_patch(roi):
    x0, y0, x1, y1 = roi['box']
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError('ROI box 必须为 0..1 的 xyxy')
    return dict(id=roi['id'], group=roi.get('group', 'manual'), rgb=[0, 0, 0],
                swatch=dict(x=x0, y=y0, w=x1-x0, h=y1-y0))


def sample_physical_patch(rgb, native, raw, info, H, patch, fraction, neutral):
    """Small card regions: require actual CFA support, without enlarging ROIs.

    The historical screen sampler keeps its >300 pixel gate. A distant card
    can have a valid central 30% ROI below that size; use 128 total pixels,
    at least 32 of each CFA colour, and nonempty CFA cells in all 4x4 tiles.
    """
    r = patch['swatch']
    x, y = r['x']+r['w']*(1-fraction)/2, r['y']+r['h']*(1-fraction)/2
    w, h = r['w']*fraction, r['h']*fraction
    poly = project(H, [[x,y], [x+w,y], [x+w,y+h], [x,y+h]])*rgb.shape[1::-1]
    x0,y0 = np.floor(poly.min(0)).astype(int)
    x1,y1 = np.ceil(poly.max(0)).astype(int)+1
    if not (x0 >= 0 and y0 >= 0 and x1 <= rgb.shape[1] and y1 <= rgb.shape[0]):
        raise ValueError('实物 ROI 越界: '+patch['id'])
    yy,xx = np.mgrid[y0:y1, x0:x1]
    uv = project(np.linalg.inv(H), np.stack([(xx+.5)/rgb.shape[1], (yy+.5)/rgb.shape[0]], -1))
    mask = (uv[:,:,0]>=x)&(uv[:,:,0]<=x+w)&(uv[:,:,1]>=y)&(uv[:,:,1]<=y+h)
    ox,oy = info['crop_origin_xy']
    cfa = np.array([[0,1],[1,2]])[(yy+oy)%2, (xx+ox)%2]
    region = raw[y0:y1, x0:x1]
    channels = [region[mask&(cfa==c)] for c in range(3)]
    if mask.sum() < 128 or min(map(len, channels)) < 32:
        raise ValueError('实物 ROI/CFA 样本不足: '+patch['id'])
    jr, yc = rgb[y0:y1, x0:x1], native[y0:y1, x0:x1]
    tiles = []
    for ty in range(4):
        for tx in range(4):
            tile = mask&(uv[:,:,0]>=x+tx*w/4)&(uv[:,:,0]<x+(tx+1)*w/4)&(uv[:,:,1]>=y+ty*h/4)&(uv[:,:,1]<y+(ty+1)*h/4)
            tc = [region[tile&(cfa==c)] for c in range(3)]
            if min(map(len, tc)) == 0:
                raise ValueError('实物 4x4 子区 CFA 样本不足: '+patch['id'])
            tiles.append(dict(rgb=jr[tile].mean(0), ycc=yc[tile].mean(0),
                raw_dn=[a.mean()-info['black'] for a in tc], pixels=int(tile.sum()), cfa_pixels=list(map(len,tc))))
    return dict(id=patch['id'], screen_rgb=patch['rgb'], polygon=poly, roi_bbox=[x0,y0,x1,y1],
        pixels=int(mask.sum()), cfa_pixels=list(map(len,channels)),
        sample_policy='small-physical-region: >=128 pixels, >=32 per CFA colour, nonempty 4x4 CFA tiles',
        jpeg_mean=jr[mask].mean(0), native_ycc_mean=yc[mask].mean(0), jpeg_sd=jr[mask].std(0), ycc_sd=yc[mask].std(0),
        raw_dn_mean=[a.mean()-info['black'] for a in channels], raw_sd=[a.std() for a in channels],
        raw_wb=[(a.mean()-info['black'])/neutral[c] for c,a in enumerate(channels)],
        raw_clip_fraction=[float(np.mean(a>=info['white']-16)) for a in channels],
        jpeg_clip_fraction=np.mean((jr[mask]<=2)|(jr[mask]>=253),axis=0), tiles=tiles)


def extract_one(pair, override, args, out, field, sampler, pages, index, count, periodic=None):
    jp = pair['jpeg']
    key = re.sub('[^A-Za-z0-9_.-]', '_', jp.stem)
    inputs = {str(p):sha(p) for p in pair.values()}
    input_stats = {str(p):(p.stat().st_size, p.stat().st_mtime_ns) for p in pair.values()}
    if override.get('manual_confirmation_required'):
        raise ValueError('manifest 仍为草稿，请核对后删除 manual_confirmation_required 或改为 false')
    signature = hashlib.sha256(json.dumps(dict(inputs=inputs, override=override, kind=args.kind,
        manifest=args.manifest_data, upstream={str(p.relative_to(ROOT)):sha(p) for p in (
            ROOT/'research/probe_pack_r1/field_20261103.py', ROOT/'research/probe_pack_r1/ramp_field_20261103.py',
            ROOT/'research/color_references/screen_chart.json', *sorted((LOCAL/'header-templates').glob('*.png')))},
        code={p.name:sha(p) for p in HERE.glob('*.py')}), sort_keys=True).encode()).hexdigest()
    cache = out/'frames'/(key+'.json')
    if cache.exists() and not args.fresh:
        old = read(cache)
        if old.get('signature') == signature:
            print('CACHE', jp.name, flush=True)
            return old
    rgb = np.asarray(Image.open(jp).convert('RGB'))
    raw, info, meta = None, None, {}
    native = None
    if 'dng' in pair:
        t = field.Tiff(pair['dng'].read_bytes())
        raw, info = field.decode_raw(t)
        meta = field.metadata(t)
        jmeta = field.metadata(field.jpeg_tiff(jp))
        for prop in ('time', 'iso', 'exposure_s', 'as_shot_neutral', 'sliders_raw'):
            if meta[prop] != jmeta[prop] and prop != 'as_shot_neutral':
                raise ValueError('DNG/JPEG 元数据不符: '+prop)
        if raw.shape != rgb.shape[:2]:
            raise ValueError('DNG DefaultCrop 与 JPEG 尺寸不符')
        if meta['orientation'] not in (None, 1):
            raise ValueError('非横向 Orientation，先用 per-frame manifest 核实原像素坐标')
        with Image.open(jp) as im:
            im.draft('YCbCr', im.size)
            if im.mode != 'YCbCr':
                raise ValueError('无法读取 JPEG 原生 YCbCr')
            native = np.asarray(im)
    kind = override.get('kind', args.kind)
    if kind == 'auto' and 'probe3' in str(args.photos).lower():
        kind = 'probe3'
    locations = []
    patches, H = [], np.eye(3)
    identity = None
    if kind == 'probe3':
        probe = module(ROOT/'research/probe_pack_r3/field/local/analyze_probe3.py', 'noon_probe3_reuse')
        os.environ.update(TMPDIR=str(LOCAL/'tmp'), MPLCONFIGDIR=str(LOCAL/'tmp/mpl'))
        H, loc = probe.locate(rgb, jp.stem)
        locations.append(loc)
        patches = probe.layout()['patches']
        for p in patches:
            p['group'] = 'memory_skin' if p['id'] == 'skin' else 'memory_sky' if p['id'] == 'blue' else 'memory_foliage' if p['id'] == 'leaf' else 'neutral'
        identity = dict(page='probe3-ramp', valid=True)
    elif kind in ('auto', 'screen'):
        try:
            if 'corners' in override:
                corners = np.asarray(override['corners'], float)
                if corners.shape != (4, 2) or not np.all((corners >= 0) & (corners <= 1)):
                    raise ValueError('corners 必须为四个 0..1 坐标')
                H = homography([[0, 0], [1, 0], [1, 1], [0, 1]], corners)
                loc = dict(method='manual-four-corners', H=H, patch_fraction_of_pitch=override.get('patch_fraction_of_pitch', [.96, .95]))
            else:
                H, loc = locate_grid(rgb)
            identity = page_identity(rgb, H, pages, LOCAL/'header-templates')
            if override.get('page'):
                identity['manual_page'] = override['page']
                identity['manual_response_conflict'] = identity['valid'] and identity['page'] != override['page']
                identity['recognized_page'] = identity['page']
                page = override['page']
                identity['page'] = page
            else:
                page = identity['page']
            if page == 'unknown':
                raise ValueError('网格存在，页面响应不足: '+json.dumps(identity))
            p = next(p for p in pages if p['id'] == page)
            patches = grid_patches(p, loc['patch_fraction_of_pitch'])
            locations.append(loc)
            kind = 'screen'
        except ValueError as e:
            if kind == 'screen' or count >= 64 and index < 64:
                raise
            kind = 'physical'
            identity = dict(page='physical', valid=False, screen_detection_error=str(e))
    if kind == 'physical':
        template = args.manifest_data.get('physical_template', {})
        chart = override.get('chart', template.get('chart', {}))
        cols, rows = int(chart.get('cols', 6)), int(chart.get('rows', 4))
        try:
            if chart.get('corners'):
                H = homography([[0, 0], [1, 0], [1, 1], [0, 1]], chart['corners'])
                loc = dict(method='manual-card-four-corners', H=H, patch_fraction_of_pitch=chart.get('patch_fraction_of_pitch', [.78, .78]))
            else:
                H, loc = locate_grid(rgb, cols, rows)
            if loc.get('inliers', cols*rows) < cols*rows*.8:
                raise ValueError('自动色卡网格支持不足 80%，请点四角')
            page = dict(patches=[dict(id=f'card_{r+1}_{c+1}', row=r, col=c, group='untrusted_card') for r in range(rows) for c in range(cols)])
            patches = grid_patches(page, loc['patch_fraction_of_pitch'], cols, rows)
            locations.append(loc)
        except ValueError as e:
            locations.append(dict(method='card-open', error=str(e)))
        manual = override.get('rois', template.get('rois', []))
        # Template ROIs are image coordinates. Each target can override them;
        # when requested, card homography maps a fixed template to this frame.
        for roi in manual:
            pp = bbox_patch(roi)
            pp['image_coordinates'] = True
            if template.get('reference_corners') and template.get('track_with_card') and locations[0].get('H') is not None:
                baseH = homography([[0, 0], [1, 0], [1, 1], [0, 1]], template['reference_corners'])
                pp['roi_H'] = H @ np.linalg.inv(baseH)
            elif template.get('track_with_card') and 'rois' not in override:
                raise ValueError('共享 ROI 要跟踪色卡，但该帧色卡定位失败；请逐帧点四角或重框')
            patches.append(pp)
        identity = dict(page=override.get('scene', 'daylight'), valid=True)
        if not patches:
            raise ValueError('实物无可用区域；填写 local manifest 的 chart.corners 和 rois')
    sets = {}
    fractions = FRACTIONS
    for fraction in fractions:
        items = []
        for patch in patches:
            ph = np.asarray(patch.get('roi_H', np.eye(3) if patch.get('image_coordinates') else H))
            if raw is not None:
                reader = sample_physical_patch if kind == 'physical' else sampler
                item = reader(rgb, native, raw, info, ph, patch, fraction, meta['as_shot_neutral'])
                # Histograms are retained by the upstream sampler but not needed
                # here; keep means, spread and 4x4 tile sensitivity instead.
                item.pop('raw_histograms', None)
                item['raw_linear_BT601_proxy'] = ycc(np.asarray(item['raw_wb'])*255/(info['white']-info['black']))
                if periodic is not None and kind in ('screen', 'probe3') and fraction == .4:
                    x0, y0, x1, y1 = item['roi_bbox']
                    # Inscribe a smaller axis-aligned rectangle inside the ROI
                    # for the diagnostic only. Colour means still use its polygon.
                    dx, dy = max(1, (x1-x0)//8), max(1, (y1-y0)//8)
                    tile = rgb[y0+dy:y1-dy, x0+dx:x1-dx].astype(float)
                    item['periodicity_diagnostic'] = {f'{axis}_{channel}':periodic(tile[..., c].mean(axis=axis))
                        for axis in (0, 1) for c, channel in enumerate('RGB')}
            else:
                r = patch['swatch']
                poly = project(ph, [[r['x']+r['w']*.5, r['y']+r['h']*.5]])[0]
                x, y = (poly * rgb.shape[1::-1]).astype(int)
                box = rgb[max(0, y-3):y+4, max(0, x-3):x+4]
                item = dict(id=patch['id'], jpeg_mean=box.mean((0, 1)), native_ycc_mean=ycc(box.mean((0, 1))), jpeg_sd=box.std((0, 1)),
                    polygon=project(ph, [[r['x'], r['y']], [r['x']+r['w'], r['y']], [r['x']+r['w'], r['y']+r['h']], [r['x'], r['y']+r['h']]])*[rgb.shape[1], rgb.shape[0]])
            item['group'] = patch.get('group', 'unknown')
            items.append(item)
        sets[str(fraction)] = items
    overlay = Image.fromarray(rgb)
    overlay.thumbnail((1400, 1000))
    draw = ImageDraw.Draw(overlay)
    for item in sets['0.4']:
        poly = np.array(item['polygon']) / rgb.shape[1::-1]*overlay.size
        draw.line([tuple(p) for p in np.vstack([poly, poly[:1]])], fill='#ffbb00', width=2)
        draw.text(tuple(poly[0]), item['id'], fill='#ffffff')
    (out/'overlays').mkdir(exist_ok=True)
    overlay.save(out/'overlays'/(key+'.jpg'), quality=90)
    row = dict(frame=jp.stem, input=inputs, signature=signature, kind=kind, identity=identity, location=locations,
               metadata=meta, raw=info, patches=sets, override=override, acquisition_index=index,
               acquisition_count=count, has_raw=raw is not None, pixel_size=rgb.shape[1::-1],
               synthetic='synthetic fixture' in str(meta.get('model', '')).lower())
    if any((p.stat().st_size, p.stat().st_mtime_ns) != input_stats[str(p)] for p in pair.values()):
        raise ValueError('读取期间照片发生变化，请等复制结束后重跑')
    dump(cache, row)
    print('EXTRACT', jp.name, kind, identity.get('page'), len(patches), flush=True)
    return plain(row)


def arrange(frames):
    screen = [f for f in frames if f['kind'] == 'screen']
    physical = [f for f in frames if f['kind'] == 'physical']
    for i, f in enumerate(screen):
        order_index = f['acquisition_index'] if f.get('acquisition_count', 0) >= 64 else i
        group = order_index // 8
        expected = DEFAULT_SEQUENCE[group] if group < len(DEFAULT_SEQUENCE) else '04 Std'
        f['setting_order'] = f['override'].get('setting', expected)
        f['scene'] = f['identity']['page']
        f['order_group'] = f['override'].get('order_group', group)
    for i, f in enumerate(physical):
        order_index = i
        f['setting_order'] = f['override'].get('setting', DEFAULT_SEQUENCE[order_index] if 0 <= order_index < 8 else '04 Std')
        f['scene'] = f['override'].get('scene', 'daylight' if order_index < 9 else 'indoor')
        f['order_group'] = i
    return screen+physical


def arrays(frame, fraction):
    p = frame['patches'][str(fraction)]
    return (np.array([v['jpeg_mean'] for v in p]), np.array([v.get('raw_wb', [np.nan]*3) for v in p]),
            np.array([v['native_ycc_mean'] for v in p]))


def weights(frame, anchors):
    def clock(f):
        value = f['metadata'].get('time')
        if value:
            return dt.datetime.strptime(value, '%Y:%m:%d %H:%M:%S').timestamp()
        return float(f['acquisition_index'])
    t = clock(frame)
    ordered = sorted(anchors, key=clock)
    before = [a for a in ordered if clock(a) <= t]
    after = [a for a in ordered if clock(a) >= t]
    a = before[-1] if before else ordered[0]
    b = after[0] if after else ordered[-1]
    alpha = 0. if clock(a) == clock(b) else (t-clock(a))/(clock(b)-clock(a))
    return a, b, float(alpha)


def summarize(rows, cm):
    if not rows:
        return dict(n=0, de00_median=None, de00_p95=None)
    values = np.array([r['DE00'] for r in rows])
    d = np.array([r['Lab_observed_minus_predicted'] for r in rows])
    hue = np.array([r['hue_error_deg'] for r in rows if r['hue_error_deg'] is not None])
    chroma = np.array([r['chroma_error'] for r in rows])
    hue_median = None
    if len(hue):
        vector = np.mean(np.exp(1j*np.deg2rad(hue)))
        if abs(vector) >= .2:
            center = np.angle(vector, deg=True)
            hue_median = float((np.median(center+(hue-center+180)%360-180)+180)%360-180)
    worst = max(rows, key=lambda r:r['DE00'])
    return dict(n=len(rows), de00_median=float(np.median(values)), de00_p95=float(np.percentile(values, 95)),
        worst=dict(frame=worst['frame'], patch=worst['patch'], DE00=worst['DE00']),
        median_delta_L=float(np.median(d[:, 0])), median_delta_C=float(np.median(chroma)),
        median_hue_error_deg=hue_median,
        hue_convention='positive rotates Lab hue counterclockwise; computed only when both C >= 5',
        native_ycc_error_median=np.median([r['native_YCbCr_error'] for r in rows], axis=0))


def analyse(frames, out, cm, issues):
    ordered = arrange([f for f in frames if f['kind'] in ('screen', 'physical')])
    expected_pages = ['T1', 'T2', 'T3', 'T4', 'V1', 'V2', 'V3', 'V4']
    for group in sorted({f['order_group'] for f in ordered if f['kind'] == 'screen'}):
        batch = [f for f in ordered if f['kind'] == 'screen' and f['order_group'] == group]
        found = [f['scene'] for f in batch]
        expected = batch[0]['override'].get('group_pages', expected_pages if group < 8 else None)
        if expected is not None and found != expected:
            issues.append('OPEN: 屏幕第 '+str(group+1)+' 组页面顺序/完整性不符，需核对 manifest。')
            for f in batch:
                if 'setting' not in f['override']:
                    f['order_untrusted'] = True
    for f in ordered:
        if f['kind'] != 'physical':
            continue
        regions = f['patches']['0.4']
        groups = {p['group'] for p in regions}
        card_count = sum(p['group'] == 'untrusted_card' for p in regions)
        if card_count != 24:
            issues.append('OPEN: '+f['frame']+' 色卡区域为 '+str(card_count)+' 块，需补齐或核对 24 块。')
        missing = [name for name, found in (
            ('皮肤', 'memory_skin' in groups), ('蓝物', bool(groups & {'blue', 'memory_sky'})),
            ('绿叶', 'memory_foliage' in groups)) if not found]
        if missing:
            issues.append('OPEN: '+f['frame']+' 缺手动区域 '+ '、'.join(missing)+'，卡片统计不能替代这些实物。')
    baseline = [f for f in ordered if f['setting_order'] == '04 Std' and f['has_raw']]
    if not baseline:
        issues.append('OPEN: 没有带 RAW 的 04，不能给出配方实拍误差。PNG 只验证页面识别。')
        return dict(rows=[], summaries={}, identity=[], drift=[])
    model = Reference(baseline[0]['metadata'].get('sliders_display'))
    dump(out/'model-provenance.json', model.provenance)
    for name, entry in model.entries.items():
        p = out/'records'/(re.sub('[^A-Za-z0-9_-]', '_', name)+'.record552')
        p.parent.mkdir(exist_ok=True)
        p.write_bytes(entry)
    inv_cache = {}
    def inverse(f, fraction):
        key = f['frame'], fraction
        if key not in inv_cache:
            j, r, yc = arrays(f, fraction)
            x, residual = model.inverse04(j)
            valid = np.array([max(v.get('jpeg_clip_fraction', [1])) < .01 and max(v.get('raw_clip_fraction', [1])) < .001 for v in f['patches'][str(fraction)]])
            valid &= np.min(r, axis=1) > 2
            valid &= residual < 2.
            inv_cache[key] = (x, r, yc, ycc(j), valid, residual)
            print('REFERENCE inverse04', f['frame'], fraction, 'valid', int(valid.sum()), flush=True)
        return inv_cache[key]
    rows, identity_rows, drift = [], [], []
    for f in ordered:
        if not f['has_raw']:
            continue
        if f.get('order_untrusted'):
            issues.append('OPEN: 有失败帧，未确认设置的帧不出具配方统计；用 intake-manifest.json 逐帧确认。')
            continue
        if f['setting_order'] not in SETTINGS:
            issues.append('OPEN: 无效设置 '+f['frame'])
            continue
        if f['metadata'].get('iso') != 200:
            issues.append('OPEN: '+f['frame']+' 不是 ISO200，未套用该模型')
            continue
        if f['metadata'].get('sliders_raw') != baseline[0]['metadata'].get('sliders_raw'):
            issues.append('OPEN: '+f['frame']+' 滑杆不同，预测跳过')
            continue
        anchors = [a for a in baseline if a['kind'] == f['kind'] and a['scene'] == f['scene'] and a['frame'] != f['frame'] and not a.get('order_untrusted')]
        if not anchors:
            if f['setting_order'] != '04 Std':
                issues.append('OPEN: '+f['frame']+' 缺相同页/场景的独立 04')
            continue
        a, b, alpha = weights(f, anchors)
        if any(f['metadata'].get(k) != control['metadata'].get(k)
               for control in (a, b) for k in ('wb_exif', 'wb_shotinfo', 'light_source')):
            issues.append('OPEN: '+f['frame']+' 与同页/同场景 04 的 WB 模式不同，已跳过预测。')
            continue
        bracketed = a['frame'] != b['frame']
        # Pairing requires equal patch IDs, never just equal array length.
        ids = [p['id'] for p in f['patches']['0.4']]
        if any([p['id'] for p in q['patches']['0.4']] != ids for q in (a, b)):
            issues.append('OPEN: '+f['frame']+' 与 04 的 ROI id 不匹配')
            continue
        all_candidates = {}
        frame_rows = []
        for fraction in FRACTIONS:
            j, raw, native = arrays(f, fraction)
            xa, ra, yca, rgbyca, va, resa = inverse(a, fraction)
            xb, rb, ycb, rgbycb, vb, resb = inverse(b, fraction)
            gain = (1-alpha)*xa/np.maximum(ra, 1e-9)+alpha*xb/np.maximum(rb, 1e-9)
            x = gain*raw
            base = model.predict('04 Std', x)
            offset = (1-alpha)*(yca-rgbyca)+alpha*(ycb-rgbycb)
            valid = va & vb & np.all(np.isfinite(x), axis=1) & np.all((x >= 0) & (x <= 4095), axis=1)
            valid &= np.array([max(v['raw_clip_fraction']) < .001 for v in f['patches'][str(fraction)]])
            predictions = {setting:model.predict(setting, x) for setting in SETTINGS}
            if fraction == .4:
                if int(valid.sum()) < len(valid)*.5:
                    issues.append('OPEN: '+f['frame']+' 有效输入块不足一半，检查 RAW 截断与 04 反演。')
                for setting, pred in predictions.items():
                    de = cm.delta_e00(cm.rgb_lab(pred/255), cm.rgb_lab(j/255))
                    all_candidates[setting] = float(np.median(de[valid])) if valid.any() else None
            pred = predictions[f['setting_order']]
            observed_lab, predicted_lab = cm.rgb_lab(j/255), cm.rgb_lab(pred/255)
            delta = cm.delta_e00(predicted_lab, observed_lab)
            oc, pc = np.linalg.norm(observed_lab[:, 1:], axis=1), np.linalg.norm(predicted_lab[:, 1:], axis=1)
            hue_error = (np.degrees(np.arctan2(observed_lab[:, 2], observed_lab[:, 1])-np.arctan2(predicted_lab[:, 2], predicted_lab[:, 1]))+180)%360-180
            first_pred = model.predict(f['setting_order'], xa/np.maximum(ra, 1e-9)*raw)
            last_pred = model.predict(f['setting_order'], xb/np.maximum(rb, 1e-9)*raw)
            endpoint_envelope = cm.delta_e00(cm.rgb_lab(first_pred/255), cm.rgb_lab(last_pred/255))
            for k, patch in enumerate(f['patches'][str(fraction)]):
                row = dict(frame=f['frame'], kind=f['kind'], setting=f['setting_order'], page=f['scene'], patch=patch['id'], group=patch['group'], ROI=fraction,
                    valid=bool(valid[k]), DE00=float(delta[k]), observed_rgb=j[k], predicted_rgb=pred[k],
                    raw_wb=raw[k], conditioned_input=x[k], native_observed_YCbCr=native[k],
                    predicted_YCbCr=ycc(pred[k])+offset[k], native_YCbCr_error=native[k]-ycc(pred[k])-offset[k],
                    observed_delta_from04=native[k]-ycc(base[k])-offset[k], predicted_delta_from04=ycc(pred[k])-ycc(base[k]),
                    Lab_observed_minus_predicted=observed_lab[k]-predicted_lab[k], chroma_error=float(oc[k]-pc[k]),
                    hue_error_deg=float(hue_error[k]) if min(oc[k], pc[k]) >= 5 else None,
                    anchors=[a['frame'], b['frame']], alpha=alpha, time_bracketed=bracketed,
                    endpoint_prediction_spread_DE00=float(endpoint_envelope[k]),
                    actual_jpeg_clipped=max(patch['jpeg_clip_fraction']) >= .01,
                    baseline_inverse_residual=max(resa[k], resb[k]))
                frame_rows.append(plain(row))
        ranked = sorted((k for k, v in all_candidates.items() if v is not None), key=all_candidates.get)
        if ranked:
            best = ranked[0]
            margin = all_candidates[ranked[1]]-all_candidates[best]
            response = best if margin >= .35 and all_candidates[best] <= 10 else 'unknown'
        else:
            best, margin, response = None, None, 'unknown'
        conflict = response != 'unknown' and response != f['setting_order']
        if conflict:
            issues.append('OPEN: 设置顺序/响应冲突 '+f['frame']+'，顺序 '+f['setting_order']+'，响应 '+response+'；只列条件统计')
        identity_rows.append(dict(frame=f['frame'], order=f['setting_order'], response=response, best=best, scores=all_candidates,
            margin=margin, conflict=conflict, model_based_check_not_menu_proof=True))
        for row in frame_rows:
            row['setting_response'] = response
            row['setting_conflict'] = conflict
            rows.append(row)
        if f['setting_order'] == '04 Std':
            primary = [r for r in frame_rows if r['ROI'] == .4 and r['valid']]
            jj, rr, _ = arrays(f, .4)
            _, ar, _, _, _, _ = inverse(a, .4)
            drift.append(dict(frame=f['frame'], reference=a['frame'], scene=f['scene'],
                raw_relative_change_median=np.median(rr/np.maximum(ar, 1e-9)-1, axis=0),
                corrected=summarize(primary, cm), independent_control=True))
        dump(out/'comparisons'/(f['frame']+'.json'), frame_rows)
    identified = {r['frame'] for r in identity_rows}
    for f in ordered:
        if f['frame'] not in identified:
            identity_rows.append(dict(frame=f['frame'], order=f['setting_order'], response='unknown', best=None,
                scores={}, margin=None, conflict=False, model_based_check_not_menu_proof=True,
                reason='未运行响应校验；缺独立04或输入不满足条件，见 OPEN。'))
    acquisition_order = {f['frame']:i for i, f in enumerate(ordered)}
    identity_rows.sort(key=lambda r:acquisition_order[r['frame']])
    summaries = {}
    for setting in SETTINGS:
        for page in sorted({r['page'] for r in rows}):
            use = [r for r in rows if r['setting'] == setting and r['page'] == page and r['ROI'] == .4 and r['valid']]
            if not use:
                continue
            q = summarize(use, cm)
            q['setting_conflict'] = any(r['setting_conflict'] for r in use)
            q['conditional_without_tail04'] = setting != '04 Std' and any(not r['time_bracketed'] for r in use)
            q['groups'] = {g:summarize([r for r in use if r['group'] == g or g == 'blue' and ('blue' in r['patch'] or 'sky' in r['patch'])], cm)
                           for g in ('memory_skin', 'blue', 'memory_foliage', 'untrusted_card')}
            q['ROI_sensitivity'] = {str(fr):summarize([r for r in rows if r['setting'] == setting and r['page'] == page and r['ROI'] == fr and r['valid']], cm) for fr in FRACTIONS}
            q['endpoint_spread_DE00_p95'] = float(np.percentile([r['endpoint_prediction_spread_DE00'] for r in use], 95))
            summaries[setting+'/'+page] = q
    signs = []
    for row in rows:
        if row['ROI'] != .4 or not row['valid'] or row['setting'] == '04 Std':
            continue
        component = 1 if row['group'] == 'memory_skin' else 2 if row['group'] in ('memory_sky', 'blue') or 'blue' in row['patch'].lower() else None
        if component is None:
            continue
        obs, pred = row['observed_delta_from04'][component], row['predicted_delta_from04'][component]
        controls = [r for r in rows if r['setting'] == '04 Std' and r['page'] == row['page'] and r['kind'] == row['kind'] and r['patch'] == row['patch'] and r['ROI'] == .4 and r['valid']]
        budget = max(abs(r['native_YCbCr_error'][component]) for r in controls) if controls else None
        measured_budget = 0. if budget is None else budget
        variants = [r for r in rows if r['frame'] == row['frame'] and r['patch'] == row['patch'] and r['valid']]
        observed_range = [min(r['observed_delta_from04'][component] for r in variants)-measured_budget,
                          max(r['observed_delta_from04'][component] for r in variants)+measured_budget]
        strong = min(abs(v) for v in observed_range) > .25 and observed_range[0]*observed_range[1] > 0 and abs(pred) > .08
        state = 'opposite_sign' if strong and obs*pred < 0 else 'same_sign' if strong and obs*pred > 0 else 'unresolved_small_component'
        signs.append(dict(frame=row['frame'], setting=row['setting'], page=row['page'], patch=row['patch'], component=['Y', 'Cb', 'Cr'][component],
            observed_delta=obs, predicted_delta=pred, state=state, control_drift_budget=budget, observed_ROI_and_control_envelope=observed_range,
            conditional_without_tail04=not row['time_bracketed'],
            setting_conflict=row['setting_conflict'],
            conditional=budget is None or not row['time_bracketed'] or row['setting_conflict'],
            isolates_probe3_single_channel_mechanism=False))
    if any(q['conditional_without_tail04'] for q in summaries.values()):
        issues.append('OPEN: 部分页/场景只有单侧 04；可给 RAW 条件误差，但该页首尾漂移与未知中间漂移上限未闭合。')
    overall = {}
    for kind in ('screen', 'physical'):
        for setting in SETTINGS[1:]:
            use = [r for r in rows if r['kind'] == kind and r['setting'] == setting and r['ROI'] == .4 and r['valid']]
            if use:
                q = summarize(use, cm)
                q.update(pages=sorted({r['page'] for r in use}), setting_conflict=any(r['setting_conflict'] for r in use),
                         conditional_without_tail04=any(not r['time_bracketed'] for r in use))
                overall[kind+'/'+setting] = q
    if any(f['setting_order'] != '04 Std' for f in ordered) and not overall:
        issues.append('OPEN: 没有任何配方的有效对比块，不能出具实拍预测误差。')
    return plain(dict(rows=rows, summaries=summaries, overall=overall, identity=identity_rows, drift=drift, sign_gaps=signs))


def report(args, out, frames, result, issues, elapsed):
    screen = [f for f in frames if f['kind'] == 'screen']
    synthetic = sum(not f['has_raw'] for f in frames)
    lines = [f'# 午间分析 {args.photos.name}', '',
        f'已提取 {len(frames)} 帧，其中屏幕 {len(screen)} 帧、无 RAW 的合成/页面图 {synthetic} 帧。耗时 {elapsed:.1f} 秒。', '',
        f'绑定 g156 test DAT SHA-256 `{DAT_SHA}`。照片本身不能证明安装的是这个 DAT。', '',
        '主测为每块中央 40%，另算 30% / 50%。DE00 比较实拍 JPEG 与现行模型预测；正 ΔL 为偏亮，正 ΔC 为偏艳，正色相角沿 Lab 逆时针。', '',
        '## 每条配方、每页', '',
        '| 配方 / 页或场景 | n | DE00 中位数 | P95 | 最差块 | ΔL | ΔC | 色相角偏差 | 条件 |',
        '| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |']
    if any(f.get('synthetic') for f in frames):
        lines[2:2] = ['本报告包含合成输入，用于验证流程，不能据此声称配方实拍通过。', '']
    overall_lines = ['## 每条配方合计', '', '| 批次 / 配方 | n | DE00 中位数 | P95 | 条件 |', '| --- | ---: | ---: | ---: | --- |']
    for key, q in result.get('overall', {}).items():
        status = ('顺序/响应冲突；' if q['setting_conflict'] else '')+('缺尾04' if q['conditional_without_tail04'] else '有首尾04')
        overall_lines.append(f"| {key} | {q['n']} | {q['de00_median']:.3f} | {q['de00_p95']:.3f} | {status} |")
    if result.get('overall'):
        at = lines.index('## 每条配方、每页')
        lines[at:at] = overall_lines+['']
    for key, q in result.get('summaries', {}).items():
        hue = '无稳定方向' if q['median_hue_error_deg'] is None else f"{q['median_hue_error_deg']:+.2f}°"
        status = ('顺序/响应冲突；' if q['setting_conflict'] else '')+('缺尾04' if q['conditional_without_tail04'] else '首尾04')
        lines.append(f"| {key} | {q['n']} | {q['de00_median']:.3f} | {q['de00_p95']:.3f} | {q['worst']['patch']} ({q['worst']['DE00']:.3f}) | {q['median_delta_L']:+.2f} | {q['median_delta_C']:+.2f} | {hue} | {status} |")
    if not result.get('summaries'):
        lines.extend(['', 'OPEN: 本批没有可比较的配方实拍；页面识别或 ramp 提取不等于配方验收。'])
    lines.extend(['', '## 肤色、蓝色、绿叶与符号缺口', '',
        '| 配方 / 页 | 区域 | n | DE00 中位数 | P95 | ΔL | ΔC |', '| --- | --- | ---: | ---: | ---: | ---: | ---: |'])
    for key, q in result.get('summaries', {}).items():
        for name, group in q['groups'].items():
            if group['n']:
                lines.append(f"| {key} | {name} | {group['n']} | {group['de00_median']:.3f} | {group['de00_p95']:.3f} | {group['median_delta_L']:+.2f} | {group['median_delta_C']:+.2f} |")
    signs = result.get('sign_gaps', [])
    for component in ('Cb', 'Cr'):
        use = [r for r in signs if r['component'] == component]
        conditional = sum(r['state']=='opposite_sign' and r['conditional'] for r in use)
        lines.extend(['', f"{'肤色 Cb' if component == 'Cb' else '蓝色 Cr'}：方向反号 {sum(r['state']=='opposite_sign' for r in use)} 块，其中 {conditional} 块缺参照或有设置冲突，只作为条件结果。同号 {sum(r['state']=='same_sign' for r in use)} 块，弱分量未判 {sum(r['state']=='unresolved_small_component' for r in use)} 块。"])
    if signs:
        lines.extend(['', '逐块有符号响应、参照预算和反号明细只保存在被忽略的 local/summary.json，不写入公开 Markdown。'])
    lines.extend(['', '这里比较完整配方相对 04 的响应，不能单独归因于 probe3 的 R±/B± 节点机制。符号门使用三 ROI 与独立 04 漂移包络，再留 0.25 输出码诊断余量；这不是置信区间。缺独立尾 04 或分量落在漂移、量化范围内时，符号结论仍为条件结果。', '',
        '## 顺序与响应', '', '| 帧 | 顺序默认 | 响应校验 | 余量 DE00 | 状态 |', '| --- | --- | --- | ---: | --- |'])
    for r in result.get('identity', []):
        margin = '' if r['margin'] is None else f"{r['margin']:.3f}"
        lines.append(f"| {r['frame']} | {r['order']} | {r['response']} | {margin} | {'冲突，未硬判' if r['conflict'] else 'unknown，保留默认假设' if r['response']=='unknown' else '响应相容'} |")
    lines.extend(['', '## 提取与 OPEN', '', '| 帧 | 类型 | 页面 | 区域数 | RAW |', '| --- | --- | --- | ---: | --- |'])
    for f in frames:
        lines.append(f"| {f['frame']} | {f['kind']} | {f['identity']['page']} | {len(f['patches']['0.4'])} | {'有' if f['has_raw'] else '无'} |")
    if result.get('drift'):
        lines.extend(['', '## 独立 04 与 RAW 漂移', '', '| 04 帧 / 参照 | 页或场景 | RAW R/G/B 中位变化 | 校正后 DE00 中位数 | P95 |', '| --- | --- | --- | ---: | ---: |'])
        for r in result['drift']:
            q = r['corrected']
            raw_change = ' / '.join(f'{v*100:+.2f}%' for v in r['raw_relative_change_median'])
            if q['n']:
                lines.append(f"| {r['frame']}/{r['reference']} | {r['scene']} | {raw_change} | {q['de00_median']:.3f} | {q['de00_p95']:.3f} |")
    if result.get('summaries'):
        lines.extend(['', '## ROI 与端点参照敏感性', '', '| 配方 / 页 | 中央30% 中位/P95 | 中央40% 中位/P95 | 中央50% 中位/P95 | 首/尾预测差 P95 |', '| --- | --- | --- | --- | ---: |'])
        for key, q in result['summaries'].items():
            values = []
            for fr in ('0.3', '0.4', '0.5'):
                v = q['ROI_sensitivity'][fr]
                values.append(f"{v['de00_median']:.3f}/{v['de00_p95']:.3f}" if v['n'] else '无有效块')
            lines.append(f"| {key} | {' | '.join(values)} | {q['endpoint_spread_DE00_p95']:.3f} |")
    periodic = [p for f in frames if f['kind'] in ('screen', 'probe3') for p in f['patches']['0.4']]
    flagged = [p for p in periodic if any(v.get('periodic_pattern_flag') for v in p.get('periodicity_diagnostic', {}).values())]
    if periodic:
        lines.extend(['', f'屏幕周期纹诊断：{len(flagged)}/{len(periodic)} 个中央 ROI 触发既有频谱门。该门只提示条纹或摩尔纹，不自动改颜色，也不把它当成厂商规格。逐块频谱与 4×4 子区域统计在 local 帧明细中。'])
    for issue in dict.fromkeys(issues):
        lines.extend(['', '- '+issue])
    lines.extend(['', 'RAW 逐块扣黑并按 AsShotNeutral 处理，用于相同块的输入漂移校正。RAW 的 BT.601 数值只是线性传感器代理，不是相机内部 YCbCr，不对它和 JPEG 直接声称颜色准确度。', '',
        '屏幕 CSS 数值只用于识页，P3-D65 屏幕、局部调光和摩尔纹不按网页标称 Lab 校准。山寨色卡不使用印刷值。MOUNT 参考仍是迁移模型，照片误差报告才是本次待测结果。', '',
        f'逐块数值、输入哈希、552 B 记录和 ROI 叠图均在 [local 明细](local/{out.name}/summary.json)。', ''])
    target = HERE/('REPORT_'+out.name+'.md')
    target.write_text('\n'.join(lines))
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('photos', type=Path)
    parser.add_argument('--manifest', type=Path, help='local JSON：逐帧设置/四角/实物 ROI')
    parser.add_argument('--kind', choices=('auto', 'screen', 'physical', 'probe3'), default='auto')
    parser.add_argument('--label', help='local 输出标签，仅字母数字 _ -')
    parser.add_argument('--extract-only', action='store_true')
    parser.add_argument('--fresh', action='store_true')
    parser.add_argument('--recursive', action='store_true')
    parser.add_argument('--max-frames', type=int)
    args = parser.parse_args()
    start = time.monotonic()
    absolute = args.photos.absolute()
    if str(absolute).startswith('/Volumes/') and not absolute.is_relative_to('/Volumes/Workspace'):
        parser.error('禁止从相机或 SD 挂载卷读取；先由机主复制到仓库 captures/')
    args.photos = absolute.resolve(strict=True)
    if str(args.photos).startswith('/Volumes/') and not args.photos.is_relative_to('/Volumes/Workspace'):
        parser.error('输入解析到其它挂载卷，禁止读取')
    if not args.photos.is_dir():
        parser.error('照片输入必须为目录')
    lock = setup()
    frozen_sources = source_identity()
    label = args.label or re.sub('[^A-Za-z0-9_-]', '_', args.photos.name)
    if not re.fullmatch('[A-Za-z0-9_-]+', label):
        parser.error('--label 只能为字母数字 _ -')
    out = LOCAL/label
    out.mkdir(exist_ok=True)
    args.manifest_data = read(args.manifest.resolve(strict=True)) if args.manifest else {}
    sys.addaudithook(guard)
    field, sampler, cm, periodic = loaders()
    if sha(DAT) != DAT_SHA:
        raise ValueError('g156 test DAT SHA 不符，停止本次分析')
    pages = read(ROOT/'research/color_references/screen_chart.json')['pages']
    pairs = discover(args.photos, args.recursive)
    if args.max_frames:
        pairs = pairs[:args.max_frames]
    if not pairs:
        raise ValueError('没有 DNG+JPEG 成对照片或合成 PNG')
    input_manifest = args.photos/'SHA256SUMS'
    if input_manifest.is_file():
        expected = {}
        for line in input_manifest.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            digest, filename = line.split(None, 1)
            filename = filename.lstrip('*')
            target = (args.photos/filename).resolve()
            if not target.is_relative_to(args.photos) or len(digest) != 64:
                raise ValueError('输入 SHA256SUMS 路径或摘要不合法')
            expected[str(target)] = digest.lower()
        verified = []
        for pair in pairs:
            for p in pair.values():
                if str(p) in expected:
                    if sha(p) != expected[str(p)]:
                        raise ValueError('输入原清单 SHA 不符: '+p.name)
                    verified.append(str(p))
        dump(out/'input-manifest-check.json', dict(manifest=str(input_manifest), manifest_sha256=sha(input_manifest), verified=verified))
    frames, issues, failures, exclusions = [], [], [], []
    def kind_hint(i, override):
        value = override.get('kind', args.kind)
        if value in ('screen', 'physical', 'probe3'):
            return value
        if len(pairs) >= 64:
            return 'screen' if i < 64 else 'physical'
        return 'unknown'
    for i, pair in enumerate(pairs):
        override = args.manifest_data.get('frames', {}).get(pair['jpeg'].stem, {})
        if override.get('kind') == 'skip':
            excluded = dict(frame=pair['jpeg'].stem, reason=override.get('reason'), kind_hint=kind_hint(i, override))
            if override.get('reason') and override.get('manual_confirmation_required') is False:
                exclusions.append(excluded)
                print('EXCLUDED', pair['jpeg'].name, override['reason'], flush=True)
            else:
                issues.append('OPEN: 未确认的手动跳过 '+pair['jpeg'].stem)
                failures.append(dict(excluded, skipped=True))
            continue
        try:
            f = extract_one(pair, override, args, out, field, sampler, pages, i, len(pairs), periodic)
            frames.append(f)
            dump(out/'progress.json', dict(completed=len(frames), total=len(pairs), last=f['frame']))
        except Exception as e:
            message = f'{type(e).__name__}: {e}'
            failures.append(dict(frame=pair['jpeg'].stem, error=message, kind_hint=kind_hint(i, override)))
            issues.append('OPEN: '+pair['jpeg'].stem+' 提取失败，原因详见 local summary.json。')
            print('OPEN', pair['jpeg'].name, message, flush=True)
    if failures:
        issues.append('OPEN: 存在提取失败帧，自动分组不能证明没有缺帧；请在 manifest 逐帧确认设置。')
        for f in frames:
            affected = any(r['kind_hint'] in (f['kind'], 'unknown') for r in failures)
            f['order_untrusted'] = affected and 'setting' not in f['override']
    arrange([f for f in frames if f['kind'] in ('screen', 'physical')])
    intake = dict(schema='noon-sweep-manifest/1', frames={f['frame']:dict(kind=f['kind'],
        **({'page':f['identity']['page']} if f['kind'] == 'screen' else {'scene':f.get('scene', 'daylight')}),
        setting=f.get('setting_order', '04 Std'), manual_confirmation_required=True) for f in frames if f['kind'] in ('screen', 'physical')},
        physical_template=dict(chart=dict(cols=6, rows=4), rois=[]))
    for i, pair in enumerate(pairs):
        name = pair['jpeg'].stem
        if name not in intake['frames']:
            screen_hint = args.kind == 'screen' or len(pairs) >= 64 and i < 64
            intake['frames'][name] = dict(kind='screen' if screen_hint else 'physical', manual_confirmation_required=True,
                setting_hint=SETTINGS[min(i//8, 7)] if screen_hint else '04 Std',
                **({'page_hint':['T1','T2','T3','T4','V1','V2','V3','V4'][i%8]} if screen_hint else {'scene':'daylight'}))
    if args.manifest:
        # Never replace a confirmed input manifest with a new unconfirmed draft.
        dump(out/'intake-manifest-applied.json', dict(args.manifest_data,
             source_manifest_sha256=sha(args.manifest), extracted_frames=[f['frame'] for f in frames]))
    else:
        dump(out/'intake-manifest.json', intake)
    result = dict(rows=[], summaries={}, identity=[], drift=[])
    if not args.extract_only and any(f['kind'] in ('screen', 'physical') for f in frames):
        try:
            result = analyse(frames, out, cm, issues)
        except Exception as e:
            dump(out/'prediction-error.json', dict(type=type(e).__name__, message=str(e)))
            issues.append(f'OPEN: 参考预测失败 {type(e).__name__}，原因详见 local prediction-error.json。')
            print(issues[-1], flush=True)
    elif args.extract_only:
        issues.append('OPEN: 本次 --extract-only，只验证取样，未跑预测。')
    if any(f['kind'] == 'probe3' for f in frames):
        checks = []
        for f in frames:
            if f['kind'] != 'probe3':
                continue
            reference = ROOT/'research/probe_pack_r3/field/local/frames'/(f['frame']+'.json')
            if reference.exists():
                prior = read(reference)['patches']['0.5']
                actual = f['patches']['0.5']
                diffs = {key:float(np.max(abs(np.array([p[key] for p in actual])-np.array([p[key] for p in prior])))) for key in ('jpeg_mean', 'native_ycc_mean', 'raw_wb')}
                checks.append(dict(frame=f['frame'], max_abs_diff=diffs, pass_exact=all(v == 0 for v in diffs.values())))
        dump(out/'probe3-rerun.json', checks)
        issues.append('probe3 为 ramp 提取复跑，只校验其既有 50% ROI；新增主测为 40%，不把探针条目当作 g156 配方。')
        if checks and not all(c['pass_exact'] for c in checks):
            issues.append('OPEN: probe3 复提取与既有值有差异，见 local/probe3-rerun.json')
    elapsed = time.monotonic()-start
    if source_identity() != frozen_sources:
        issues.append('OPEN: 运行期间代码或页面模板有变化，本次回执不能绑定最终源码。')
    changed_inputs = [name for f in frames for name, digest in f['input'].items() if sha(name) != digest]
    if changed_inputs:
        issues.append('OPEN: 处理期间照片有变化，详见 local/input-drift.json。')
        dump(out/'input-drift.json', changed_inputs)
    if sha(DAT) != DAT_SHA:
        issues.append('OPEN: 运行期间 DAT 有变化，本次预测不能绑定最终 DAT。')
    if (out/'model-provenance.json').exists() and result['rows']:
        changed = [rel for rel, digest in read(out/'model-provenance.json')['inputs'].items() if sha(ROOT/rel) != digest]
        if changed:
            issues.append('OPEN: 运行期间参考模型输入有变化，详见 local/model-input-drift.json。')
            dump(out/'model-input-drift.json', changed)
    summary = dict(schema='noon-sweep/1', input_directory=str(args.photos), dat_sha256=DAT_SHA,
        elapsed_seconds=elapsed, frame_count=len(frames), failures=failures, exclusions=exclusions, issues=list(dict.fromkeys(issues)),
        summaries=result['summaries'], overall=result.get('overall', {}), identity=result['identity'], drift=result['drift'], sign_gaps=result.get('sign_gaps', []),
        environment=dict(python=sys.executable, isolated=bool(sys.flags.isolated), nice=os.getpriority(os.PRIO_PROCESS, 0), compute_processes=1,
        numerical_threads=1, network=False, camera_or_SD=False), source_sha256=frozen_sources)
    dump(out/'all-patches.json', result['rows'])
    if result['rows']:
        keys = ['frame', 'kind', 'setting', 'page', 'patch', 'group', 'ROI', 'valid', 'DE00', 'chroma_error', 'hue_error_deg', 'time_bracketed', 'setting_response', 'setting_conflict']
        with (out/'patches.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, keys, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(result['rows'])
    elapsed = time.monotonic()-start
    summary['elapsed_seconds'] = elapsed
    dump(out/'summary.json', summary)
    path = report(args, out, frames, result, issues, elapsed)
    completed = time.monotonic()-start
    dump(out/'completion.json', dict(elapsed_seconds=completed, report_sha256=sha(path),
        summary_sha256=sha(out/'summary.json'), completed_utc=dt.datetime.now(dt.timezone.utc).isoformat()))
    print('REPORT', path, flush=True)
    print('LOCAL', out, 'elapsed_s', round(completed, 2), flush=True)
    # Exit 2 distinguishes incomplete intake from a verified recipe comparison.
    return 2 if failures or any(i.startswith('OPEN') for i in issues) else 0


if __name__ == '__main__':
    raise SystemExit(main())
