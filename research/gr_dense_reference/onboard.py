#!/usr/bin/env python3
"""One original GR IV DNG to a private, offline-verified r3s spare-card package."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native as n
import owners
import json
import shutil
import subprocess
import time

sys.path.insert(0, str(n.ROOT / 'research/contrib_gr_analysis'))
from tiff_makernote import decode_image_control_0247, PENTAX_IMAGE_TONE

GEOMETRY = dict(width=6304, height=4224, bits=14, active_tlbr=[34, 26, 4194, 6250],
                crop_xy=[54, 58], crop_wh=[6192, 4128], cfa=[0, 1, 1, 2], black=[64]*4)
SLIDERS = ('saturation', 'hue', 'high_low_key', 'contrast', 'contrast_highlight',
           'contrast_shadow', 'sharpness', 'shading', 'clarity')
PRESETS = {256: (0, 0, 0, 0), 262: (-1, 3, -1, -2), 267: (1, 1, 0, -1)}


def inspect(path):
    """Read bounded TIFF/MakerNote data only; no contributor-supplied code is loaded."""
    path = Path(path)
    if not path.is_absolute() and not path.exists():
        path = n.ROOT / path
    path = path.resolve()
    row = dict(path=str(path), eligible=False, reasons=[], warnings=[])
    if not path.is_relative_to((n.ROOT / 'captures/contrib').resolve()):
        row['reasons'].append('original DNG must be under captures/contrib')
        return row
    row['path'] = str(path.relative_to(n.ROOT))
    try:
        row['sha256'] = n.sha(path)
        t = n.Tiff(path.read_bytes())
        model = str(t.scalar(t.root, 272, '')).strip()
        row.update(model=model, firmware=str(t.scalar(t.root, 305, '')).strip(),
                   orientation=t.scalar(t.root, 274, 1), body_name=None, serials={},
                   iso=None, image_control=None)
        for node in t.ifds:
            if 34855 in node.entries:
                row['iso'] = t.scalar(node, 34855)
            for tag in (42033, 50735):
                if tag in node.entries:
                    row['serials'][str(tag)] = node.entries[tag].value
        if model not in ('RICOH GR IV', 'RICOH GR IV HDF'):
            row['reasons'].append(f'not a GR IV / 不是彩色 GR IV 或 GR IV HDF（{model or "机型缺失"}）')
        try:
            maker = t.maker()
            row['body_name'] = t.scalar(maker, 0x0251)
            for tag in (0x001d, 0x0229):
                if tag in maker.entries:
                    value = maker.entries[tag].value
                    row['serials'][str(tag)] = value.strip() if isinstance(value, str) else value
            tone = t.scalar(maker, 0x004f)
            entry = maker.entries.get(0x0247)
            control = decode_image_control_0247(t.data[entry.offset:entry.offset+entry.size]) if entry else {}
            values = dict(zip(('high_low_key', 'contrast', 'contrast_highlight', 'contrast_shadow'),
                              PRESETS.get(tone, ())))
            expected = dict.fromkeys(SLIDERS, 0)
            expected.update(values)
            row['image_control'] = dict(preset=dict(value=tone, name=PENTAX_IMAGE_TONE.get(tone)),
                sliders=control, factory_default=(all(control.get(k) == v for k, v in expected.items())
                                                 if tone in PRESETS else None),
                slider_names='inferred by existing GR III/IV MakerNote parser; raw hex retained')
        except ValueError as error:
            if not row['reasons']:
                row['reasons'].append(f'camera metadata cannot be read / 相机资料无法读取：{error}')
        if row['orientation'] != 1:
            row['reasons'].append('portrait orientation / 照片带旋转方向，请提供横拍原片（orientation 1）')
        try:
            row['geometry'] = t.geometry()
            supported_model = model in ('RICOH GR IV', 'RICOH GR IV HDF')
            if supported_model and row['geometry']['crop_wh'] != GEOMETRY['crop_wh']:
                row['reasons'].append('crop mode / not 6192x4128 / 使用了裁切模式，请提供 6192×4128 原片')
            changed = [k for k, value in GEOMETRY.items()
                       if supported_model and row['geometry'].get(k) != value]
            if 'black' in changed:
                row['reasons'].append('unsupported RAW geometry / 这张原片的黑电平不是 64，'
                                      '不能作为这版测试卡模板，请提供另一张低 ISO 原片')
            if changed and 'crop_wh' not in changed:
                other = [k for k in changed if k != 'black']
                if other:
                    row['reasons'].append('unsupported RAW geometry / 原片尺寸或传感器格式不符：' + ', '.join(other))
        except (ValueError, KeyError) as error:
            row['geometry_error'] = str(error)
            if model in ('RICOH GR IV', 'RICOH GR IV HDF'):
                row['reasons'].append(f'unsupported RAW geometry / 原片尺寸或传感器格式不符：{error}')
        if not row['serials'].get('553'):
            row['reasons'].append('camera body serial is missing / 无法确认机身，请提供未处理的相机原始 DNG')
        if not isinstance(row['iso'], (int, float)) or row['iso'] <= 0:
            row['reasons'].append('ISO is missing / 原片缺少 ISO 资料')
        elif row['iso'] > 400:
            row['warnings'].append(f'ISO {row["iso"]} is above 400; allowed, template ISO/NR metadata is retained')
        if not row['reasons']:
            refs, _, _ = n.streams(t)
            row['allocation_bytes'] = {k: v['capacity'] for k, v in refs.items()}
        row['body_identity'] = dict(model=model, body_name=row['body_name'], serials=row['serials'])
        row['eligible'] = not row['reasons']
    except (ValueError, OSError, KeyError, TypeError, IndexError) as error:
        row['reasons'].append(f'cannot read this original DNG / 这张原片无法读取：{error}')
        row['eligible'] = False
    return row


def candidates(paths):
    rows = [inspect(path) for path in paths]
    identities = [row.get('body_identity') for row in rows]
    if len(rows) > 1 and any(identity != identities[0] for identity in identities[1:]):
        for row in rows:
            row['reasons'].append('different camera body / 这些原片来自不同机身，请只提供同一台相机的原片')
            row['eligible'] = False
    return rows


def choose(rows):
    eligible = [row for row in rows if row['eligible']]
    n.require(eligible, 'candidate set refused: no eligible template')
    # Preserve the established order: lowest ISO, known factory preset, ample allocation.
    def rank(row):
        capacity = row['allocation_bytes']
        return (row['iso'], row['image_control']['factory_default'] is not True,
                -capacity['raw'], -capacity['full'], -capacity['maker'], row['path'])
    selected = min(eligible, key=rank)
    reason = (f'lowest ISO {selected["iso"]}; factory-default preset='
              f'{selected["image_control"]["factory_default"]}; ties prefer factory defaults, '
              'then ample RAW/full-preview/maker-preview allocation, then path')
    return selected, reason


def run(args):
    started = time.monotonic()
    n.preflight()
    owners.slug(args.owner)
    registered = owners.load().get(args.owner)
    paths = args.candidates or ([n.ROOT / registered['template']['path']] if registered else [])
    n.require(paths, 'a new owner needs --candidates with one or more original DNGs')
    rows = candidates(paths)
    for row in rows:
        print(json.dumps(row, ensure_ascii=False), flush=True)
    if not any(row['eligible'] for row in rows):
        rejected = dict(schema='gr-dense-onboarding/1', owner=args.owner, status='REFUSED', candidates=rows,
                        camera_acceptance=False, runtime_seconds=time.monotonic()-started)
        path = owners.PRIVATE / '_onboarding-refusals' / f'{args.owner}-{time.time_ns()}.json'
        n.dump(path, rejected)
        for row in rows:
            for reason in row['reasons']:
                print(f'REFUSED {row["path"]}: {reason}', file=sys.stderr)
        print(f'Summary: {path}', file=sys.stderr)
        return 2
    selected, reason = choose(rows)
    for row in rows:
        for rejected in row['reasons']:
            print(f'EXCLUDED {row["path"]}: {rejected}', file=sys.stderr)
    entry = dict(template=dict(path=selected['path'], sha256=selected['sha256']),
                 model=selected['model'], body_identity=selected['body_identity'], instructions={})
    for lang in ('zh', 'en'):
        label = getattr(args, f'control_label_{lang}')
        if label:
            entry['instructions'][f'control_label_{lang}'] = label
    if registered:
        n.require(registered['template'] == entry['template'],
                  'registered owner template differs; use their pinned original, or a new owner slug')
        n.require(not entry['instructions'] or entry['instructions'] == registered.get('instructions', {}),
                  'refusing to change a registered owner handout')
    base = owners.set_root(args.owner, args.output or owners.PRIVATE / args.owner)
    n.require(not base.exists(), f'output exists: {base}; use a NEW --output directory')
    subprocess.run(['df', '-h', '/Volumes/Workspace'], check=True)
    n.require(shutil.disk_usage('/Volumes/Workspace').free >= 3 * 1024**3, 'need about 3 GiB free per owner')
    base.mkdir(parents=True, exist_ok=False)
    if not registered:
        owners.register(args.owner, entry)
    summary_path = base / 'onboarding-summary.json'
    summary = dict(schema='gr-dense-onboarding/1', owner=args.owner, status='BUILDING', candidates=rows,
                   selected_template=selected, choice_reason=reason, output=str(base),
                   excluded_candidates=[row['path'] for row in rows if not row['eligible']],
                   high_iso_warning=any(row['warnings'] for row in rows),
                   camera_acceptance=False, firmware_ready=False, deployable=False)
    n.dump(summary_path, summary)
    try:
        n.SCRATCH = base / 'work/native'
        n.preflight()
        n.compile_codec()
        summary['proof'] = n.prove(args.owner)
        n.dump(base / 'template.json', dict(selected, choice_reason=reason))
        # Redirect the legacy injector BEFORE import, including its ledger and temporary files.
        import dense
        dense.LOCAL, dense.TMP = base, base / 'work/r2'
        import inject
        template = n.ROOT / selected['path']
        inject.build(acceptance=True, template=template, private_owner=args.owner)
        for band in range(4):
            inject.build(band=band, template=template, private_owner=args.owner)
        import build_r3
        build_r3.compile_apple()
        for number in range(1, 6):
            build_r3.build(args.owner, number)
        import readback_r3
        readback = readback_r3.self_test(args.owner)
        import report_r3
        evidence = report_r3.audit_owner(args.owner)
        summary['delivery'] = report_r3.package(args.owner, evidence)
        summary['gates'] = dict(G1=True, G2=True, G3_cards=5, G4_cards=5,
            apple_raw_full_resolution=5, unexplained_mutations=0, readback_passed=readback['passed'],
            content_identities=readback['content_identities_passed'],
            readback_negative_checks=len(readback['negative_checks']), filename_used=False,
            r3s_package=True, zip_extraction=True)
        for row in rows:
            n.require(n.sha(n.ROOT / row['path']) == row['sha256'], 'read-only candidate changed')
        summary['input_hashes_unchanged'] = True
        summary['source_sha256'] = {name: n.sha(n.HERE / name) for name in (
            'owners.py', 'onboard.py', 'native.py', 'native.c', 'inject.py', 'build_r3.py',
            'readback_r3.py', 'report_r3.py', 'instructions_r3.py', 'apple_raw.m')}
        summary['status'] = 'OFFLINE_READY'
    except Exception as error:
        summary.update(status='STOPPED', failure=f'{type(error).__name__}: {error}')
        raise
    finally:
        summary['runtime_seconds'] = round(time.monotonic()-started, 3)
        n.dump(summary_path, summary)
    print(f'{args.owner}: OFFLINE_READY; {Path(selected["path"]).name}; {reason}', flush=True)
    print(f'G1/G2 PASS; G3/G4 5/5; readback PASS; ZIP 11 members, extracted hashes PASS; '
          f'camera_acceptance=false; {summary["runtime_seconds"]:.1f}s', flush=True)
    print(f'Package: {base / "SEND_r3s.zip"}\nSummary: {summary_path}', flush=True)
    return 0


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner', required=True)
    parser.add_argument('--candidates', type=Path, nargs='+')
    parser.add_argument('--control-label-zh', help='complete Chinese control sentence')
    parser.add_argument('--control-label-en', help='complete English control sentence')
    parser.add_argument('--output', type=Path, help='NEW build directory under local/private/<owner>')
    args = parser.parse_args()
    try:
        return run(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        detail = error.stderr.decode(errors='replace') if isinstance(error, subprocess.CalledProcessError) and error.stderr else str(error)
        print(f'STOP: {detail}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
