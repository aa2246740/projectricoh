#!/usr/bin/env python3
"""Fetch inert research data into one fresh, isolated folder; never execute it."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.request

HERE = Path(__file__).resolve().parent
SCRATCH = Path('/tmp/gxr_color_refs')

def fetch(name, url, filename, terms, byte_range=None, quiet=False):
    if not re.fullmatch(r'[a-z0-9_-]+', name):
        raise ValueError('Use a simple unique download name')
    if Path(filename).name != filename:
        raise ValueError('Filename must be a basename')
    folder = SCRATCH / 'downloads' / name
    folder.mkdir(parents=True, exist_ok=False)
    path = folder / filename
    record = {'id': name, 'url': url, 'local_path': str(path), 'terms': terms,
              'status': 'started', 'downloaded_code_executed': False}
    if byte_range is not None:
        if not re.fullmatch(r'\d+:\d+',byte_range):raise ValueError('Range must be START:END')
        start,end=map(int,byte_range.split(':'))
        if start>end:raise ValueError('Invalid byte range')
        record['requested_byte_range']=[start,end]
    h = hashlib.sha256()
    count = 0
    try:
        headers={'User-Agent':'GXR-colour-reference-research/1.0'}
        if byte_range is not None:headers['Range']=f'bytes={start}-{end}'
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as r, path.open('xb') as out:
            record['resolved_url'] = r.url
            record['http_status'] = r.status
            record['content_type'] = r.headers.get('Content-Type')
            record['advertised_bytes'] = r.headers.get('Content-Length')
            if byte_range is not None:
                record['content_range']=r.headers.get('Content-Range')
                if r.status!=206 or not record['content_range'].startswith(f'bytes {start}-{end}/'):
                    raise ValueError('Server did not return the exact requested range')
            while chunk := r.read(1024 * 1024):
                out.write(chunk)
                h.update(chunk)
                count += len(chunk)
        if record.get('advertised_bytes') and count!=int(record['advertised_bytes']):raise ValueError('Incomplete advertised response length')
        if byte_range is not None and count!=end-start+1:raise ValueError('Incomplete byte range')
        record.update(status='downloaded', bytes=count, sha256=h.hexdigest())
    except (Exception,KeyboardInterrupt) as e:
        record.update(status='failed', bytes=count, partial_sha256=h.hexdigest(), error=str(e))
        raise
    finally:
        (folder / 'receipt.json').write_text(json.dumps(record, indent=2, ensure_ascii=False)+'\n')
    if not quiet:print(json.dumps(record, ensure_ascii=False))
    return path

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('name'); p.add_argument('url'); p.add_argument('filename')
    p.add_argument('--terms', default='Copyright retained by publisher; no redistribution assumed')
    p.add_argument('--byte-range',default=None,help='Optional exact HTTP byte interval START:END')
    a = p.parse_args()
    fetch(a.name, a.url, a.filename, a.terms,a.byte_range)
