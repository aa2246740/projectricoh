#!/usr/bin/env python3
"""Extract only LUT data and PDF explanations. No ZIP paths are trusted."""
from pathlib import Path
import hashlib
import json
import zipfile

HERE = Path(__file__).resolve().parent
SRC = Path('/tmp/gxr_color_refs/downloads/fuji_eterna55_v110/luts.zip')
OUT = Path('/tmp/gxr_color_refs/extracted/fuji')

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    with zipfile.ZipFile(SRC) as z:
        for i in z.infolist():
            p = Path(i.filename)
            if i.is_dir() or p.suffix.lower() not in ('.cube', '.pdf'):
                continue
            if p.is_absolute() or '..' in p.parts or i.file_size > 30_000_000:
                raise ValueError('Unsafe archive member')
            data = z.read(i)
            dest = OUT / p
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and dest.read_bytes() != data:
                raise ValueError('Refuse changed extraction')
            dest.write_bytes(data)
            records.append({'archive': str(SRC), 'member': i.filename,
                            'local_path': str(dest), 'bytes': len(data),
                            'sha256': hashlib.sha256(data).hexdigest()})
    (HERE/'extracted_source_manifest.json').write_text(json.dumps(records,indent=2)+'\n')
    print(f'{len(records)} inert data members extracted')

if __name__ == '__main__':
    main()
