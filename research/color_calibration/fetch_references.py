#!/usr/bin/env python3
"""Optional network step: fetch only pinned public research inputs, never execute them."""
import hashlib
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
COMMIT = 'd6effd55cf37ce208c24cf8d072ac14028ca289b'
REPO = 'bastibe/Darktable-Film-Simulation-Panel'
FILES = [
    ('README.md', 'author_provenance.txt'),
    ('styles/Ricoh_Positive Film.dtstyle', 'ricoh_positive.dtstyle'),
    ('styles/Ricoh_Negative Film.dtstyle', 'ricoh_negative.dtstyle'),
    ('styles/Ricoh_Ricoh Standard.dtstyle', 'ricoh_standard.dtstyle'),
    ('styles/Fuji_Classic Neg.dtstyle', 'fuji_classic_neg.dtstyle'),
    ('styles/Fuji_Nostalgic Neg.dtstyle', 'fuji_nostalgic_neg.dtstyle'),
    ('styles/Fuji_Classic Chrome.dtstyle', 'fuji_classic_chrome.dtstyle'),
    ('styles_source/Standard.JPG', 'reference_ricoh_standard.JPG'),
    ('styles_source/Positive Film.JPG', 'reference_ricoh_positive.JPG'),
    ('styles_source/Negative Film.JPG', 'reference_ricoh_negative.JPG'),
    ('styles_source/color checker.cht', 'color_checker.cht'),
]
IMPLEMENTATION_SOURCES = [
    ('https://raw.githubusercontent.com/darktable-org/darktable/release-4.8.0/src/iop/colorchecker.c',
     'colorchecker-darktable-4.8.0.c', '332e6438f127c34c0e0236a3f5ffe7a6eb0d858d1c33aeb048d1d483bcf61a73'),
    ('https://raw.githubusercontent.com/darktable-org/darktable/release-4.8.0/src/iop/tonecurve.c',
     'tonecurve-darktable-4.8.0.c', 'b8cf58a3d21672455372310ff95b5a757392f4d61b1445542075846d1d285679'),
]


def main():
    dest = HERE / 'references'
    dest.mkdir(exist_ok=True)
    manifest = []
    previous = HERE / 'reference_manifest.json'
    known = {r['local']: r['sha256'] for r in json.loads(previous.read_text())} if previous.exists() else {}
    for source, name in FILES:
        url = f'https://raw.githubusercontent.com/{REPO}/{COMMIT}/' + quote(source)
        path = dest / name
        if not path.exists():
            with urlopen(url, timeout=45) as response:
                data = response.read(32 * 1024 * 1024 + 1)
            assert len(data) <= 32 * 1024 * 1024
            path.write_bytes(data)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if str(path.relative_to(HERE)) in known:
            assert digest == known[str(path.relative_to(HERE))], f'Cached reference changed: {path}'
        manifest.append({'repository': REPO, 'commit': COMMIT, 'source_path': source,
                         'download_url': url, 'local': str(path.relative_to(HERE)),
                         'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        print(f'{name}: {len(data)} bytes', flush=True)
    (HERE / 'reference_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    implementations = []
    for url, name, expected in IMPLEMENTATION_SOURCES:
        path = dest / name
        if not path.exists():
            with urlopen(url, timeout=30) as response:
                path.write_bytes(response.read())
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, f'Implementation source hash mismatch: {path}'
        implementations.append({'url': url, 'local': str(path.relative_to(HERE)), 'sha256': expected, 'bytes': len(data)})
    (HERE / 'darktable_source_manifest.json').write_text(json.dumps(implementations, indent=2) + '\n')


if __name__ == '__main__':
    main()
