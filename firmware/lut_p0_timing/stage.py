"""Stage only the exact candidate covered by all host evidence."""
import importlib.util
import json
from pathlib import Path

s=importlib.util.spec_from_file_location('stage_common',Path(__file__).with_name('common.py'))
c=importlib.util.module_from_spec(s);s.loader.exec_module(c)


def main():
    c.guard();c.run(['/usr/bin/python3','-I','-B',c.HERE/'freeze.py'],'freeze-before-stage')
    manifest=json.loads((c.LOCAL/'manifest.json').read_text());sha=c.sha(c.LOCAL/'GXRCE.DAT')
    assert sha==manifest['sha256'] and manifest['file_bytes']<=65536
    for name in ('host-results','replay-results','seed-replay-results','audit-results','r3-results','independent-kernel-results'):
        r=json.loads((c.LOCAL/(name+'.json')).read_text())
        assert r['status']=='PASS' and r['dat_sha256']==sha,(name,'stale evidence')
    for group in ('sources','headers'):
        for p,expected in manifest[group].items():assert c.sha(c.ROOT/p)==expected,('source drift',p)
    assert c.sha(c.ARCHIVE)==manifest['service_archive_sha256']
    services=json.loads((c.LOCAL/'service-build.json').read_text())
    assert services['status']=='PASS' and c.sha(c.ARCHIVE)==services['archive_sha256']
    for group in ('sources','copies'):
        for p,expected in services[group].items():assert c.sha(c.ROOT/p)==expected,('service source drift',p)
    host=json.loads((c.LOCAL/'host-results.json').read_text())
    assert host['first_entry']['published'] and host['first_entry']['old_seed_rejected']
    assert host['actual_product_generations']==[113,114] and host['native_view']['count']==1
    assert c.sha(c.LOCAL/'native_model.h')==host['native_model_sha256']
    assert c.sha(c.HERE/'native_model.py')==host['native_generator_sha256']
    for p,expected in host['sources'].items():assert c.sha(c.ROOT/p)==expected,('host source drift',p)
    for row in host['runs']:
        assert c.sha(c.ROOT/row['fixture'])==row['fixture_sha256']
        assert c.sha(c.ROOT/row['log'])==row['log_sha256']
    r3=json.loads((c.LOCAL/'r3-results.json').read_text())
    for p,expected in r3['test_sources'].items():assert c.sha(c.ROOT/p)==expected,('r3 test drift',p)
    assert r3['unchanged_value_negative_control'] and not r3['incomplete_has_tick_hz']
    independent=json.loads((c.LOCAL/'independent-kernel-results.json').read_text())
    assert independent['pairs']==16384 and independent['r2_output_bytes_equal']
    assert c.sha(c.HERE/'r3_replay.py')==independent['runner_sha256']
    r2=c.LOCAL/'staged_r2'
    for p,expected in json.loads((r2/'preserved.json').read_text()).items():
        assert c.sha(r2/p)==expected,('r2 preservation drift',p)
    assert c.sha(r2/'GXRCE.DAT')=='5a4f28efcf15ff4273d97b167c892c1cbab2ba3cd6d8804362afb246a9b931c5'
    dest=c.LOCAL/'staged';dest.mkdir(exist_ok=True)
    (dest/'GXRCE.DAT').write_bytes((c.LOCAL/'GXRCE.DAT').read_bytes())
    (dest/'SHA256SUMS').write_text(sha+'  GXRCE.DAT\n')
    assert c.sha(dest/'GXRCE.DAT')==sha
    c.save(c.LOCAL/'delivery.json',dict(status='STAGED_HOST_ONLY_REVIEW_PENDING',
        path=str(dest/'GXRCE.DAT'),sha256=sha,size=manifest['file_bytes'],margin=65536-manifest['file_bytes'],
        independent_review=False,card_write=False,camera_tested=False,network_used=False))
    print('STAGED '+str(dest/'GXRCE.DAT')+' sha256='+sha+' bytes='+str(manifest['file_bytes']))


if __name__=='__main__':main()
