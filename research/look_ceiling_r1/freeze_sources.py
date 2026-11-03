"""Retain the exact read-only Studio source snapshot used for the calculations."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import tarfile
import shutil
import runtime as rt

def main():
    path=rt.LOCAL/'studio_source_snapshot.tar.gz'
    files=sorted(p for p in rt.SNAPSHOT.rglob('*') if p.is_file())
    with tarfile.open(path,'w:gz') as archive:
        for file in files:
            archive.add(file,arcname=str(file.relative_to(rt.SNAPSHOT)),recursive=False)
    rt.dump('studio_snapshot_receipt.json',dict(files=len(files),archive='local/'+path.name,
        archive_sha256=rt.sha(path),source_readonly=True,
        files_sha256={str(p.relative_to(rt.SNAPSHOT)):rt.sha(p) for p in files}))
    names=['docs/GXR_RECIPES_GUIDE.md','decisions.tsv','research/vlog_alchemy_eval/REPORT.md',
        'research/hw_mining_r1/SYNTHESIS.md','research/hw_mining_r2/SYNTHESIS.md','research/hw_mining_r3/SYNTHESIS.md',
        'research/hw_mining_r1/validation/VALIDATION.md','research/hw_mining_r2/validation/VALIDATION.md','research/hw_mining_r3/validation/VALIDATION.md',
        'research/mcr_value_model_r1/REPORT.md','research/g154/REPORT.md','research/cpu_speed_r1/REPORT.md',
        'research/color_fit_v2/fuji_round5/REPORT.md','research/gr4_lut_ceiling/REPORT.md',
        'research/bw03_round3/REPORT.md','research/fit_data_relocate_r1/REPORT.md']
    evidence=rt.read(rt.HERE/'evidence_sources.json') if (rt.HERE/'evidence_sources.json').exists() else []
    for name in names:
        source=rt.ROOT/name;digest=rt.sha(source);dest=rt.LOCAL/'reference_texts'/digest/name
        if any(r['source']==name and r['sha256']==digest for r in evidence):continue
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        evidence.append(dict(source=name,sha256=digest,private_snapshot=str(dest.relative_to(rt.HERE))))
    rt.dump('evidence_sources.json',evidence)
    seeds=[]
    for source in sorted((rt.LOCAL/'fits').glob('*/*.json')):
        if source.stem in ('L0','L1') or source.stem.endswith(('_fullfields','_physical')):continue
        seeds.append(dict(path=str(source.relative_to(rt.HERE)),sha256=rt.sha(source)))
    rt.dump('control_seed_inventory.json',seeds)
    rt.finish('freeze_sources')

if __name__=='__main__':main()
