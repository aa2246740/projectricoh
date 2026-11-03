"""Stdlib-only final verification receipts, named Scratch cleanup, and SHA-256 seal."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCAL=HERE/'local'
SCRATCH=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/look-ceiling-r1')

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def read(p):return json.loads(p.read_text())
def dump(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--clean',action='store_true');args=ap.parse_args()
    volume=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
    assert Path('/Volumes/Workspace').is_mount() and volume['FilesystemType']=='apfs'
    assert volume.get('DiskUUID',volume.get('VolumeUUID'))=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert volume['WritableVolume'] and volume['WritableMedia']
    required=('REPORT.md','METHODS.md','PROBES.md','PROGRESS.md','REPRODUCE.md','comparison.html',
        'results.json','results_auxiliary.json','all_scores.csv','scores.csv','quality.csv','primary_quality.json',
        'recipe_roadmap.json','storage_costs.json','look_payload_costs.csv','software_lut_estimates.json',
        'published_axis_seed_checks.json','environment.json','error_modes.json','original_flog2_results.json')
    for name in required:assert (HERE/name).is_file(),name
    for name in ('REPORT.md','METHODS.md','PROBES.md','REPRODUCE.md'):
        for target in re.findall(r'\[[^\]]*\]\(([^)\n]+)\)',(HERE/name).read_text()):
            if '://' in target or target.startswith('#'):continue
            if target in ('verification.json','inputs_used.json','cleanup.json','SHA256SUMS'):continue
            assert (HERE/target.split('#',1)[0]).resolve().exists(),(name,target)
    checks=[read(LOCAL/f'verification_{a:02d}_{b:02d}.json') for a,b in ((0,18),(18,36),(36,51))]
    assert sum(v['primary_fits'] for v in checks)==1530
    assert sum(v['quality_fixtures_recomputed'] for v in checks)==1530
    aux=read(LOCAL/'verification_auxiliary.json')
    assert aux['full_two_stage_group_scores']==408
    assert aux['free_curve_group_scores']==408
    assert aux['published_axis_group_scores']==408
    assert aux['full_two_stage_C_group_scores']==280
    result=read(HERE/'results.json')
    assert result['primary_fit_count']==1530 and not result['partial']
    historical=read(HERE/'original_flog2_results.json')['verification']
    assert historical['status']=='PASS' and historical['integer_models']==180 and historical['quality_cases']==180
    expected={}
    for path in sorted(LOCAL.glob('input_hashes*.json')):
        for name,digest in read(path).items():expected.setdefault(name,set()).add(digest)
    relocation=read(HERE/'relocation_receipt.json')
    aliases={r['old']:r['new'] for r in relocation['data_paths']}
    old_fits=read(ROOT/'artifacts/downloads/vlog-alchemy-eval-20261102/look_fits.json')['fits']
    original_groups=0
    for i in range(27):
        meta=read(LOCAL/f'target_{i:02d}.json');old=next(r for r in old_fits if r['name']==meta['name'])
        assert meta['baseline_exact_reproduction']
        for group in ('a12-50','mount-a12'):
            aa=meta['scores'][group];bb=old['units'][group]['photo_holdout']
            assert abs(aa['similarity_percent']-bb['similarity_percent'])<1e-10
            for field in ('median','p95','max'):assert abs(aa['de00'][field]-bb['de00'][field])<1e-10
            original_groups+=1
    approved_versions={r['path']:{r['before_sha256'],r['after_sha256']} for r in relocation['authorized_source_changes']}
    versions={name:sorted(digests) for name,digests in expected.items() if len(digests)>1}
    source=read(HERE/'studio_snapshot_receipt.json')
    assert sha(LOCAL/'studio_source_snapshot.tar.gz')==source['archive_sha256']
    import tarfile
    with tarfile.open(LOCAL/'studio_source_snapshot.tar.gz','r:gz') as archive:
        for name,digest in source['files_sha256'].items():
            assert hashlib.sha256(archive.extractfile(name).read()).hexdigest()==digest
    text_sources={}
    for r in read(HERE/'evidence_sources.json'):
        assert sha(HERE/r['private_snapshot'])==r['sha256']
        text_sources.setdefault(r['source'],set()).add(r['sha256'])
    for name,digests in versions.items():
        allowed=approved_versions.get(name,set())|text_sources.get(name,set())
        assert set(digests)<=allowed,(name,digests)
    drift=[];frozen_covered=[];frozen_text=[]
    for name,digests in sorted(expected.items()):
        p=ROOT/aliases.get(name,name);actual=sha(p) if p.is_file() else None
        if actual not in digests:
            if name.startswith('studio/src/') and ('src/'+name.removeprefix('studio/src/')) in source['files_sha256']:
                frozen_covered.append(name)
            elif name in text_sources and text_sources[name]&digests:
                frozen_text.append(name)
            else:drift.append(dict(path=name,expected=sorted(digests),current=actual))
    dump(HERE/'inputs_used.json',dict(inputs=[dict(path=k,sha256=sorted(v)) for k,v in sorted(expected.items())],
        unexpected_live_drift=drift,studio_live_drift_covered_by_frozen_archive=frozen_covered,
        text_live_drift_covered_by_private_snapshot=frozen_text,byte_identical_data_relocations=relocation['data_paths'],
        observed_source_versions=versions,
        authorized_routing_code_versions={k:v for k,v in versions.items() if k in approved_versions}))
    assert not drift,drift
    dump(HERE/'verification.json',dict(label='电脑预测，离线研究验收',status='NUMERICS_PASS_PROCESS_LIMIT_EXCEPTION',
        numeric_status='PASS',scope_policy_status='PROCESS_LIMIT_EXCEPTION',
        primary_fits=1530,target_unit_profiles=51,integer_parameters_before_scoring=True,
        historical_FLog2_supplement=historical,total_integer_models_verified=1710,
        original27_published_photo_groups_exact=original_groups,
        reconstructed_pixels=sum(v['pixels_reconstructed'] for v in checks),
        quality_fixtures_recomputed=1530,auxiliary=aux,input_paths=len(expected),
        frozen_studio_source_files=source['files'],studio_live_drift_frozen=len(frozen_covered),
        text_live_drift_frozen=frozen_text,
        authorized_data_relocations=relocation['data_paths'],observed_source_versions=versions,
        unexpected_input_drift=0,model_derivative_checks=read(HERE/'model_checks.json'),
        two_stage_derivative_checks=read(HERE/'two_pass_full_checks.json'),
        two_stage_C_derivative_checks=read(HERE/'two_pass_full_checks_C.json'),
        camera_acceptance=False,card_access=False,firmware_or_DAT_built=False,
        git_writes=False,subagents_spawned=False,
        process_policy=dict(nice=10,numeric_threads=1,normal_max_numeric_processes=3,
            brief_rescheduling_overlap_processes=4,
            exception='At 05:50 UTC a replacement process briefly overlapped the old bounded job; the old job was immediately interrupted. Preserved partial bounded fits are sensitivity only.'),
        completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    if args.clean:
        processes=subprocess.check_output(['ps','-axo','pid,args'],text=True).splitlines()
        active=[]
        for line in processes:
            parts=line.strip().split(None,1)
            if len(parts)<2 or not parts[0].isdigit() or int(parts[0])==os.getpid():continue
            executable=Path(parts[1].split(None,1)[0]).name.lower()
            if 'python' in executable and 'look_ceiling_r1' in parts[1]:active.append(line)
        assert not active,active
        assert SCRATCH==Path('/Volumes/Workspace/Scratch/tmp/projectricoh/look-ceiling-r1') and not SCRATCH.is_symlink()
        existed=SCRATCH.exists()
        if existed:shutil.rmtree(SCRATCH)
        assert not SCRATCH.exists()
        dump(HERE/'cleanup.json',dict(path=str(SCRATCH),removed=existed,absent=True,
            utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),retained_private_inputs='local/'))
    files=sorted(p for p in HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    manifest=''.join(sha(p)+'  '+str(p.relative_to(HERE))+'\n' for p in files)
    (HERE/'SHA256SUMS').write_text(manifest)
    if args.clean:
        for name in ('verification.json','inputs_used.json','cleanup.json','SHA256SUMS'):assert (HERE/name).is_file()
    for line in manifest.splitlines():
        digest,name=line.split('  ',1);assert sha(HERE/name)==digest,name
    print('SHA256SUMS verified',len(files),'files; Scratch absent:',not SCRATCH.exists(),flush=True)

if __name__=='__main__':main()
