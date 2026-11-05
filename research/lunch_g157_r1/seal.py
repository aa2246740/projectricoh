"""Check publication privacy and seal the actual artifacts, without network or device access."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C
import argparse
from html.parser import HTMLParser
import re
import subprocess


class LocalImages(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.ids = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        assert tag != 'script'
        if tag == 'img':
            self.images.append(a['src'])
        if tag == 'section':
            self.ids.append(a['id'])


def private_files():
    return sorted(p for p in C.LOCAL.rglob('*') if p.is_file()
        and p.name not in ('SHA256SUMS', 'seal.json') and p.suffix != '.log'
        and not p.is_relative_to(C.LOCAL / 'queues')
        and not p.is_relative_to(C.LOCAL / 'admissions'))


def verify_sums(root):
    count = 0
    for line in (root / 'SHA256SUMS').read_text().splitlines():
        digest, relative = line.split('  ', 1)
        p = (root / relative).resolve()
        assert p.is_relative_to(root.resolve()) and C.sha(p) == digest, relative
        count += 1
    return count


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--verify-only', action='store_true')
    args = p.parse_args()
    C.admit('seal-verify' if args.verify_only else 'seal')
    if args.verify_only:
        print('HASH CHECK PASS', verify_sums(C.HERE), 'public,', verify_sums(C.LOCAL), 'private files', flush=True)
        return
    verification = C.read(C.LOCAL / 'verification.json')
    assert verification['status'] == 'PASS'
    summary = C.read(C.LOCAL / 'summary.json')
    receipt = C.read(C.LOCAL / 'report-receipt.json')
    report = (C.HERE / 'REPORT.md').read_text()
    assert report.splitlines()[0] == receipt['first_line']
    assert C.sha(C.HERE / 'REPORT.md') == receipt['report_sha256']
    assert report.count('## 配方识别表') == 1 and report.count('## 各配方的预测准确度') == 1
    assert report.count('## 相似度') == 1 and report.count('## 异常') == 1
    assert not any(s in report for s in ('<img', 'data:image', '![', 'GPSLatitude', 'GPSLongitude'))
    public_ids = re.findall(r'^\| \[(R\d+)\]', report, re.M)
    expected = [r['id'] for r in summary['rows']]
    assert len(public_ids) == 55 and sorted(public_ids) == sorted(expected)
    page = LocalImages()
    page.feed((C.LOCAL / 'index.html').read_text())
    assert sorted(page.ids) == sorted(expected)
    for relative in page.images:
        assert not re.match(r'\w+:', relative)
        image = (C.LOCAL / relative).resolve()
        assert image.is_relative_to(C.LOCAL) and image.is_file()
    paths = sorted(p for p in C.LOCAL.rglob('*') if p.is_file())
    relative = [str(p.relative_to(C.ROOT)) for p in paths]
    ignored = subprocess.run(['git', 'check-ignore', '--stdin'], input='\n'.join(relative)+'\n',
                             text=True, cwd=C.ROOT, capture_output=True, check=True)
    assert set(ignored.stdout.splitlines()) == set(relative)
    tracked = subprocess.check_output(['git', 'ls-files', str(C.LOCAL.relative_to(C.ROOT))], cwd=C.ROOT, text=True)
    assert not tracked.strip()
    public = sorted(p for p in C.HERE.iterdir() if p.is_file())
    assert all(p.suffix in ('.py', '.md') or p.name == 'SHA256SUMS' for p in public)
    C.decision('seal', '检查公开报告及本地图片边界，封存实际产物',
               '保证逐张证据可复查，照片派生物不进入公开文件',
               'local/seal.json; SHA256SUMS; local/SHA256SUMS',
               '55 report rows; 114 originals unchanged; all local artifacts ignored')
    files = private_files()
    (C.LOCAL / 'SHA256SUMS').write_text(''.join(C.sha(p) + '  ' + str(p.relative_to(C.LOCAL)) + '\n' for p in files))
    public = sorted(C.HERE.glob('*.py')) + [C.HERE / 'REPORT.md']
    (C.HERE / 'SHA256SUMS').write_text(''.join(C.sha(p) + '  ' + p.name + '\n' for p in public))
    C.dump('seal.json', dict(status='PASS', public_files=len(public), private_files=len(files),
         private_images_ignored=True, private_files_tracked=0, owner_review_images=len(page.images),
         report_rows=55, original_files_unchanged=verification['original_photo_files'],
         public_SHA256SUMS_sha256=C.sha(C.HERE / 'SHA256SUMS'),
         private_SHA256SUMS_sha256=C.sha(C.LOCAL / 'SHA256SUMS'), created_utc=C.utc()))
    print('SEAL PASS', len(public), 'public,', len(files), 'private files,', len(page.images), 'local review images', flush=True)


if __name__ == '__main__':
    main()
