"""Replay original r2 probes, recording every source adaptation as a diff."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import sys

BUNDLE = Path(__file__).resolve().parent
OUT = Path(os.environ.get('REVIEW_OUT', BUNDLE))
OLD = BUNDLE.parent / 'review_studio_gpu_preview_r2'
TMP = Path(os.environ['REVIEW_TMP'])
SOURCE = Path(os.environ['REVIEW_SOURCE'])
CASES = {
    'media_root_race': 'media-root-race.json',
    'path_delete_race': 'path-delete-race.json',
    'card_reader_retarget': 'card-reader-retarget.json',
    'lut_reimport_probe': 'lut-reimport-probe.json',
    'http_boundary_extra': 'http-boundary-extra.json',
}


def adapt(case):
    old = (OLD / (case + '.py')).read_text()
    new = old.replace('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-gpu-preview-r2', str(TMP / 'r2-replay'))
    for index, value in enumerate(('/Users/wu/Pictures/GXR Studio', '/Users/wu/Pictures/GXR 导出', '/Users/wu/Library/Application Support/GXR Studio')):
        new = new.replace(value, str(TMP / ('unused-protected-' + str(index))))
    new = new.replace("WT=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/gpu-preview')", f'WT=Path({str(SOURCE)!r})')
    if case == 'media_root_race':
        new = new.replace('for mode in (True,False):', 'for mode in (True,):')
        new = new.replace("if not swapped and ((mode and Path(path)==root) or (not mode and str(path)==str(root/'a/b/photo.DNG'))):",
                          "if not swapped and (Path(path)==root or (str(path)==root.name and kwargs.get('dir_fd') is not None)):")
        new = new.replace(",use_dir_fd=mode", '')
    if case == 'path_delete_race':
        new = new.replace("for mode in ('dir_fd','path'):", "for mode in ('dir_fd',):")
        new = new.replace("cls=privacy.PrivateDir if mode=='dir_fd' else privacy._PathPrivateDir", 'cls=privacy.PrivateDir')
    if case == 'card_reader_retarget':
        new = new.replace('CardReader,PathCardReader,scan_card_strict', 'CardReader,scan_card_strict')
        new = new.replace("[('dir_fd',CardReader),('path',PathCardReader)]", "[('dir_fd',CardReader)]")
        new = new.replace('            if base_class is PathCardReader:super().__init__()\n', '')
    if case == 'http_boundary_extra':
        new = new.replace("if not swapped and str(path)==str(root) and not kwargs.get('dir_fd'):",
                          "if not swapped and ((str(path)==str(root) and not kwargs.get('dir_fd')) or (str(path)==root.name and kwargs.get('dir_fd') is not None)):")
    prelude = f'import sys\nsys.path.insert(0, {str(SOURCE / "src")!r})\n'
    return old, prelude + new


def check(case, result):
    if case == 'media_root_race':
        assert all(row['swapped'] and not row['outside_bytes_returned'] and row['error'] for row in result)
    elif case == 'path_delete_race':
        assert all(row['swapped'] and row['outside_file_survives'] and not row['own_original_survives'] and row['error'] is None for row in result)
    elif case == 'card_reader_retarget':
        assert all(row['swapped'] and not row['outside_bytes_read'] and row['scan_complete'] for row in result)
        assert all([p['relpath'] for p in row['photos']] == ['DCIM/100RICOH/OWN.JPG'] for row in result)
        assert all(row['production_read_head_calls'] for row in result)
    elif case == 'lut_reimport_probe':
        assert not result['same_key_after_delete_reimport'] and not result['same_table_after_space_change'] and not result['wrong_current_table']
        assert all(row['samples_equal'] for row in result['rows'])
    elif case == 'http_boundary_extra':
        roots = [row for row in result if row['case'].startswith('root_replaced')]
        assert len(roots) == 3 and all(row['swapped'] for row in roots)
        assert all(not row.get('outside_bytes_returned', False) and not row.get('parsed_external_layout', False) for row in roots)
        ranges = [row for row in result if row['case'] == 'range_integer_overflow']
        assert len(ranges) == 1 and ranges[0]['statuses'] == [200] * 12 and ranges[0]['fd_growth'] == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('case', choices=CASES)
    args = parser.parse_args()
    target = OUT / 'r2-replay'
    target.mkdir(exist_ok=True)
    old, new = adapt(args.case)
    script = target / (args.case + '.py')
    script.write_text(new)
    (target / (args.case + '.diff')).write_text(''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile='r2-original/' + script.name, tofile='r3-replay/' + script.name)))
    (target / (args.case + '-input.json')).write_text(json.dumps({'original':str(OLD / script.name),'original_sha256':hashlib.sha256(old.encode()).hexdigest(),'replay_sha256':hashlib.sha256(new.encode()).hexdigest()},indent=2)+'\n')
    exec(compile(new, str(script), 'exec'), {'__file__':str(script),'__name__':'__main__'})
    result = json.loads((target / CASES[args.case]).read_text())
    check(args.case, result)
    print(json.dumps({'case':args.case,'required_trigger_observed':True,'current_result_checks_pass':True}))


if __name__ == '__main__':
    main()
