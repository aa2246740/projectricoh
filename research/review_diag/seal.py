"""Check unchanged inputs and seal this review. All paths are repository-relative."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def check_manifest(path):
    count=0
    for line in path.read_text().splitlines():
        expected,name=line.split(None,1)
        name=name.removeprefix('*')
        file=ROOT/name
        assert digest(file)==expected,(name,'input drift')
        count+=1
    return count


def main():
    delivery=ROOT/'research/diag_dat_v1/SHA256SUMS'
    card=ROOT/'firmware/package_v36_diag1/CARD_SHA256SUMS'
    assert check_manifest(delivery)==14022
    assert check_manifest(card)==30
    source=ROOT/'firmware/package_v36_g120b/SD_ROOT'
    package=ROOT/'firmware/package_v36_diag1/local/SD_ROOT'
    files=sorted(x for x in package.iterdir() if x.is_file())
    assert len(files)==30
    fixed=[p for p in files if p.name!='GXRCE.DAT']
    assert len(fixed)==29
    assert all(digest(p)==digest(source/p.name) for p in fixed)
    review=(OUT/'REVIEW.md').read_text()
    assert review.splitlines()[0]=='不可以上测试卡'
    for file in ('REVIEW.md','CODEGEN.md'):
        for link in __import__('re').findall(r'\]\(([^)]+)\)',(OUT/file).read_text()):
            if link=='SHA256SUMS':continue
            assert (OUT/link).is_file(),(file,link)
    finish=datetime.now(timezone.utc)
    start=datetime(2026,10,28,15,15,27,tzinfo=timezone.utc)
    elapsed=(finish-start).total_seconds()/60
    assert elapsed<90,elapsed
    record=dict(start_utc=start.isoformat(),finished_utc=finish.isoformat(),
        elapsed_minutes=round(elapsed,2),timebox_minutes=90,
        input_manifest_sha256=digest(delivery),input_entries_verified=14022,
        card_manifest_sha256=digest(card),card_entries_verified=30,
        fixed_files_equal_to_gen120b=29,
        review_first_line=review.splitlines()[0],
        write_scope='research/review_diag/',network_camera_card_access=False)
    (OUT/'evidence/seal.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    protected=[delivery,card,package/'GXRCE.DAT',package/'ilaunch3',
        ROOT/'firmware/engine_diag_v1/candidate/local/full-r13/engine.elf',
        ROOT/'firmware/engine_diag_v1/candidate/containers/product/diag.c',
        ROOT/'firmware/engine_diag_v1/candidate/containers/product/diag_fields.h',
        ROOT/'firmware/engine_diag_v1/candidate/engine_services/services.c',
        ROOT/'firmware/engine_diag_v1/candidate/engine_services/native_seed.c',
        ROOT/'firmware/resident_v36/resident/hooks.c',
        ROOT/'firmware/resident_v36/resident/shared.c',
        ROOT/'firmware/resident_v36/resident/resident.h',
        ROOT/'firmware/resident_v36/local/resident/build/resident.map']
    manifest=OUT/'SHA256SUMS'
    output=[p for p in OUT.rglob('*') if p.is_file() and p!=manifest]
    paths=sorted(set(output+protected))
    manifest.write_text(''.join(f'{digest(p)}  {p.relative_to(ROOT)}\n' for p in paths))
    assert check_manifest(manifest)==len(paths)
    print('PASS sealed',len(paths),'files;',record['elapsed_minutes'],'minutes; input 14022/14022, card 30/30, fixed 29/29')


if __name__=='__main__':
    main()
