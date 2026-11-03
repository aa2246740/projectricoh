"""Freeze the existing evidence consumed by this study, excluding append-only decisions.tsv."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c
import datetime
import json


def main():
    folders = ('research/gr4_lut_ceiling', 'research/gr4_dense_returns_r1',
               'research/gr4_nega_returns_r1', 'research/color_references')
    for folder in folders:
        for p in sorted((c.ROOT / folder).rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.name != 'decisions.tsv': c.inp(p)
    raw = c.inp('artifacts/downloads/dpreview-gxr-a12-studio/studio_iso200.DNG')
    assert c.sha(raw) == 'f6d19a3219a674a5a7f9b30284285eb6e6d7dd8252309e9d481419e0468fe5c5'
    c.inp('artifacts/downloads/dpreview-gxr-a12-studio-preview/studio_iso200_preview.jpg')
    for name in ('R8051477.DNG', 'R8051477.JPG'):
        c.inp('artifacts/card-b-mount/card-b-after-v34c-first-run-20261026T032356Z/root/DCIM/100RICOH/' + name)
    # Repair the initial simultaneous acquisition records from local file timestamps.
    sourcefile = c.LOCAL / 'sources.json'
    sources = json.loads(sourcefile.read_text()) if sourcefile.exists() else []
    for label, url in [('babelcolor-page', 'https://babelcolor.com/colorchecker-2.htm'),
                       ('camspec-page', 'https://www.gujinwei.org/research/camspec/db.html'),
                       ('munsell-page', 'https://sites.uef.fi/spectral/databases-software/')]:
        if not any(r['label'] == label for r in sources):
            p = c.DOWNLOADS / label / 'index.html'
            sources.append(dict(label=label,url=url,status=200,method='GET',untrusted=True,
                date_utc=datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat(),
                file=str(p.relative_to(c.ROOT)),sha256=c.sha(p),bytes=p.stat().st_size,
                receipt_reconstructed_from_download_mtime=True))
    c.dump(sourcefile, sources)
    print('frozen evidence files', c.verify())


if __name__ == '__main__': main()
