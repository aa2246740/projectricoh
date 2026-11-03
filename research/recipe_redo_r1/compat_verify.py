"""Rebuild compatible rows, predictions and fixtures from final record bytes."""
import argparse
import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import compat_g155c as compat
import runtime as rt
from runtime import np
import fit_one as fit
from entry_codec import predict,record_checks,look_identity_valid


def verify(family):
    root=compat.activate(family)
    receipts=[]
    for unit,indices in compat.TARGETS.items():
        ui=compat.UNITS.index(unit)
        for index in indices:
            meta_path=root/'targets'/unit/f'{index:02d}.json'
            meta=rt.read(meta_path);template=bytes.fromhex(meta['template_hex'])
            compat.configure(family,template,ui)
            camera=rt.Camera(ui);gradients,rings=fit.quality.fixtures(camera)
            for path in sorted((root/'fits'/unit/f'{index:02d}').glob('L0_*.json')):
                doc=rt.read(path);entry=path.with_suffix('.record552').read_bytes()
                checks=record_checks(entry)
                assert checks['sha256']==doc['record']['sha256'] and entry[1]==1
                assert checks['row_crcs_valid'] and checks['existing_row_domain_checks_pass']
                assert doc['target_sha256']==rt.sha(meta_path)
                if doc.get('parameters'):
                    rebuilt=fit.encode(template,doc['parameters'],level=0,look_unit_mask=1<<ui)
                    assert rebuilt==entry,('Rebuild mismatch',path)
                    assert look_identity_valid(entry,1<<ui)
                else:assert entry==template
                if family!='free':
                    assert entry[216:272]==template[216:272]
                    if family=='reuse_tone_matrix':
                        assert entry[20:115]==template[20:115] and entry[456:551]==template[456:551]
                    else:
                        assert entry[115:211]==template[115:211]
                        assert entry[20:82]==template[20:82] and entry[456:518]==template[456:518]
                points=0
                for group,scores in doc['scores'].items():
                    if scores is None:continue
                    data=rt.arrays(meta_path.with_name(f'{index:02d}_{group}.npz'))
                    prediction=predict(entry,data['x'],ui)
                    saved=rt.arrays(path.with_name(path.stem+'_'+group+'.npz'))['prediction']
                    assert np.array_equal(prediction,saved)
                    for role,output in [('candidate',prediction),('current',predict(template,data['x'],ui))]:
                        score=rt.score(data['base'],output,data['want'])
                        for metric in ('median','p95','max','mean'):
                            assert abs(score['de00'][metric]-scores[role]['de00'][metric])<1e-10
                    if group=='train':assert abs(fit.objective(prediction,data['want'],data['sw'])-doc['objective'])<1e-10
                    points+=len(prediction)
                quality=fit.guard(camera,entry,template,gradients,rings,ui,doc.get('gray',False))
                assert rt.plain(quality)==doc['quality']
                if doc.get('full_start_confirmation'):
                    manifest=rt.read(rt.HERE/doc['start_manifest'])
                    assert len(manifest['starts'])==len(doc['solver_attempts'])
                    assert rt.sha(rt.HERE/doc['start_manifest'])==doc['start_manifest_sha256']
                    source=rt.read(rt.HERE/doc['exact_confirmation_of'])
                    groups={key:rt.arrays(meta_path.with_name(f'{index:02d}_{key}.npz'))
                        for key in meta['input_file_sha256']}
                    gate=compat.gate_with_natural(source,entry,groups,ui)
                    assert gate==doc['reviewed_holdout_gate']
                receipts.append(dict(unit=unit,index=index,name=doc['name'],fit=str(path.relative_to(rt.HERE)),
                    fit_sha256=rt.sha(path),record_sha256=checks['sha256'],points_replayed=points,
                    flags=1,base05_flags=1,all_552_bytes_rebuilt=True,all_scores_replayed=True,
                    fixtures_rebuilt=True,full_start_confirmation=doc.get('full_start_confirmation',False),
                    exact_gate=doc.get('reviewed_holdout_gate',{}).get('status')))
    result=dict(status='PASS',family=family,records=receipts,record_count=len(receipts),
        no_DAT_built=True,scope='Computer prediction and record reconstruction only')
    rt.dump(root/'verification.json',result)
    print('COMPAT VERIFY',family,'PASS',len(receipts),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--family',required=True,choices=compat.FAMILIES)
    verify(ap.parse_args().family)
