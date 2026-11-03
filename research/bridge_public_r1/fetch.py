"""Only read-only public HTTP GET; never import or execute downloaded files."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c
import argparse
import datetime
import json
import re
import urllib.request
import urllib.error
import urllib.parse
import fcntl


def fetch(label, url, filename=None):
    assert re.fullmatch(r'[a-zA-Z0-9_-]+', label)
    assert urllib.parse.urlsplit(url).scheme in ('http', 'https')
    sources = c.LOCAL / 'sources.json'
    records = json.loads(sources.read_text()) if sources.exists() else []
    existing = [r for r in records if r['label'] == label and r['url'] == url]
    if existing:
        r = existing[-1]
        if r.get('file'): assert c.sha(c.ROOT / r['file']) == r['sha256']
        print(label, r['status'], '(cached)'); return r
    folder = c.DOWNLOADS / label
    folder.mkdir(exist_ok=False)
    filename = filename or Path(urllib.parse.urlsplit(url).path).name or 'index.html'
    assert Path(filename).name == filename
    path = folder / filename
    r = dict(label=label, url=url, date_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
             method='GET', untrusted=True)
    c.NETWORK = True
    try:
        req = urllib.request.Request(url, method='GET', headers={'User-Agent': 'PublicColourResearch/1.0'})
        with urllib.request.urlopen(req, timeout=35) as response:
            data = response.read(70 * 1024 * 1024 + 1)
            assert len(data) <= 70 * 1024 * 1024, 'download exceeds 70 MiB limit'
            path.write_bytes(data)
            r.update(status=response.status, final_url=response.url,
                     content_type=response.headers.get('Content-Type'), bytes=len(data),
                     file=str(path.relative_to(c.ROOT)), sha256=c.sha(path))
    except urllib.error.HTTPError as error:
        path = folder / 'http-error.txt'
        path.write_bytes(error.read(256000))
        r.update(status=error.code, error=str(error), file=str(path.relative_to(c.ROOT)), sha256=c.sha(path))
    except Exception as error:
        r.update(status='unavailable', error=str(error), sha256=None)
    finally: c.NETWORK = False
    c.dump(folder / 'receipt.json', r)
    with (c.LOCAL / '.sources.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        records = json.loads(sources.read_text()) if sources.exists() else []
        records.append(r); c.dump(sources, records)
    print(label, r['status'], r.get('bytes', ''))
    return r


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('label'); ap.add_argument('url'); ap.add_argument('--name')
    a = ap.parse_args(); fetch(a.label, a.url, a.name)
