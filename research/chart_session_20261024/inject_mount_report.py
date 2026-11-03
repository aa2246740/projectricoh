"""Inject operator-reported lens/aperture/settings without changing camera EXIF."""
import argparse
import copy
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import session_runtime as s


def template():
    return {'schema': 'ricoh-mount-user-report/1', 'source': 'user_report',
        'lens': {'focal_length_mm': 35, 'maximum_aperture_f': 2.0,
                 'brand_model': None, 'physical_instance_id': None},
        'capture': {'actual_aperture_f': None,
            'corrections': {'peripheral_illumination': None, 'red_blue_shading': None, 'distortion': None}},
        'note': '35mm f/2 is the user-reported lens, not the actual shooting aperture. Remaining fields await user confirmation.'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write-template', action='store_true')
    ap.add_argument('--report', type=Path, default=s.LOCAL/'operator_reports/mount.pending.json')
    ap.add_argument('--frames', type=Path, default=s.LOCAL/'analysis-final/exchange/mount/frames.json')
    ap.add_argument('--output', type=Path, default=s.LOCAL/'operator_reports/mount.frames.user-report.json')
    args = ap.parse_args()
    s.guard()
    sys.addaudithook(s.audit)
    if args.write_template:
        assert not args.report.exists()
        s.dump(args.report, template())
        print('User report template written; actual aperture/settings remain null.')
        return
    report = json.loads(args.report.read_text())
    assert report['schema'] == 'ricoh-mount-user-report/1' and report['source'] == 'user_report'
    aperture = report['capture']['actual_aperture_f']
    assert aperture is None or type(aperture) in (int, float) and aperture > 0
    data = json.loads(args.frames.read_text())
    assert not args.output.exists()
    for f in data['frames'].values():
        assert f['module'] == 'mount'
        f.setdefault('exif_observations', {'aperture_f': f.get('exif_aperture_f', f.get('aperture_f')),
                                         'lens_model': f.get('original_exif_lens_model', '')})
        f['operator_report'] = copy.deepcopy(report)
        f['aperture_f'] = aperture
        f['aperture_source'] = 'user_report' if aperture is not None else 'unknown'
        reported_id = report['lens']['physical_instance_id']
        if not reported_id:
            assert set(data['frames']) <= {f'R805{n}' for n in range(1261,1269)}, 'A new session needs an explicit physical lens ID'
        f['lens_id'] = reported_id or 'mount-20261024-user-reported-35mm-f2'
        f['lens_id_source'] = 'user_report' if reported_id else 'analysis_assigned_session_label'
        f['lens_id_scope'] = 'this capture session only; no camera EXIF, brand, model or serial is inferred'
        f['lens_note'] = 'user-reported 35mm f/2; does not establish actual aperture or EXIF lens model'
        f['corrections'] = copy.deepcopy(report['capture']['corrections'])
        f['corrections_source'] = 'user_report'
        f['calibration_metadata_ready'] = bool(aperture and f['lens_id'] and
            all(v not in (None, 'unknown') for v in f['corrections'].values()))
    data['metadata_complete'] = all(f['calibration_metadata_ready'] for f in data['frames'].values())
    data['operator_report_path'] = str(args.report.resolve())
    data['operator_report_sha256'] = s.sha(args.report)
    s.dump(args.output, data)
    print(json.dumps({'frames': len(data['frames']), 'metadata_complete': data['metadata_complete'],
                      'EXIF_changed': False, 'aperture_f': aperture}, ensure_ascii=False))


if __name__ == '__main__':
    main()
