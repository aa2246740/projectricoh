#!/usr/bin/env python3
"""Strict partial MAIN: unchanged factory gates, exactly four Standard/Positive pairs."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import argparse
import copy

OWNER = 'gr4'
STYLES = {'standard', 'positive'}
EXPECTED = {f'dense-band-{i}' for i in range(1, 5)}


def validate_groups(groups):
    assert set(groups) == EXPECTED, 'need all four dense bands'
    for ident, group in groups.items():
        assert set(group) == STYLES, 'need exactly default Standard+Positive: ' + ident


def identities():
    rb, a, common = rt.readback_modules()
    test = rt.read(rt.RETURNS / 'test')
    assert test['passed'] and test['stage'] == 'test' and test['camera_evidence'] and test['owner'] == OWNER
    assert test['identities'][0]['card_id'] == 'acceptance-38'
    candidates = rb.cards(OWNER)
    expected_dngs = {candidates[k][1]['dng_sha256']: k for k in EXPECTED}
    returned, groups, records = {}, {}, []
    for number in range(103, 107):
        folder = rt.INPUT / f'R{number:07d}'
        dng = folder / f'R{number:07d}.DNG'
        value = rt.sha(dng)
        assert value in expected_dngs and expected_dngs[value] not in returned
        returned[expected_dngs[value]] = dict(path=dng, sha256=value)
        for suffix in ('Std', 'Posi'):
            path = folder / f'R{number:07d} {suffix}.JPG'
            assert rb.OFFLINE not in path.read_bytes(), 'offline fixture cannot become camera evidence'
            mode, metadata = rb.camera_record(path, OWNER)
            assert mode in STYLES
            image = a.load_jpeg(path)
            ident, matching, alignment = rb.identify(image, candidates, mode)
            assert ident in EXPECTED
            group = groups.setdefault(ident, {})
            assert mode not in group, 'duplicate card/style'
            if group:
                previous = next(r['metadata'] for r in records if r['card_id'] == ident)
                assert metadata['white_balance'] == previous['white_balance']
                assert metadata['wb_rggb'] == previous['wb_rggb']
            group[mode] = str(path)
            records.append(dict(card_id=ident, style=mode, path=path, sha256=rt.sha(path),
                                content_sha256=candidates[ident][1]['content_sha256'],
                                matching=matching, alignment=alignment, metadata=metadata))
            print(ident, mode, round(matching['rank_correlation'], 4), flush=True)
    assert set(returned) == EXPECTED
    validate_groups(groups)
    result = dict(schema='gr-dense-partial-main/1', partial=True, passed=True, stage='main', owner=OWNER,
                  required_styles=sorted(STYLES), missing_factory_styles=['negative'], groups=groups,
                  identities=records, returned_dngs=returned, source='camera returns', camera_evidence=True,
                  offline_prediction=False, camera_acceptance=False, firmware_ready=False,
                  filename_used_for_matching=False, acceptance_receipt_sha256=rt.sha(rt.RETURNS / 'test'),
                  original_readback_sha256=rt.sha(rt.ROOT / 'research/gr_dense_reference/readback_r3.py'))
    rt.dump(rt.RETURNS / 'partial-main-identities.json', result)
    # Cheap negative cases exercise the narrowed completeness and unchanged default gates.
    tests = {}
    for name, bad in [('missing_band', {k: v for k, v in groups.items() if k != 'dense-band-1'}),
                      ('missing_positive', {**groups, 'dense-band-1': {'standard': 'unused'}}),
                      ('extra_negative', {**groups, 'dense-band-1': {**groups['dense-band-1'], 'negative': 'unused'}})]:
        try:
            validate_groups(bad)
        except AssertionError:
            tests[name] = True
        else:
            raise AssertionError('accepted ' + name)
    for mode in sorted(STYLES):
        original = next(r['metadata'] for r in records if r['style'] == mode)
        for key in ('high_low_key', 'contrast', 'contrast_highlight', 'contrast_shadow',
                    'saturation', 'hue', 'sharpness', 'shading', 'clarity'):
            bad = copy.deepcopy(original)
            bad['control'][key] += 1
            try:
                rb.defaults(bad, mode)
            except ValueError:
                tests[f'{mode}_{key}'] = True
            else:
                raise AssertionError('accepted altered default slider ' + key)
    rt.dump(rt.RETURNS / 'partial-gate-review.json', dict(all_passed=all(tests.values()), cases=tests,
        wrapper_sha256=rt.sha(Path(__file__)),
        review='camera_record, cards, identify, load_jpeg, align, sample and analyze reused unchanged; only required style set differs',
        original_main_gate_unchanged=True, partial=True))


def band(number):
    rb, a, common = rt.readback_modules()
    record = rt.read(rt.RETURNS / 'partial-main-identities.json')
    assert record['passed'] and record['partial'] is True
    validate_groups(record['groups'])
    ident = f'dense-band-{number}'
    manifest, card = rb.cards(OWNER)[ident]
    for r in record['identities']:
        if r['card_id'] == ident:
            assert rt.sha(r['path']) == r['sha256']
    result = a.analyze(manifest, record['groups'][ident], rt.RETURNS / f'{ident}-partial-analysis.json')
    for mode, state in result['modes'].items():
        rb.defaults(state['metadata'], mode)
    result.update(partial=True, required_styles=sorted(STYLES), default_negative_available=False)
    rt.dump(rt.RETURNS / f'{ident}-partial-analysis.json', result)
    print(ident, 'fit-usable', sum(p['usable_for_fit'] for p in result['transforms']['positive']), flush=True)


def diagnostics(number):
    rb, a, common = rt.readback_modules()
    manifest, card = rb.cards(OWNER)[f'dense-band-{number}']
    folder = rt.INPUT / f'R{number+102:07d}'
    standard = rt.read(rt.RETURNS / f'dense-band-{number}-partial-analysis.json')['modes']['standard']
    tm = common.load_module('dense_diag_metadata', rt.ROOT / 'research/contrib_gr_analysis/tiff_makernote.py')
    result = dict(schema='gr-dense-nondefault-diagnostics/1', diagnostic_only=True,
                  target_eligible=False, card_id=card['card_id'], modes={})
    for suffix, expected_tone in (('Nega', 267), ('BB', 263)):
        path = folder / f'R{number+102:07d} {suffix}.JPG'
        assert rb.OFFLINE not in path.read_bytes()
        tiff, _ = tm.jpeg_exif_tiff(path.read_bytes())
        _, at, note, root, _ = tm.maker_note_bytes(tiff)
        assert at is not None and note.startswith(b'RICOH\0')
        entries, decoded = tm.decode_gr3_family(tiff, at)
        tone = decoded['image_tone']['value']
        assert tone == expected_tone
        metadata = dict(image_tone=tone, control=decoded['image_control_0x0247'],
            raw_development_process=decoded['raw_development_process_0x0062'],
            white_balance=decoded['white_balance_0x0019'],
            wb_rggb=next(e['value'] for e in entries if e['tag'] == 0x0201),
            model=next(r['value'] for r in root if r['tag'] == 272))
        assert metadata['white_balance'] == standard['metadata']['white_balance']
        assert metadata['wb_rggb'] == standard['metadata']['wb_rggb']
        assert metadata['model'].strip() == card['geometry']['model'].strip()
        assert metadata['raw_development_process'] not in (None, 0)
        from PIL import Image
        with Image.open(path) as im:
            assert float(im.getexif().get_ifd(34665).get(37380, 999)) == 0.
        if suffix == 'Nega':
            try:
                rb.defaults(metadata, 'negative')
            except ValueError as error:
                default_failure = str(error)
            else:
                raise AssertionError('the diagnostic Negative unexpectedly passed the factory gate')
        else:
            default_failure = 'unrequested Bleach Bypass 2; no factory-preset target is declared'
        image = a.load_jpeg(path)
        # Rank matching establishes only the card identity; it never names this style.
        try:
            ident, matching, alignment = rb.identify(image, rb.cards(OWNER), 'negative' if suffix == 'Nega' else 'standard')
            matching['method'] = 'original frozen-model rank matcher'
        except ValueError as error:
            # Keep the same numerical gates but compare against the newly measured
            # Standard card. Nondefault styles need not track a factory predictor.
            ident, matching, alignment = measured_standard_identity(image, rb, a)
            matching['original_matcher_rejection'] = str(error)
        assert ident == card['card_id']
        h, alignment = a.align(image, card)
        samples = a.sample(image, card, h)
        correction = a.correct(card, samples)
        result['modes'][suffix] = dict(path=path, sha256=rt.sha(path), metadata=metadata,
            default_preset=False, exclusion_reason=default_failure, target_eligible=False,
            matching=matching, alignment=alignment, radial=correction, patches=samples)
    rt.dump(rt.RETURNS / f'dense-band-{number}-diagnostics.json', result)
    print(card['card_id'], 'Nega/BB measured as diagnostics only', flush=True)


def measured_standard_identity(image, rb, a):
    from scipy.ndimage import map_coordinates
    from scipy.stats import rankdata
    cards = {k: v for k, v in rb.cards(OWNER).items() if k in EXPECTED}
    h, alignment = a.align(image, next(iter(cards.values()))[1])
    pixels = np.asarray(image)
    scores = {}
    for ident, (_, card) in cards.items():
        std = rt.read(rt.RETURNS / f'{ident}-partial-analysis.json')['modes']['standard']
        lookup = {p['id']: p for p in std['patches']}
        patches = sorted((p for p in card['patches'] if p['role'] == 'colour'),
                         key=lambda p: rb.n.digest(p['id'].encode()))[:96]
        xy = a.project(h, [p['center'] for p in patches])
        actual = np.stack([map_coordinates(pixels[..., k], [xy[:, 1], xy[:, 0]],
                          order=1, output=np.float64) for k in range(3)], axis=-1)
        expected = np.array([lookup[p['id']]['rgb_observed'] for p in patches])
        scores[ident] = float(np.mean([np.corrcoef(rankdata(expected[:, k]), rankdata(actual[:, k]))[0, 1]
                                      for k in range(3)]))
    best, runner = sorted(scores, key=scores.get, reverse=True)[:2]
    rb.n.require(scores[best] >= .65 and scores[best] - scores[runner] >= .20,
                 'diagnostic measured-Standard identity failed: ' + str(scores))
    return best, dict(method='rank versus measured default Standard, diagnostics only', scores=scores,
        rank_correlation=scores[best], margin=scores[best]-scores[runner], threshold=.65,
        minimum_margin=.20, filename_used=False), alignment


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--identify', action='store_true')
    parser.add_argument('--band', type=int, choices=range(1, 5))
    parser.add_argument('--diagnostics', type=int, choices=range(1, 5))
    args = parser.parse_args()
    if args.identify:
        identities()
    if args.band:
        band(args.band)
    if args.diagnostics:
        diagnostics(args.diagnostics)
    assert args.identify or args.band or args.diagnostics
