"""Research-only acquisition. Run with python3 -I; never executes downloaded data."""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
import pathlib
import re
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRATCH = pathlib.Path('/tmp/gxr_gr_firmware')
HEADERS = {'User-Agent': 'GXR-firmware-static-research/1.0'}


def request(url, method='GET'):
    return urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS, method=method), timeout=45)


def acquire(item, kind):
    record = dict(item, checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
    url = item['url']
    parsed = urllib.parse.urlparse(url)
    if kind == 'firmware':
        official = parsed.hostname == 'www.ricoh-imaging.co.jp' or parsed.hostname == 'ricoh-imaging.co.jp'
        archived = parsed.hostname == 'web.archive.org' and re.search(r'https?://(?:www\.)?ricoh-imaging\.co\.jp/', url)
        if not official and not archived:
            raise ValueError('Firmware source is not an official Ricoh URL or its archive: ' + url)
        target = SCRATCH / 'downloads' / (item['model'] + '-' + item['version'])
        target.mkdir(parents=True, exist_ok=False)
        dest = target / pathlib.PurePosixPath(parsed.path).name
    elif kind == 'docs':
        dest = SCRATCH / 'docs' / item['name']
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            record.update(status='cached', size=dest.stat().st_size, sha256=hashlib.sha256(dest.read_bytes()).hexdigest(), path=str(dest))
            return record
    try:
        with request(url, 'HEAD' if kind == 'probe' else 'GET') as response:
            record.update(http_status=response.status, final_url=response.url, content_type=response.headers.get('Content-Type'), content_length=response.headers.get('Content-Length'))
            if kind != 'probe':
                with dest.open('xb') as out:
                    while block := response.read(1024 * 1024):
                        out.write(block)
                record.update(size=dest.stat().st_size, sha256=hashlib.sha256(dest.read_bytes()).hexdigest(), path=str(dest))
        record['status'] = 'ok'
    except Exception as error:
        record.update(status='error', error=str(error))
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=['docs', 'firmware', 'probe'])
    parser.add_argument('input')
    parser.add_argument('output')
    args = parser.parse_args()
    items = json.loads(pathlib.Path(args.input).read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        records = list(executor.map(lambda x: acquire(x, args.kind), items))
    output = pathlib.Path(args.output)
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n')
    for item in records:
        print(json.dumps({k: v for k, v in item.items() if k in ['name', 'model', 'version', 'status', 'size', 'http_status', 'error']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
