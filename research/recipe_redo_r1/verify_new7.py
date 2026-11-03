"""Independently replay the new RAW holdout from full saved MOUNT records."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as rt
from runtime import np
from entry_codec import predict
import prepare_targets as pt
import argparse
from capabilities import mount_l1_enabled


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--level',type=int,choices=(0,1),default=1 if mount_l1_enabled() else 0)
    ap.add_argument('--tag',default='')
    args=ap.parse_args();suffix='_L1' if args.level else ''
    assert not args.tag or Path(args.tag).name==args.tag
    root = rt.LOCAL/('new7/recipe_holdout'+suffix+('_'+args.tag if args.tag else ''))
    materials=rt.read(rt.LOCAL/'new7/materials.json')
    assert len(materials)==7 and len({r['sha256'] for r in materials})==7
    assert not any(r['duplicate_prior_sensor_payload'] for r in materials)
    old_photos=rt.read(rt.LOCAL/'inputs/mount-a12/photos.json')
    assert not ({r['sha256'] for r in materials}&{r['sha256'] for r in old_photos})
    receipt = rt.read(root/'scores.json')
    assert receipt==rt.read(rt.HERE/('new7_raw_holdout_summary'+suffix+'.json'))
    if args.level:
        assert receipt['parameters_frozen_before_holdout_scoring']
        assert receipt['new7_not_used_in_training_objective_or_parameter_selection']
        assert not receipt.get('all_parameters_frozen_before_new_capture_notice',False)
    assert len(receipt['profiles'])==35 and rt.sha(root/'inputs.npz')==receipt['input_sha256']
    data = rt.arrays(root/'inputs.npz')
    dense = {slot:pt.builtin.DenseTarget(slot) for slot in (1,2)}
    cubes = pt.official()
    inverse = rt.arrays(root/'s1rii_inverse.npz')
    leica = rt.ROOT/'artifacts/downloads/huzi-panasonic-std-luts-20261024/original'
    checked = []
    for row in receipt['profiles']:
        index=row['index']
        meta=rt.read(rt.LOCAL/'targets/mount-a12'/f'{index:02d}.json')
        entry=(rt.HERE/row['record_file']).read_bytes()
        assert rt.sha(rt.HERE/row['record_file'])==row['record_sha256']
        values=rt.arrays(root/f'{index:02d}.npz')
        valid=values['valid_source_mask']
        stock=predict(rt.release_dat().entry_of(2,4),data['x'],2,round_output=False)
        assert np.array_equal(stock[valid],values['base'])
        if index<27:
            target=pt.Target(pt.Cube.read(Path(meta['source'])),meta['input'],meta['output'])
            want=(np.clip(target.cube.apply(pt.xyz_to_encoded(data['xyz'],'srgb')),0,1)*255
                  if meta['interpretation']=='scene' else target.render(stock,data['xyz']))
        else:
            slot=meta['builtin_slot']
            if slot in (1,2):
                want,mask,_=dense[slot](data['raw_codes'],data['xyz'],stock)
                assert np.array_equal(valid,mask)
            elif slot==3:
                want,mask,_=pt.builtin.hc_target(data['raw_codes'],data['xyz'],stock)
                assert np.array_equal(valid,mask)
            elif slot==4:
                want=stock.copy()
            elif slot in (5,6):
                want=cubes[slot,'historical'][0].apply(pt.fg_input(data['xyz']))*255
            else:
                cube=pt.Cube.read(leica/('Leica Chrome.cube' if slot==7 else 'Leica VIVID.cube'))
                want=np.clip(.3*inverse['rgb']+.7*cube.apply(inverse['rgb']/255)*255,0,255)
        assert np.array_equal(want[valid],values['want'])
        predicted=predict(entry,values['x'],2)
        assert np.array_equal(predicted,values['prediction'])
        normal=bytearray(entry)
        normal[0]=1
        independent=rt.camera_model(2).predict(bytes(normal),values['x'])
        assert np.array_equal(np.rint(independent),predicted)
        assert np.array_equal(predict(bytes.fromhex(meta['template_hex']),values['x'],2),values['current'])
        for name,prediction in (('current',values['current']),('candidate',predicted)):
            actual=rt.score(values['base'],prediction,values['want'])
            assert actual==row[name]
        passed=(row['candidate']['de00']['median']<=row['current']['de00']['median']+1e-10
                and row['candidate']['de00']['p95']<=row['current']['de00']['p95']+1e-10)
        assert passed==row['scene_gate_pass']
        checked.append(dict(index=index,record_sha256=row['record_sha256'],points=len(predicted),
                            want_reconstructed=True,ordinary_Standard_replayed=True,scores_recomputed=True))
    rt.dump('new7_raw_holdout_verification'+suffix+'.json',dict(status='PASS',created_utc=rt.utc(),profiles=35,
        level=args.level,rows=checked,input_sha256=receipt['input_sha256'],summary_sha256=rt.sha(rt.HERE/('new7_raw_holdout_summary'+suffix+'.json')),
        source_receipt_sha256=rt.sha(root/'scores.json'),no_observed_jpeg_used=True,
        no_04_identity_promotion=True,no_parameter_changes=True))
    print('New RAW holdout replay PASS',len(checked),'profiles',sum(r['points'] for r in checked),'points')


if __name__=='__main__':
    main()
