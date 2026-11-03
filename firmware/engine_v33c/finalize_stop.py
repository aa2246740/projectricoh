"""Seal the R6-01 stop evidence without producing or staging a candidate."""
import json
from pathlib import Path
import plistlib
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c


def volume():
    info=plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert info['MountPoint']=='/Volumes/Workspace' and info['FilesystemType']=='apfs'
    assert info['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['WritableVolume'] and info['WritableMedia']


def check():
    volume();n=c.freeze_check();seen=set()
    for row in (c.HERE/'SHA256SUMS').read_text().splitlines():
        digest,path=row.split('  ',1)
        p=c.HERE/path;p.resolve().relative_to(c.HERE)
        assert not p.is_symlink() and c.sha(p)==digest,path
        seen.add(path)
    actual={str(p.relative_to(c.HERE)) for p in c.HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
    assert actual==seen
    stop=json.loads((c.LOCAL/'STOP.json').read_text())
    assert stop['status']=='STOPPED_NOT_STAGED' and stop['product_assertions_pass'] is False
    assert not (c.LOCAL/'full-r7').exists() and not (c.LOCAL/'card_update').exists()
    print(f'PASS evidence manifest: {len(seen)} files; {n} protected inputs unchanged. Product remains blocked.')


def main():
    if sys.argv[1:]==['--check']:
        check();return
    assert not sys.argv[1:]
    c.guard();n=c.freeze_check();volume()
    upstream=c.ROOT/'firmware/engine_v33b'
    copied=[]
    for relative in ('containers/product','engine_services'):
        for p in sorted((upstream/relative).rglob('*')):
            if p.is_file():
                out=c.HERE/p.relative_to(upstream)
                assert c.sha(out)==c.sha(p),str(out)
                copied.append(str(out.relative_to(c.HERE)))
    results=json.loads((c.LOCAL/'boundary-results.json').read_text())
    assert results['runs']==38 and results['first_build_required_assertions']==10
    assert results['first_build_failures']==10 and results['product_assertions_pass'] is False
    commands=[json.loads(line) for line in (c.LOCAL/'commands.jsonl').read_text().splitlines()]
    runs=[r for r in commands if r['label'].startswith(('review-','boundary-'))]
    labels={r['label'] for r in runs}
    assert len(labels)==38 and len(runs)%38==0
    rounds=len(runs)//38
    assert rounds>=2 and all(sum(r['label']==label for r in runs)==rounds for label in labels)
    assert all(r['returncode']==(1 if r['label'].startswith('boundary-') else 0) for r in runs)
    logs=json.loads((c.LOCAL/'review-log-read.json').read_text())
    assert len(logs)==1944
    assert all(c.sha(c.ROOT/r['path'])==r['sha256'] for r in logs)
    before=(c.LOCAL/'git-before.txt').read_text().splitlines()
    after=subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=no'],cwd=c.ROOT,text=True).splitlines()
    normalize=lambda x:[r for r in x if r[3:]!='decisions.tsv']
    assert normalize(before)==normalize(after)
    assert (c.HERE/'.gitignore').read_text()=='/local/\n'
    assert not (c.LOCAL/'full-r7').exists() and not (c.LOCAL/'card_update').exists()
    identities={
        'full_r6_sha256':c.sha(upstream/'local/full-r6/GXRCE.DAT'),
        'approved_body_sha256':c.sha(c.ROOT/'firmware/image_v3/local/candidate-v32/candidate/SD_ROOT/ilaunch3'),
        'resident_elf_sha256':c.sha(c.UPSTREAM/'local/resident/build/resident.elf')}
    assert identities['full_r6_sha256']=='8ae376fe5edd4a2f78dbf3f9db95a70313f59d136f21ca300b4eb657b9e264d6'
    assert identities['approved_body_sha256']=='05b46ee65f4861f2e09e9b7c519cbcc2dffb195158a40c3bb033540b36a98d8c'
    assert identities['resident_elf_sha256']=='f25899258471d0652a8fef8980b9f0a83a0ca7cd4ddc6bbe8fcc337467362b58'
    sizes=json.loads((upstream/'local/artifact-inspection.json').read_text())['sizes']
    c.save(c.LOCAL/'STOP.json',dict(status='STOPPED_NOT_STAGED',reason='R6-01: no existing engine callback after native cursor stores before first frame',
        product_assertions_pass=False,target_generation=109,candidate_built=False,candidate_staged=False,
        memory_write_policy_changed=False,r6_02_fixed=False,engine_only_fix_implemented=False,
        unique_host_cases=38,host_runs=len(runs),required_first_build_failures_per_round=10,rounds=rounds,
        full_r6_sizes=sizes,**identities))
    c.save(c.LOCAL/'scope.json',dict(protected_inputs=n,protected_inputs_unchanged=True,
        product_service_files_unchanged=copied,tracked_status_unchanged_except_decisions=True,
        write_root=str(c.HERE),no_card_access=True,no_resident_or_body_rebuild=True))
    paths=sorted(p for p in c.HERE.rglob('*') if p.is_file() and p.name!='SHA256SUMS')
    assert not any(p.is_symlink() for p in paths)
    (c.HERE/'SHA256SUMS').write_text(''.join(c.sha(p)+'  '+str(p.relative_to(c.HERE))+'\n' for p in paths))
    check()


if __name__=='__main__':main()
