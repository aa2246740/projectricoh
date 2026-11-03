#!/usr/bin/env python3
"""Check actual archives, protected inputs and report outputs; optionally rehash SD."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAPTURE = ROOT / 'captures/a12-50/2026-10-16/S1b-sd-import'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-sd', action='store_true', help='Read and hash the source card as well')
    args = parser.parse_args()
    manifest = json.loads((CAPTURE / 'ingest_manifest.json').read_text())
    analysis = json.loads((HERE / 'new_captures_analysis.json').read_text())
    captures = json.loads((CAPTURE / 'verification.json').read_text())
    protected = json.loads((HERE / 'new_captures_protected_inputs_before.json').read_text())
    errors, results = [], {}

    def require(condition, explanation):
        if not condition:
            errors.append(explanation)

    require(manifest['source_inventory_before'] == manifest['source_inventory_after'], 'SD changed during ingest')
    require(len(manifest['copied_files']) == 16, 'Expected 16 archived capture files')
    for item in manifest['copied_files']:
        path = ROOT / item['destination']
        require(path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], f'Capture bytes changed: {path}')
        require(path.stat().st_mode & 0o777 == 0o444, f'Capture not 0444: {path}')
        source_relative = str(Path(item['source']).relative_to(manifest['source_root']))
        require(item['sha256'] == manifest['source_inventory_before'][source_relative]['sha256'], f'Source/copy hash mismatch: {path}')
    results['archived_files_bytes_and_0444_verified'] = 16
    changed = []
    for name, expected in protected.items():
        path = ROOT / name
        if not path.is_file() or path.stat().st_size != expected['bytes'] or sha(path) != expected['sha256']:
            changed.append(name)
    for directory in ['firmware', 'artifacts/firmware', 'artifacts/stage1b-candidate', 'research/color_targets']:
        actual = {str(p.relative_to(ROOT)) for p in (ROOT / directory).rglob('*') if p.is_file()}
        expected = {p for p in protected if p.startswith(directory + '/')}
        require(actual == expected, f'Protected file set changed: {directory}')
    require(not changed, f'Protected files changed: {changed}')
    results.update(protected_files_checked=len(protected), changed_protected_files=changed,
                   protected_baseline_sha256=sha(HERE / 'new_captures_protected_inputs_before.json'))
    require(len(analysis['captures']) == 8 and len(captures['captures']) == 8, 'Capture pair count mismatch')
    require(analysis['captures'] == captures['captures'], 'Capture verification and analysis disagree')
    for capture in analysis['captures']:
        require(capture['verification']['valid_dng_structure_and_full_raw_decode'], capture['id'] + ': invalid RAW')
        require(capture['verification']['valid_companion_jpeg_full_decode'], capture['id'] + ': invalid JPEG')
        require(all(capture['verification']['paired_fields_equal'].values()), capture['id'] + ': pair mismatch')
        require(capture['raw']['cfa_pattern'] == [0, 1, 1, 2], capture['id'] + ': CFA mismatch')
        require(capture['raw']['raw_pixels_decoded'] == 12318048, capture['id'] + ': incomplete RAW decode')
        previews = capture['verification']['embedded_jpeg_previews']
        require(len(previews) == 1 and previews[0]['dimensions_wh'] == [640, 424]
                and previews[0]['ifd_dimensions_wh'] == [640, 480] and previews[0]['full_decode']
                and previews[0]['ifd_dimensions_match_jpeg'] is False, capture['id'] + ': native preview discrepancy changed')
        require(capture['verification']['strict_dng_conformance_verified'] is False, capture['id'] + ': unsupported strict DNG conformance claim')
    new = [c for c in analysis['captures'] if c['new_capture_date_2026_10_16']]
    require([c['id'] for c in new] == ['R8051136', 'R8051137'], 'New shooting-date membership mismatch')
    require(new[0]['dng']['color_raw_13'] == [3] * 13, '1136 neutral color bytes mismatch')
    require(new[1]['dng']['color_raw_13'] == [3, 3, 3, 8, 3, 3, 3, 3, 3, 3, 3, 3, 3], '1137 Orange Plus bytes mismatch')
    require(new[0]['recipe']['candidate_slots_by_selector_and_13_color_values'] == [1, 13, 14, 15, 16], 'Ambiguous neutral slot was collapsed')
    require(new[1]['recipe']['candidate_slots_by_selector_and_13_color_values'] == [8], 'Orange signature slot mismatch')
    require(all(c['dng']['wb']['offsets_axis0_axis1'] is None for c in new), 'Unverified WB offsets promoted to known')
    require(analysis['calibrated_gxr_recipe_count'] == 0 and analysis['calibrated_gxr_recipes'] == [], 'Unsupported calibrated recipe claim')
    require(len(analysis['targets']) == 16 and all(t['calibrated_gxr_parameters'] is None and not t['deployable'] for t in analysis['targets']), 'Unsupported target deployment claim')
    require(analysis['calibration_identifiability']['color_control_design_rank'] == 1, 'Color control design rank mismatch')
    require(new[0]['color']['patches']['orange_C_ab_above_10_hue_40_to_90_count'] == 0, 'Baseline orange coverage unexpectedly changed')
    require(analysis['new_pair_diagnostics']['positive_jpeg_effect_verified'] is False, 'Unsupported JPEG effect claim')
    require(analysis['embedded_preview_comparison']['all_imported_previews_match_old_control_dimensions'], 'New preview discrepancy relative to old control')
    results['preview_metadata_discrepancy_present_in_old_control_and_all_8'] = True
    require(captures['card_package_identity']['recipe_matches_package'] and captures['card_package_identity']['ilaunch3_matches_candidate'], 'Card/candidate identity mismatch')
    results['valid_pairs_and_evidence_limits_checked'] = 8
    broken_links = []
    for path in [HERE / 'NEW_CAPTURES_REPORT.md', CAPTURE / 'README.md']:
        for link in re.findall(r'\]\(([^)]+)\)', path.read_text()):
            if link.startswith(('https://', 'http://', '#')):
                continue
            target = (path.parent / link.split('#')[0]).resolve()
            if target != HERE / 'new_captures_verification.json' and not target.exists():
                broken_links.append(f'{path.name}: {link}')
    require(not broken_links, f'Broken report links: {broken_links}')
    results['report_local_links_valid'] = not broken_links
    scripts = ['ingest_new_captures.py', 'analyze_new_captures.py', 'write_new_captures_report.py', 'verify_new_captures.py']
    for name in scripts:
        ast.parse((HERE / name).read_text(), filename=name)
    results['scripts_syntax_checked'] = scripts
    if args.verify_sd:
        source = Path(manifest['source_root'])
        require(source.is_dir(), f'Source card unavailable: {source}')
        after = {}
        if source.is_dir():
            for path in sorted(source.rglob('*')):
                require(not path.is_symlink(), f'Unexpected source symlink: {path}')
                if path.is_file():
                    st = path.stat()
                    after[str(path.relative_to(source))] = {'bytes': st.st_size, 'sha256': sha(path), 'mtime_ns': st.st_mtime_ns}
            names = manifest['source_inventory_before'].keys() | after.keys()
            changes = [name for name in sorted(names) if manifest['source_inventory_before'].get(name) != after.get(name)]
            require(not changes, f'SD changed since ingest: {changes}')
            results['sd_final_inventory'] = after
            results['sd_files_checked'] = len(after)
            results['sd_changed_files'] = changes
    results['schema'] = 'gxr-new-captures-output-verification-v1'
    results['pass'] = not errors
    results['errors'] = errors
    (HERE / 'new_captures_verification.json').write_text(json.dumps(results, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({key: value for key, value in results.items() if key != 'sd_final_inventory'}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
