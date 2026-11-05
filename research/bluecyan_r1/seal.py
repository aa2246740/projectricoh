#!/usr/bin/env python3
"""Seal the report, code and ignored evidence without changing original inputs."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze as a
from analyze import ROOT, LOCAL, read, dump, sha
import subprocess
import re
from datetime import datetime, timezone


def main():
    verification = read(LOCAL/'verification.json')
    assert verification['status'] == 'PASS'
    for path, digest in verification['source_sha256'].items():
        assert sha(ROOT/path) == digest, path
    report = a.HERE/'REPORT.md'
    text = report.read_text()
    assert text.startswith('部分找到：')
    assert not re.search(r'!\[|data:image|/Users/wu/Pictures|\bR\d{7}\b', text)
    assert not re.search(r'\b(?:GPSLatitude|GPSLongitude)\b', text)
    assert not re.search(r'(?i)[0-9a-f]{128,}', text)
    rows = read(LOCAL/'history/identities.json')
    for row in rows:
        for key in ('path', 'jpeg'):
            assert Path(row[key]).name.casefold() not in text.casefold()
    assert '待下述' not in text and 'TODO' not in text
    # Assert the key published comparisons directly against the saved evidence.
    comparisons = []
    noon = read(LOCAL/'physical/noon-scores.json')
    for recipe in ('05 F-CC', '06 F-CN'):
        for split in ('V', 'card'):
            item = noon[recipe+' '+split]
            for model in ('old', 'physical'):
                pair = f"{item[model]['median']:.3f} / {item[model]['p95']:.3f}"
                assert pair in text, (recipe, split, model, pair)
                comparisons.append(dict(recipe=recipe, split=split, model=model, printed=pair))
    history = read(LOCAL/'physical/history-scores.json')
    for recipe in ('04', '05', '06'):
        item = history['2026-10-31 allISO '+recipe]['all']
        for model in ('old', 'corrected'):
            pair = f"{item[model]['median']:.3f}/{item[model]['p95']:.3f}"
            assert pair in text, (recipe, model, pair)
            comparisons.append(dict(recipe=recipe, split='Saturday allISO', model=model, printed=pair))
    sources = sorted(p for p in a.HERE.iterdir() if p.is_file())
    assert all(p.suffix in ('.md', '.py', '.swift') for p in sources)
    files = sorted(p for p in LOCAL.rglob('*') if p.is_file() and p.name != 'final-seal.json')
    relative = [str(p.relative_to(ROOT)) for p in files]+[str((LOCAL/'final-seal.json').relative_to(ROOT))]
    result = subprocess.run(['git', 'check-ignore', '--stdin'], input='\n'.join(relative)+'\n',
                            text=True, capture_output=True, cwd=ROOT, check=True)
    assert set(result.stdout.splitlines()) == set(relative)
    tracked = subprocess.check_output(['git', 'ls-files', 'research/bluecyan_r1/local'], cwd=ROOT, text=True)
    assert not tracked.strip()
    manifest = {str(p.relative_to(LOCAL)): sha(p) for p in files}
    dump('final-seal.json', dict(status='PASS', sealed_utc=datetime.now(timezone.utc).isoformat(),
        git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        public_sha256={str(p.relative_to(ROOT)): sha(p) for p in sources},
        local_sha256=manifest, local_files_ignored=len(relative), local_tracked_files=0,
        report_checks=dict(private_original_names_absent=True, private_pixels_absent=True,
                           GPS_coordinates_absent=True, byte_dumps_absent=True,
                           comparisons_from_saved_evidence=comparisons),
        original_photo_hash_check=verification['private_original_files_verified']+verification['noon_original_files_verified'],
        live_device_access=False, DAT_built=False, candidate_camera_exposures=0))
    print('SEAL PASS', len(sources), 'public text/source files;', len(relative), 'ignored evidence files;',
          'report SHA256', sha(report), flush=True)


if __name__ == '__main__':
    main()
