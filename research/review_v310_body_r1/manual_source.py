#!/usr/bin/python3
"""Retain the public official update manual and its relevant text passages."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request

HERE = Path(__file__).resolve().parent
URL = 'https://www.ricoh-imaging.co.jp/english/r_dc/download/firmware/docs/gxr_fwup_cs.pdf'


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) >= 10
    target = HERE / 'evidence/official-manual.json'
    assert not target.exists()
    raw = urllib.request.urlopen(URL, timeout=45).read()
    assert raw.startswith(b'%PDF-')
    pdf = HERE / 'local/official-gxr-update-manual-cs.pdf'
    assert not pdf.exists()
    pdf.write_bytes(raw)
    converter = shutil.which('pdftotext')
    assert converter, 'pdftotext unavailable; retained PDF remains the primary source'
    text = subprocess.check_output([converter, '-layout', str(pdf), '-'], text=True)
    text_path = HERE / 'local/official-gxr-update-manual-cs.txt'
    text_path.write_text(text)
    lines = text.splitlines()
    selected = []
    for i, line in enumerate(lines):
        if re.search(r'Fn2|MENU|2\s*[~～−—–-]\s*3|自动|自動|重新|播放', line):
            selected.append(dict(line=i + 1, text='\n'.join(lines[max(0, i - 1):i + 2])))
    target.write_text(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        URL=URL, PDF_sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
        PDF=str(pdf.relative_to(HERE)), text=str(text_path.relative_to(HERE)),
        passages=selected), ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status='SOURCE_RETAINED', bytes=len(raw), passages=len(selected))))


if __name__ == '__main__':
    main()
