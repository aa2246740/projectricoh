"""Verify protected inputs, observed pairs, scores and the public hash manifest."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import ROOT, HERE, LOCAL, guard, read, dump, sha, protected_tree, pair_modules, modules
import argparse
import ast
import hashlib
import json
import re
import numpy as np

TREES = ('captures', 'artifacts', 'firmware', 'research')
PARTS = dict(captures=1, artifacts=1, firmware=1, research=6)


def baseline_index():
    out = {}
    for tree in TREES:
        p = LOCAL / ('protected_before_' + tree + '.json')
        out[tree] = dict(files=len(read(p)), manifest_sha256=sha(p), parts=PARTS[tree])
    p = HERE / 'protected_baselines.json'
    if p.exists():
        assert read(p) == out, 'Baseline manifests changed'
    else:
        dump(p, out)
    return out


def tree_check(tree, part):
    assert 0 <= part < PARTS[tree]
    expected = read(LOCAL / ('protected_before_' + tree + '.json'))
    keys = sorted(expected)
    # Partition by fixed, contiguous positions; hashing remains in the foreground.
    subset = keys[len(keys) * part // PARTS[tree]:len(keys) * (part + 1) // PARTS[tree]]
    changed = [rel for rel in subset if not (ROOT / rel).is_file() or sha(ROOT / rel) != expected[rel]]
    added, removed = [], []
    if part == 0:
        current = {str(p.relative_to(ROOT)) for p in (ROOT / tree).rglob('*')
                   if p.is_file() and not p.is_relative_to(HERE)}
        added, removed = sorted(current - set(keys)), sorted(set(keys) - current)
    assert not changed and not added and not removed, dict(changed=changed, added=added, removed=removed)
    result = dict(tree=tree, part=part, checked=len(subset), changed=0, added=0, removed=0,
                  manifest_sha256=sha(LOCAL / ('protected_before_' + tree + '.json')))
    dump(LOCAL / 'verification' / (tree + '_' + str(part) + '.json'), result)
    return result


def sources(data_root):
    data_root = Path(data_root).resolve()
    expected = read(LOCAL / 'protected_before_captures.json')
    count = 0
    for line in (data_root / 'SHA256SUMS').read_text().splitlines():
        digest, relative = line.split('  ', 1)
        path = (data_root / relative).resolve()
        assert path.is_relative_to(data_root)
        assert expected[str(path.relative_to(ROOT))] == digest
        count += 1
    result = dict(provider_manifest_entries=count, matches_initial_input_hashes=True)
    dump(LOCAL / 'verification/sources.json', result)
    return result


def pair(frame_id):
    common, extractor = pair_modules()
    f = next(f for f in read(LOCAL / 'inventory.json') if f['id'] == frame_id)
    if not f['standalone_jpeg']:
        f['jpg'] = None
    raw, md = extractor.raw_frame(f)
    jpg, _, _ = extractor.camera_jpeg(f)
    p = LOCAL / 'samples' / (frame_id + '.npz')
    with np.load(p, allow_pickle=False) as z:
        d = dict(z)
    take = np.linspace(0, len(d['uc']) - 1, min(64, len(d['uc'])), dtype=int)
    xx, yy = d['xy'][take].T
    n = np.asarray(md['tags']['50728'])
    be = md['tags'].get('50730', [0])[0]
    h, w = raw['rgb'].shape[:2]
    radial = read(ROOT / 'research/gr4_modes/local/tone_curves.json')['radial']
    coef = radial['gr4_coef_natural_log' if f['family'] == 'gr4' else 'gr3_coef_natural_log']
    meanraw, meanjpeg = [], []
    for x, y in zip(xx, yy):
        ay, ax = np.mgrid[int(y) - 2:int(y) + 3, int(x) - 2:int(x) + 3]
        r2 = ((ay - (h - 1) / 2) ** 2 + (ax - (w - 1) / 2) ** 2) / ((h / 2) ** 2 + (w / 2) ** 2)
        gain = np.exp(-sum(c * r2 ** (i + 1) for i, c in enumerate(coef)))
        meanraw.append((raw['rgb'][ay, ax] / n * 2 ** be * gain[..., None]).mean((0, 1)))
        meanjpeg.append(jpg[ay, ax].mean((0, 1)))
    raw_error = float(abs(np.asarray(meanraw) - d['uc'][take]).max())
    jpeg_error = float(abs(np.asarray(meanjpeg) - d['jpeg'][take]).max())
    assert raw_error < 2e-6 and jpeg_error < 5e-5
    assert sha(ROOT / f['dng']) == md['source_sha256']
    with np.load(LOCAL / ('scores_' + frame_id + '.npz'), allow_pickle=False) as z:
        scoredata = dict(z)
    q = read(HERE / ('scores_' + frame_id + '.json'))
    cm = modules()[1]
    from score import selected
    selected_indices = selected(d)
    assert np.array_equal(scoredata['xy'], d['xy'][selected_indices])
    assert np.max(abs(scoredata['style_observed'] - cm.rgb_lab(d['jpeg'][selected_indices] / 255))) < 1e-10
    for iso in (200, 1600):
        use = scoredata['valid']
        error = cm.delta_e00(scoredata['target'][use], scoredata['pred' + str(iso)][use])
        base = cm.delta_e00(scoredata['target'][use], scoredata['base'][use])
        sc = q['models'][str(iso)]['score']
        assert len(error) == sc['n']
        assert abs(np.median(error) - sc['median']) < 1e-10
        assert abs(np.percentile(error, 90) - sc['p90']) < 1e-10
        assert abs((error < 2).mean() - sc['fractions']['lt2']) < 1e-12
        assert abs(1 - np.median(error) / np.median(base) - sc['similarity']) < 1e-10
    result = dict(frame=frame_id, checked_positions=len(take), raw_mean_max_abs_error=raw_error,
                  JPEG_mean_max_code_error=jpeg_error, scores_independently_recomputed=True,
                  source_hash_matches=True)
    dump(LOCAL / 'verification' / ('pair_' + frame_id + '.json'), result)
    return result


def public_files():
    files = sorted(p for p in HERE.rglob('*') if p.is_file() and not p.is_relative_to(LOCAL)
                   and p.name != 'SHA256SUMS')
    for p in files:
        assert p.name in ('.gitignore', 'REPORT.md') or p.suffix in ('.py', '.json', '.csv'), p
        s = p.read_text()
        assert not re.search(r'(?<![0-9a-fA-F])[0-9a-fA-F]{96,}(?![0-9a-fA-F])', s), p
        if p.suffix == '.py':
            assert not any(isinstance(n, ast.Constant) and isinstance(n.value, bytes) and len(n.value) >= 48
                           for n in ast.walk(ast.parse(s))), p
        if p.suffix == '.json':
            def scan(v):
                if isinstance(v, list):
                    assert not (len(v) >= 48 and all(isinstance(x, int) and 0 <= x <= 255 for x in v)), p
                    for x in v:
                        scan(x)
                elif isinstance(v, dict):
                    for x in v.values():
                        scan(x)
            scan(read(p))
    return files


def seal():
    files = public_files()
    (HERE / 'SHA256SUMS').write_text(''.join(sha(p) + '  ' + str(p.relative_to(HERE)) + '\n' for p in files))
    return dict(sealed_public_files=len(files))


def final():
    index = baseline_index()
    n = 0
    for tree in TREES:
        subtotal = 0
        for part in range(PARTS[tree]):
            q = read(LOCAL / 'verification' / (tree + '_' + str(part) + '.json'))
            assert q['manifest_sha256'] == index[tree]['manifest_sha256']
            assert q['changed'] == q['added'] == q['removed'] == 0
            subtotal += q['checked']
        assert subtotal == index[tree]['files']
        n += subtotal
    count = 0
    known = set()
    for line in (HERE / 'SHA256SUMS').read_text().splitlines():
        digest, rel = line.split('  ', 1)
        p = (HERE / rel).resolve()
        assert p.is_relative_to(HERE) and not p.is_relative_to(LOCAL)
        assert sha(p) == digest, rel
        known.add(p)
        count += 1
    assert known == set(public_files())
    pairs = read(LOCAL / 'inventory.json')
    for f in pairs:
        assert read(LOCAL / 'verification' / ('pair_' + f['id'] + '.json'))['scores_independently_recomputed']
    assert read(LOCAL / 'verification/sources.json')['matches_initial_input_hashes']
    identity = read(HERE / 'round5_identity.json')
    assert all(all(e.values()) for e in identity['entries'].values())
    old = read(ROOT / 'research/color_fit_v2/gr_dense_t1/baseline_metrics.json')
    for group, record in read(HERE / 'baseline_recomputed.json').items():
        for iso, sc in record.items():
            expected = old[group]['models'][iso]['observed_dense']
            for key in ('n', 'median', 'p90', 'similarity'):
                assert abs(sc[key] - expected[key]) < 1e-10
    pooled = []
    for f in pairs:
        if f['group'] == 'A':
            with np.load(LOCAL / ('scores_' + f['id'] + '.npz'), allow_pickle=False) as z:
                pooled.append({k: z[k][z['valid']] for k in ('target', 'base', 'pred200', 'pred1600')})
    pooled = {k: np.concatenate([d[k] for d in pooled]) for k in pooled[0]}
    cm = modules()[1]
    q = read(HERE / 'scores_A_pooled.json')
    for iso in (200, 1600):
        e = cm.delta_e00(pooled['target'], pooled['pred' + str(iso)])
        b = cm.delta_e00(pooled['target'], pooled['base'])
        sc = q['models'][str(iso)]['score']
        assert len(e) == sc['n'] and abs(np.median(e) - sc['median']) < 1e-10
        assert abs(np.percentile(e, 90) - sc['p90']) < 1e-10
        assert abs((e < 2).mean() - sc['fractions']['lt2']) < 1e-12
        assert abs(1 - np.median(e) / np.median(b) - sc['similarity']) < 1e-10
    result = dict(result='PASS', protected_files=n, changed_inputs=0, added_inputs=0, removed_inputs=0,
                  public_files=count, public_hashes='PASS', public_raw_byte_scan='PASS',
                  pair_frames=len(pairs), paired_positions=sum(read(LOCAL / 'verification' / ('pair_' + f['id'] + '.json'))['checked_positions'] for f in pairs),
                  score_recomputations=2 * (len(pairs) + 1), baseline_score_parity=True, round5_entries_match=True,
                  refit_performed=False, generated_tables=0, firmware_ready=False, deployable=False)
    dump(LOCAL / 'verification/final.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--baseline-index', action='store_true')
    p.add_argument('--tree', choices=TREES)
    p.add_argument('--part', type=int, default=0)
    p.add_argument('--sources', type=Path)
    p.add_argument('--pair')
    p.add_argument('--seal', action='store_true')
    p.add_argument('--final', action='store_true')
    a = p.parse_args()
    guard()
    assert sum(bool(x) for x in (a.baseline_index, a.tree, a.sources, a.pair, a.seal, a.final)) == 1
    result = baseline_index() if a.baseline_index else tree_check(a.tree, a.part) if a.tree else sources(a.sources) if a.sources else pair(a.pair) if a.pair else seal() if a.seal else final()
    print(json.dumps(result, ensure_ascii=False))
