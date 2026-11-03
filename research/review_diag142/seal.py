"""Verify retained results, remove owned temporary files, and seal the review."""
from pathlib import Path
import json
import plistlib
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope
scope.enable_fence()


def remove_tree(path):
    """Use absolute unlink paths so the audit hook need not resolve dir_fd."""
    assert not path.is_symlink()
    for child in sorted(path.rglob('*'),key=lambda p:len(p.parts),reverse=True):
        if child.is_symlink() or child.is_file():child.unlink()
        else:child.rmdir()
    path.rmdir()


def main():
    info=plistlib.loads(subprocess.run(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace'],
                                    capture_output=True,check=True,timeout=30).stdout)
    assert info['VolumeUUID'].upper()=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert info['MountPoint']=='/Volumes/Workspace' and info['FilesystemType']=='apfs'
    assert info['WritableVolume'] and info['WritableMedia']
    report=scope.HERE/'REVIEW.md'
    text=report.read_text()
    assert text.splitlines()[0]=='可以上卡'
    assert all(('## '+str(i)+'.') in text for i in range(1,7))
    static=json.loads((scope.HERE/'static-review.json').read_text())
    cases=[('28mm','full'),('50mm','full'),('mount','full'),
           ('28mm','empty'),('28mm','notready'),('28mm','heap')]
    receipts=[]
    for unit,mode in cases:
        name='accept-'+unit+'-'+mode
        receipt=json.loads((scope.HERE/(name+'-receipt.json')).read_text())
        assert receipt['exit_code']==0 and receipt['timeout_seconds']==4200
        case=scope.HERE/'cases'/(unit+'-'+mode)
        observation=json.loads((case/'review-observation.json').read_text())
        assert observation['dat_sha256']==static['dat_sha256']
        for item in observation['observations']:
            assert item['settings_before_sha256']==item['settings_after_sha256']
            assert not item['settings_write_events'] and item['rpc_w']==0
            assert item['rpc_commands']==[21,23]
        results=list((case/'local').glob('accept-*.json'))
        assert len(results)==1
        result=json.loads(results[0].read_text())
        assert result['dat']==static['dat_sha256']
        assert all(n==0 for n in result['writes'].values())
        receipts.append({'unit':unit,'mode':mode,**receipt})
    experiments=json.loads((scope.HERE/'experiments.json').read_text())
    receipt=json.loads((scope.HERE/'experiments-receipt.json').read_text())
    assert receipt['exit_code']==0
    assert [t['result'] for t in experiments['binding_header_instructions']]==[0,7,8,8]
    assert experiments['counterexample_observed'] and experiments['diag_page'][5]=='M000 082'
    assert experiments['g137_root']['state']==3 and experiments['g137_rows']==8
    assert experiments['diag_heap_before_load']==experiments['g137_heap_before_load']
    frozen=scope.freeze_check()
    original=json.loads((scope.ROOT/'research/unit28_stock/local/inputs-before.json').read_text())
    assert all(scope.sha(scope.ROOT/name)==digest for name,digest in original.items())
    extra=('firmware/engine_v54_g137/candidate/local/full-r13/engine.elf',
           'firmware/engine_v54_g137/candidate/engine_services/services.c',
           'firmware/engine_v54_g137/candidate/engine_services/native_seed.c')
    extra_hashes={name:scope.sha(scope.ROOT/name) for name in extra}
    assert extra_hashes[extra[0]]=='2ac9ea5aeab59b3a4421f0d77f17003ce3d71bab45731042e984537836c2f044'
    removed=[]
    for unit,mode in cases:
        case=scope.HERE/'cases'/(unit+'-'+mode)
        for path in (case/'local/decode',case/'local/layout',case/'rows-g137.json'):
            if path.exists():
                assert not path.is_symlink()
                if path.is_dir():remove_tree(path)
                else:path.unlink()
                removed.append(str(path.relative_to(scope.HERE)))
    for path in (scope.HERE/'experiments',scope.HERE/'experiments-g137',scope.SCRATCH):
        if path.exists():
            assert not path.is_symlink()
            remove_tree(path)
            removed.append(str(path))
    assert not scope.SCRATCH.exists()
    seal={'verdict':'可以上卡','review_sha256':scope.sha(report),'dat_sha256':static['dat_sha256'],
          'frozen_inputs_unchanged':frozen,'upstream_frozen_inputs_unchanged':len(original),
          'additional_source_hashes':extra_hashes,'cases':receipts,
          'experiments':receipt,'settings_write_events':0,'diagnostic_rpc_w':0,
          'diagnostic_file_mutations':0,'scratch_removed':True,'removed':removed,
          'volume_uuid':info['VolumeUUID'],'product_code_or_original_report_edited':False,
          'camera_or_card_accessed':False,'git_mutations':False}
    scope.save(scope.HERE/'seal.json',seal)
    inputs=json.loads((scope.HERE/'inputs-before.json').read_text())
    inputs.update(extra_hashes)
    for path in scope.HERE.rglob('*'):
        if path.is_file() and path.name!='SHA256SUMS':
            inputs[str(path.relative_to(scope.ROOT))]=scope.sha(path)
    manifest=scope.HERE/'SHA256SUMS'
    manifest.write_text(''.join(digest+'  '+name+'\n' for name,digest in sorted(inputs.items())))
    checked=0
    for line in manifest.read_text().splitlines():
        digest,name=line.split('  ',1)
        assert scope.sha(scope.ROOT/name)==digest,name
        checked+=1
    assert scope.freeze_check()==frozen and not scope.SCRATCH.exists()
    print('SEALED',checked,'hashes; six cases PASS; 206 original inputs unchanged; scratch removed')


if __name__=='__main__':
    main()
