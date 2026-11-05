"""Seal R2 artifacts and prove R1's original sealed files were left untouched."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from r2_common import C,R1,decision
import argparse
from html.parser import HTMLParser
import subprocess


def hashes(root,filename):
    count=0
    for line in (root/filename).read_text().splitlines():
        expected,relative=line.split('  ',1)
        p=(root/relative).resolve();assert p.is_relative_to(root.resolve())
        assert C.sha(p)==expected,str(p)
        count+=1
    return count


class Page(HTMLParser):
    def __init__(self):super().__init__();self.images=[]
    def handle_starttag(self,tag,attrs):
        assert tag!='script'
        if tag=='img':self.images.append(dict(attrs)['src'])


def main():
    p=argparse.ArgumentParser();p.add_argument('--verify-only',action='store_true');args=p.parse_args()
    while True:
        try:C.admit('r2-seal-verify' if args.verify_only else 'r2-seal');break
        except SystemExit as e:
            if e.code!=75:raise
            C.time.sleep(10)
    if args.verify_only:
        print('R2 HASH CHECK PASS',hashes(C.HERE,'SHA256SUMS_R2'),'public,',hashes(C.LOCAL,'SHA256SUMS'),'private',flush=True)
        return
    verification=C.read(C.LOCAL/'verification.json');assert verification['status']=='PASS'
    receipt=C.read(C.LOCAL/'report.json')
    report=(C.HERE/'REPORT_R2.md').read_text()
    assert report.splitlines()[0]==receipt['first_line']
    assert C.sha(C.HERE/'REPORT_R2.md')==receipt['report_sha256']
    assert not any(x in report for x in ('<img','data:image','![','GPSLatitude','GPSLongitude'))
    summary=C.read(C.LOCAL/'summary.json')
    assert len(summary['planned_table'])==13
    for r in summary['planned_table']:
        assert r['name'] in report
    coverage=C.read(C.LOCAL/'coverage.json')
    assert coverage['no_parameter_estimation']
    for path,digest in coverage['protected_sources'].items():assert C.sha(path)==digest
    page=Page();page.feed((C.LOCAL/'previews/index.html').read_text())
    from PIL import Image
    for relative in page.images:
        image=(C.LOCAL/'previews'/relative).resolve()
        assert image.is_relative_to(C.LOCAL) and image.is_file()
        with Image.open(image) as im:
            assert im.width==256;im.verify()
    assert len(page.images)==12
    # These checksums predate R2. They are not regenerated here.
    old_public=hashes(C.HERE,'SHA256SUMS')
    old_private=hashes(R1,'SHA256SUMS')
    allprivate=[p for p in C.LOCAL.rglob('*') if p.is_file()]
    relative=[str(p.relative_to(C.ROOT)) for p in allprivate]
    ignored=subprocess.run(['git','check-ignore','--stdin'],input='\n'.join(relative)+'\n',text=True,
                           cwd=C.ROOT,capture_output=True,check=True)
    assert set(relative)==set(ignored.stdout.splitlines())
    tracked=subprocess.check_output(['git','ls-files',str(C.LOCAL.relative_to(C.ROOT))],cwd=C.ROOT,text=True)
    assert not tracked.strip()
    decision('seal','封存R2并核对R1原清单全部通过','两轮证据保持可复查，图像只在local内',
             'local/r2/seal.json; SHA256SUMS_R2',f'R1 preserved: {old_public} public, {old_private} private files')
    files=sorted(p for p in C.LOCAL.rglob('*') if p.is_file() and p.name not in ('SHA256SUMS','seal.json')
        and p.suffix!='.log' and not p.is_relative_to(C.LOCAL/'queues') and not p.is_relative_to(C.LOCAL/'admissions'))
    (C.LOCAL/'SHA256SUMS').write_text(''.join(C.sha(p)+'  '+str(p.relative_to(C.LOCAL))+'\n' for p in files))
    public=sorted(C.HERE.glob('r2_*.py'))+[C.HERE/'REPORT_R2.md']
    (C.HERE/'SHA256SUMS_R2').write_text(''.join(C.sha(p)+'  '+p.name+'\n' for p in public))
    C.dump('seal.json',dict(status='PASS',public_files=len(public),private_files=len(files),
        R1_original_public_files_unchanged=old_public,R1_original_private_files_unchanged=old_private,
        local_review_images=len(page.images),private_files_tracked=0,no_image_payload_in_public_report=True,
        public_sums_sha256=C.sha(C.HERE/'SHA256SUMS_R2'),private_sums_sha256=C.sha(C.LOCAL/'SHA256SUMS'),
        created_utc=C.utc()))
    print('R2 SEAL PASS',len(public),'public,',len(files),'private; R1 unchanged',old_public,old_private,flush=True)


if __name__=='__main__':main()
