#!/usr/bin/env python3
"""Fetch immutable, hash-recorded data only; never run upstream programs."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import *

COMMIT = 'e51ba9a23458ff5c316f630b860eb0201139d126'
REPO = 'https://github.com/shenmintao/V-Log-Alchemy'


def main():
    import concurrent.futures
    import urllib.request
    import urllib.parse
    preflight(); install_fence()
    subprocess.run(['df', '-h', '/Volumes/Workspace'], check=True)
    if os.statvfs('/Volumes/Workspace').f_bavail / os.statvfs('/Volumes/Workspace').f_blocks < .2:
        raise RuntimeError('Workspace has less than 20% available space')
    manifest = DOWNLOAD/'SOURCES.json'
    if manifest.exists():
        doc = json.loads(manifest.read_text())
        assert doc['commit'] == COMMIT
        for row in doc['files']:
            assert sha(DOWNLOAD/row['path']) == row['sha256']
        print('Existing immutable download verified:', len(doc['files']), 'files')
        return
    # A failed first download is retained. Resume in a new empty source directory manually.
    DOWNLOAD.mkdir(parents=True, exist_ok=False)
    def read(url, limit=16*1024*1024):
        req = urllib.request.Request(url, headers={'User-Agent': 'projectricoh-private-study'})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read(limit+1)
        if len(data) > limit:
            raise ValueError('Download exceeds bounded size')
        return data
    commit_url = f'https://api.github.com/repos/shenmintao/V-Log-Alchemy/commits/{COMMIT}'
    commit_data = read(commit_url)
    assert json.loads(commit_data)['sha'] == COMMIT
    (DOWNLOAD/'commit.json').write_bytes(commit_data)
    tree_url = f'https://api.github.com/repos/shenmintao/V-Log-Alchemy/git/trees/{COMMIT}?recursive=1'
    tree_data = read(tree_url)
    (DOWNLOAD/'tree.json').write_bytes(tree_data)
    tree = json.loads(tree_data)
    assert not tree['truncated']
    selected = [r for r in tree['tree'] if r['type'] == 'blob' and (
        r['path'].startswith('Luts/Panasonic-Standard/') or r['path'] in (
            'LICENSE', 'README.md', 'Samples/Panasonic-Standard/README.md',
            'Samples/Panasonic-Standard/controlled_profile_comparison.json',
            'Samples/Panasonic-Standard/comparison_report.json'))]
    def fetch(row):
        rel = row['path']
        url = f'https://raw.githubusercontent.com/shenmintao/V-Log-Alchemy/{COMMIT}/'+urllib.parse.quote(rel)
        blob = read(url, 4*1024*1024)
        git_blob = hashlib.sha1(f'blob {len(blob)}\0'.encode()+blob).hexdigest()
        assert git_blob == row['sha']
        dest = DOWNLOAD/rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
        return {'path': rel, 'url': url, 'bytes': len(blob), 'sha256': sha(dest), 'git_blob_sha1': git_blob}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(fetch, selected))
    dump(manifest, {'repo_url': REPO, 'commit': COMMIT, 'license': 'Apache-2.0', 'files': rows,
                    'metadata_urls': [commit_url, tree_url]})
    print('Downloaded immutable data:', len(rows), 'files')


if __name__ == '__main__':
    main()
