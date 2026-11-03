#!/usr/bin/env python3
"""Download official data to a new quarantine directory; extract data files only."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import argparse
import json
import re
import subprocess
import urllib.request
from urllib.parse import urljoin
import zipfile
from guard import HERE, LOCAL, DOWNLOADS, mount_guard, install_write_fence, sha, dump

PAGE = 'https://leica-camera.com/en-US/photography/cameras/sl/sl3-black/downloads'
LICENSE = '官方公开下载；未发现开放许可证或跨品牌配方再分发授权。仅保留本地研究，发布前须向 Leica 核实。'
SPECS = {
    'leica-llog-v1.6.pdf': 'https://leica-camera.com/sites/default/files/pm-118912-L-Log_Reference_Manual_V1.6.pdf',
    'fuji-flog.pdf': 'https://dl.fujifilm-x.com/support/lut/F-Log_DataSheet_E_Ver.1.0.pdf',
    'fuji-flog2.pdf': 'https://dl.fujifilm-x.com/support/lut/F-Log2_DataSheet_E_Ver.1.0.pdf',
    'panasonic-vlog.pdf': 'https://pro-av.panasonic.net/en/cinema_camera_varicam_eva/support/pdf/VARICAM_V-Log_V-Gamut.pdf',
    'sony-slog3.pdf': 'https://pro.sony/s3/cms-static-content/uploadfile/06/1237494271406.pdf',
    'apple-log.pdf': 'https://download.developer.apple.com/Developer_Tools/Apple_Log_profile/Apple_Log_Profile_White_Paper.pdf',
}


def get(url, limit=32 << 20):
    request = urllib.request.Request(url, headers={'User-Agent': 'GXR-local-LUT-research/1.0'})
    with urllib.request.urlopen(request, timeout=30) as f:
        data = f.read(limit + 1)
        if len(data) > limit:
            raise ValueError('download exceeds limit')
        return data, f.geturl(), dict(f.headers)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--name', default='20261023-official')
    args = p.parse_args()
    if not re.fullmatch('[a-zA-Z0-9_-]+', args.name):
        p.error('name must be a simple directory name')
    mount_guard()
    subprocess.run(['df', '-h', '/Volumes/Workspace'], check=True)
    install_write_fence(download=True)
    dest = DOWNLOADS / args.name
    dest.mkdir(parents=True, exist_ok=False)
    listing, final, _ = get(PAGE, 4 << 20)
    (dest / 'official-download-page.html').write_bytes(listing)
    urls = sorted(set(urljoin(PAGE, x) for x in re.findall(r'href="([^"]+\.zip)"', listing.decode())
                      if any(k in x.lower() for k in ('leica-pure', 'leica-cine', 'look-up-tables'))))
    manifest = {'source_page': PAGE, 'source_page_final': final, 'license': LICENSE, 'archives': [], 'specs': []}
    for url in urls:
        data, final, headers = get(url)
        archive = dest / Path(url).name
        archive.write_bytes(data)
        members = []
        with zipfile.ZipFile(archive) as z:
            if sum(i.file_size for i in z.infolist()) > 128 << 20:
                raise ValueError('uncompressed archive too large')
            for i in z.infolist():
                rel = Path(i.filename)
                if i.is_dir() or '__MACOSX' in rel.parts or rel.name.startswith('.'):
                    continue
                if rel.is_absolute() or '..' in rel.parts or i.flag_bits & 1:
                    raise ValueError('unsafe ZIP member')
                if rel.suffix.lower() not in ('.cube', '.pdf', '.txt', '.rtf'):
                    continue
                target = dest / archive.stem / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(i))
                members.append({'path': str(target.relative_to(DOWNLOADS)), 'bytes': target.stat().st_size,
                                'sha256': sha(target)})
        manifest['archives'].append({'url': url, 'final_url': final, 'path': str(archive.relative_to(DOWNLOADS)),
                                     'sha256': sha(archive), 'bytes': len(data), 'license': LICENSE,
                                     'members': members, 'last_modified': headers.get('Last-Modified')})
        print(archive.name, len(data), 'bytes;', len(members), 'data files')
    specs = dest / 'specs'
    specs.mkdir(exist_ok=True)
    for name, url in SPECS.items():
        try:
            data, final, _ = get(url, 12 << 20)
            if not data.startswith(b'%PDF'):
                raise ValueError('not a PDF (login or error page)')
            f = specs / name
            f.write_bytes(data)
            manifest['specs'].append({'url': url, 'final_url': final, 'path': str(f.relative_to(DOWNLOADS)), 'sha256': sha(f)})
            print(name, len(data), 'bytes')
        except Exception as exc:
            manifest['specs'].append({'url': url, 'error': str(exc)})
            print(name, type(exc).__name__, str(exc)[:90])
    (dest / 'SOURCES.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    dump(LOCAL / 'official_sources.json', manifest)


if __name__ == '__main__':
    main()
