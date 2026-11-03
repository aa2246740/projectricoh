#!/usr/bin/env python3
"""Recheck final artifacts, protected trees, public content, and sealed checksums."""
import sys
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import dense
common = dense.legacy()
import ast
import re
import subprocess


def public_files():
    return sorted(p for p in dense.HERE.rglob('*') if p.is_file() and
                  not p.is_relative_to(dense.LOCAL) and p.name != 'SHA256SUMS')


def code_hashes():
    return {p.name: dense.sha(p) for p in public_files() if p.suffix == '.py'}


def byte_literal(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, bytes):
        return len(node.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = byte_literal(node.left), byte_literal(node.right)
        return a + b if a is not None and b is not None else None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        for value, multiplier in ((node.left, node.right), (node.right, node.left)):
            size = byte_literal(value)
            if size is not None and isinstance(multiplier, ast.Constant) and isinstance(multiplier.value, int):
                return size * max(0, multiplier.value)
    return None


def numeric_count(value):
    if isinstance(value, (list, tuple)):
        return sum(numeric_count(v) for v in value)
    return int(type(value) in (int, float))


def source_check(source):
    tree = ast.parse(source)
    forbidden = {'raw', 'rgb', 'camera_rgb', 'lab_d65', 'xyz_d50', 'pixels', 'pixel_data', 'patches'}
    for node in ast.walk(tree):
        length = byte_literal(node)
        dense.require(length is None or length < 48, 'public raw byte literal >=48 B')
        if isinstance(node, (ast.List, ast.Tuple)):
            try:
                value = ast.literal_eval(node)
            except (ValueError, TypeError):
                continue
            dense.require(numeric_count(value) < 48, 'public embedded numeric array')
        if isinstance(node, ast.keyword) and node.arg in forbidden:
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            dense.require(numeric_count(value) < 3, 'public per-patch designed colour literal')
        values = []
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in forbidden for t in node.targets):
            values.append(node.value)
        if isinstance(node, ast.Dict):
            values.extend(v for k, v in zip(node.keys, node.values)
                          if isinstance(k, ast.Constant) and k.value in forbidden)
        for expression in values:
            try:
                value = ast.literal_eval(expression)
            except (ValueError, TypeError):
                continue
            dense.require(numeric_count(value) < 3, 'public assigned per-patch colour literal')
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            dense.require(not (len(node.value) >= 96 and
                re.fullmatch(r'[A-Za-z0-9+/=]+', node.value)), 'public encoded binary payload')


def public_content():
    allowed = {'.py', '.md', '.txt', '.json'}
    forbidden = {'raw', 'rgb', 'camera_rgb', 'lab_d65', 'xyz_d50', 'pixels', 'pixel_data',
                 'patches_by_id', 'patch_predictions', 'curve', 'coefficients'}
    def aggregate(value):
        if isinstance(value, dict):
            dense.require(not (set(value) & forbidden), 'public JSON contains point/pixel/model data')
            for item in value.values():
                aggregate(item)
        elif isinstance(value, list):
            dense.require(not any(isinstance(v, list) for v in value), 'public JSON contains matrix/array')
            for item in value:
                aggregate(item)
    for p in public_files():
        dense.require(not p.is_symlink(), 'public symlink')
        dense.require(p.suffix in allowed or p.name in ('.gitignore', 'DNG_SHA256SUMS'), 'unexpected public data file')
        text = p.read_text(encoding='utf-8')
        dense.require('\x00' not in text, 'binary data in public file')
        dense.require(not re.search(r'data:image/[^;]+;base64,', text), 'public embedded image')
        if p.suffix == '.py':
            source_check(text)
        if p.suffix == '.json':
            aggregate(dense.read(p))
            dense.require(dense.read(p).get('schema') in
                ('gr-dense-coverage/1', 'gr-dense-offline-validation/1'), 'non-aggregate public JSON')
    # These rejection fixtures never write their contents to disk.
    for source in ("payload = b'x' * 48", 'pixels = [' + ','.join(['1'] * 48) + ']',
                   'dict(raw=[0.1, 0.2, 0.3])', 'raw = [0.1, 0.2, 0.3]',
                   "record = {'camera_rgb': [0.1, 0.2, 0.3]}"):
        try:
            source_check(source)
        except ValueError:
            pass
        else:
            raise ValueError('content guard failed a negative fixture')
    return len(public_files())


def rules():
    dense.require((dense.HERE / '.gitignore').read_text() == 'local/\n', 'ignore rule changed')
    dense.require(dense.ignored(dense.LOCAL / 'probe'), 'local is not ignored')
    original = dense.read(dense.LOCAL / 'protected.json')['artifacts_ignored']
    dense.require(dense.ignored(dense.ARTIFACTS / 'probe.DNG') == original, 'artifact ignore state changed')
    for i in range(1, 6):
        card = dense.read(dense.LOCAL / 'cards' / f'R090000{i}.json')
        p = Path(card['dng_path'])
        dense.require(p.parent == dense.delivery() and dense.ignored(p), 'DNG path is not in ignored delivery')
        dense.require(card['public_container'] and card['template_sha256'] ==
            'd41bf7988052a17ac1722d111525b946d1ffc239052d28fca664b00b6cec63b1', 'wrong public container')
        dense.require(card['original_photo_previews_retained'] is False, 'original preview retained')
    indexed = subprocess.run(['git', 'ls-files', '-z', 'research/gr_dense_reference/local',
        'artifacts/gr-dense-reference'], cwd=dense.ROOT, check=True, capture_output=True).stdout
    dense.require(not indexed, 'private or DNG data present in Git index')
    try:
        (dense.ROOT / 'dense-outside-probe').write_text('must not be written')
    except ValueError:
        pass
    else:
        raise ValueError('write fence did not reject out-of-scope write')


def verify_card(number):
    from validate import decode_check, jpeg_check, manifest
    decode_check(number)
    jpeg_check(number)
    card = dense.read(manifest(number))
    record = dict(passed=True, dng_sha256=card['dng_sha256'], code=code_hashes(),
        decode_sha256=dense.sha(dense.LOCAL / 'validation' / f'R090000{number}-decode.json'),
        jpeg_sha256=dense.sha(dense.LOCAL / 'validation' / f'R090000{number}-jpeg.json'),
        mapped_sha256=dense.sha(dense.LOCAL / 'mapped' / f'R090000{number}.json'),
        model_sha256=dense.sha(common.MODEL),
        prediction_sha256=dense.sha(dense.LOCAL / 'predictions' / f'R090000{number}' / 'prediction.json'),
        patch_prediction_sha256=dense.sha(dense.LOCAL / 'predictions' / f'R090000{number}' / 'patch_predictions.npz'))
    dense.dump(dense.LOCAL / 'verified' / f'R090000{number}.json', record)
    return record


def sums(path, files, seal):
    mapping = {str(p.relative_to(dense.ROOT)): dense.sha(p) for p in sorted(files)}
    if seal:
        dense.allowed(path).write_text(''.join(f'{digest}  {name}\n' for name, digest in mapping.items()))
    actual = {}
    for line in path.read_text().splitlines():
        digest, name = line.split('  ', 1)
        actual[name] = digest
    dense.require(actual == mapping, f'checksum mismatch: {path.name}')
    return len(mapping)


def final(seal=False, strict_workspace=False):
    rules()
    preservation = dense.preservation(strict_workspace)
    public_n = public_content()
    files = []
    for i in range(1, 6):
        card = dense.read(dense.LOCAL / 'cards' / f'R090000{i}.json')
        receipt = dense.read(dense.LOCAL / 'verified' / f'R090000{i}.json')
        dense.require(receipt['passed'] and receipt['code'] == code_hashes(), 'card verification is stale; rerun --card')
        dense.require(receipt['dng_sha256'] == dense.sha(card['dng_path']) == card['dng_sha256'], 'stale DNG verification')
        dense.require(receipt['model_sha256'] == dense.sha(common.MODEL), 'model changed')
        for key, path in (
            ('decode_sha256', dense.LOCAL / 'validation' / f'R090000{i}-decode.json'),
            ('jpeg_sha256', dense.LOCAL / 'validation' / f'R090000{i}-jpeg.json'),
            ('mapped_sha256', dense.LOCAL / 'mapped' / f'R090000{i}.json'),
            ('prediction_sha256', dense.LOCAL / 'predictions' / f'R090000{i}' / 'prediction.json'),
            ('patch_prediction_sha256', dense.LOCAL / 'predictions' / f'R090000{i}' / 'patch_predictions.npz')):
            dense.require(receipt[key] == dense.sha(path), f'verification artifact changed: {path.name}')
        files.append(Path(card['dng_path']))
    from coverage import summarize, validation_summary
    # A normal check compares derived aggregate documents; sealing never accepts changed inputs.
    before = {p: dense.sha(p) for p in (dense.HERE/'coverage.json', dense.HERE/'offline_validation.json') if p.exists()}
    summarize(); validation_summary()
    if not seal:
        dense.require(all(dense.sha(p) == digest for p, digest in before.items()), 'aggregate report changed')
    from instructions import text
    dense.require((dense.HERE/'OWNER_ZH_EN.txt').read_text() == text(), 'owner instructions are stale')
    count_dng = sums(dense.HERE/'DNG_SHA256SUMS', files, seal)
    count_public = sums(dense.HERE/'SHA256SUMS', public_files(), seal)
    count_delivery = sums(dense.delivery()/'SHA256SUMS', files+[dense.delivery()/'OWNER_ZH_EN.txt'], seal)
    local_files = sorted(p for p in dense.LOCAL.rglob('*') if p.is_file()
        and not p.is_relative_to(dense.TMP) and p.name not in ('SHA256SUMS', 'verification.json'))
    count_local = sums(dense.LOCAL/'SHA256SUMS', local_files, seal)
    public_content()
    result = dict(passed=True, protected=preservation, public_content_files=public_n,
        checksum_files=dict(public=count_public, dng=count_dng, delivery=count_delivery, local=count_local),
        final_artifact_checks_rerun=True, all_five_cards_verified=True,
        artifacts_directory_ignored=dense.ignored(dense.ARTIFACTS/'probe.DNG'),
        delivery=str(dense.delivery().relative_to(dense.ROOT)), private_data_in_index=False,
        camera_acceptance=False, firmware_ready=False, deployable=False,
        versions=dict(python=sys.version.split()[0], numpy=__import__('numpy').__version__,
            pillow=__import__('PIL').__version__, imagecodecs=__import__('imagecodecs').__version__))
    dense.dump(dense.LOCAL/'verification.json', result)
    print(__import__('json').dumps(result, ensure_ascii=False))
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--card', type=int, choices=range(1, 6), help='re-run one bounded verification unit')
    parser.add_argument('--final', action='store_true', help='check current receipts, protections, public data and checksums')
    parser.add_argument('--seal', action='store_true', help='seal hashes only after all checks pass')
    parser.add_argument('--strict-workspace', action='store_true',
                        help='also fail on unrelated concurrent changes to tracked files')
    args = parser.parse_args()
    if args.card:
        dense.require(not args.final and not args.seal, 'use --card separately')
        verify_card(args.card)
    else:
        if not args.final:
            for number in range(1, 6):
                verify_card(number)
        final(args.seal, args.strict_workspace)
