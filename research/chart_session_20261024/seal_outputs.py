"""Verify the final fresh Mount path, then seal and verify all task artifacts."""
import ast
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import session_runtime as s


def main():
    s.guard()
    for path in s.HERE.glob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
    out = s.LOCAL / 'analysis-final'
    verification = json.loads((out / 'verification.json').read_text())
    assert verification['passed'] and len(verification['04_RAW_direct_prediction_all_six_pages_best_04']) == 6
    fresh = json.loads((s.LOCAL / 'adapter-final-probe/frames/R8051262.json').read_text())
    final = json.loads((out / 'frames/R8051262.json').read_text())
    assert fresh['meta']['f'] is None and not fresh['metadata_errors'] and fresh['status'] == 'ok'
    assert fresh['valid_patches'] == final['valid_patches']
    assert fresh['patches'] == final['patches']
    s.dump(s.LOCAL / 'delivery.json', {'passed': True, 'fresh_Mount_extractor_valid_patches': fresh['valid_patches'],
        'fresh_Mount_all_patch_records_equal_repaired_final': True,
        'accepted_frame_count': verification['accepted_frames'], 'excluded_A': verification['excluded_A'],
        'source_inputs_unchanged': verification['unchanged_inputs_verified'],
        'all_task_python_syntax_checked': True, 'no_fit_executed': True})
    review=s.LOCAL/'moire-review-v2/verification.json'
    if review.exists():
        v=json.loads(review.read_text())
        assert v['passed'] and v['native_RAW_patch_records_reproduced']==4988
        assert (s.HERE/'REPORT.md').read_bytes()==(s.HERE/'MOIRE_REVIEW.md').read_bytes()
        s.dump(s.LOCAL/'delivery_moire_review.json',{'passed':True,'decision':'a','JPEG_moire_exclusion_amplitude_codes':6,
            'independent_case_count':len(v['independently_recomputed_cases']),
            'RAW_records_reproduced':v['native_RAW_patch_records_reproduced'],
            'source_inputs_unchanged':v['inputs_unchanged'],'no_fit_executed':True})
    manifest = s.HERE / 'SHA256SUMS'
    paths = sorted(path for path in s.HERE.rglob('*') if path.is_file() and path != manifest)
    manifest.write_text(''.join(f'{s.sha(path)}  {path.relative_to(s.HERE)}\n' for path in paths))
    for line in manifest.read_text().splitlines():
        digest, rel = line.split(maxsplit=1)
        assert s.sha(s.HERE / rel) == digest, rel
    print(json.dumps({'checksums_verified': len(paths), 'manifest_sha256': s.sha(manifest),
                      'fresh_Mount_valid_patches': fresh['valid_patches']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
