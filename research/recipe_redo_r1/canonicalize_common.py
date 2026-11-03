"""Emit shared-curve records when an L1 solution has exactly equal RGB curves."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
import argparse
import copy
import shutil
from report import select
from entry_codec import encode,predict,record_checks
from fit_one import guard,quality


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--unit',choices=('mount-a12','a12-50','a12-28'),required=True)
    ap.add_argument('--tag',required=True);args=ap.parse_args()
    snapshot=rt.freeze_task_code()
    ui=('a12-50','a12-28','mount-a12').index(args.unit)
    camera=rt.Camera(ui);gradients,rings=quality.fixtures(camera)
    converted=[]
    for index in range(35):
        folder=rt.LOCAL/'fits'/args.unit/f'{index:02d}'
        path,doc=select(folder.glob('L1_*.json'))
        assert doc
        if not doc.get('parameters') or not doc['record']['independent_curves']:
            continue
        curves=doc['parameters']['curve_y_u8']
        if not (len(curves)==3 and curves[0]==curves[1]==curves[2]):continue
        meta=rt.read(rt.LOCAL/'targets'/args.unit/f'{index:02d}.json')
        template=bytes.fromhex(meta['template_hex'])
        old=path.with_suffix('.record552').read_bytes()
        new=encode(template,doc['parameters'],level=0,gray=doc.get('gray',False),
                   mirror_iso100=doc.get('mirror_iso100_curve',False),look_unit_mask=doc.get('look_unit_mask'))
        output=folder/('L1_'+args.tag)
        assert not output.with_suffix('.json').exists() and not output.with_suffix('.record552').exists()
        points=0
        for group,score in doc['scores'].items():
            if not score:continue
            data=rt.arrays(rt.LOCAL/'targets'/args.unit/f'{index:02d}_{group}.npz')
            assert np.array_equal(predict(old,data['x'],ui),predict(new,data['x'],ui))
            points+=len(data['x'])
            shutil.copyfile(path.parent/(path.stem+'_'+group+'.npz'),output.parent/(output.name+'_'+group+'.npz'))
        q=guard(camera,new,template,gradients,rings,ui,doc.get('gray',False))
        assert q==doc['quality']
        result=copy.deepcopy(doc)
        result.update(requested_tag=args.tag,record_encoding_level=0,record=record_checks(new),
            record_path=str(output.with_suffix('.record552').relative_to(rt.HERE)),
            canonical_equivalence_parent=str(path.relative_to(rt.HERE)),
            canonical_equivalence_parent_sha256=rt.sha(path),
            postprocess_code_snapshot=snapshot,
            canonicalization='Equal RGB curves use the existing shared-curve control; all model predictions and guards unchanged',
            no_independent_mode_switch_required=True,canonical_prediction_points=points)
        output.with_suffix('.record552').write_bytes(new)
        rt.dump(output.with_suffix('.json'),result)
        converted.append(dict(index=index,name=doc['name'],old_sha256=doc['record']['sha256'],
                              new_sha256=result['record']['sha256'],points=points))
    rt.assert_task_code(snapshot)
    rt.dump(rt.LOCAL/'canonicalization'/f'{args.unit}_{args.tag}.json',dict(status='PASS',records=converted,
        no_fit_or_holdout_parameter_selection=True,physical_switch_avoided_only_for_exactly_equal_curves=True))
    print('Shared-curve canonicalization',args.unit,len(converted),'records')


if __name__=='__main__':main()
