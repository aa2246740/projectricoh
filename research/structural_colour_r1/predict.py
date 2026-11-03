"""Re-evaluate conditional one/two-pass models using this task's copied code."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as fence
import argparse
import csv
import importlib.util
import time

p=argparse.ArgumentParser()
p.add_argument('--indices',default='0:27,43:51')
args=p.parse_args()
indices=[]
for part in args.indices.split(','):
    if ':' in part:
        aa,bb=map(int,part.split(':'));indices.extend(range(aa,bb))
    else:indices.append(int(part))
assert set(indices)<=set(range(27))|set(range(43,51))
code=fence.HERE/'model_copy'
spec=importlib.util.spec_from_file_location('runtime',code/'runtime.py')
rt=importlib.util.module_from_spec(spec)
sys.modules['runtime']=rt
spec.loader.exec_module(rt)
sys.path.insert(0,str(code))
from ceiling_model import Problem
from two_pass import Joint
from run import load_arrays
np=rt.np
rows=[]
max_difference=0.
started=time.monotonic()
for index in indices:
    meta=rt.read(rt.LOCAL/f'target_{index:02d}.json')
    data=load_arrays(rt.LOCAL/f'target_{index:02d}.npz')
    groups={key:load_arrays(rt.LOCAL/meta.get('group_files',{}).get(key,'samples_'+key+'.npz'))
        for key in ('train','a12-50','mount-a12')}
    c=rt.camera_for_unit(meta.get('camera_ui',0))
    x,sw=groups['train']['x'],groups['train']['sw']
    output_dir=rt.LOCAL/'replay'/f'{index:02d}'
    output_dir.mkdir(parents=True,exist_ok=True)
    for axis in ('Y','C'):
        key='L4_'+axis+'_post_add_after_Rbefore_fullfields'
        reference=rt.read(rt.LOCAL/'fits'/f'{index:02d}'/(key+'.json'))
        first=Problem(c,x,data['train_target'],sw,reference['config'])
        state=first.unpack(reference['parameters'])
        singles={}
        for group in ('a12-50','mount-a12'):
            g=groups[group]
            if not len(g['x']):continue
            pred=first.predict_state(state,g['x'])
            score=rt.score(data[group+'_base'],pred,data[group+'_target'])
            old=reference['scores'][group]['de00']['median']
            max_difference=max(max_difference,abs(score['de00']['median']-old))
            assert abs(score['de00']['median']-old)<1e-8
            singles[group]=score
        for level in (1,4):
            directory='two_pass_full'+('_C' if axis=='C' else '')
            doc=rt.read(rt.LOCAL/directory/f'{index:02d}'/('body_L'+str(level)+'.json'))
            model=Joint(c,x,data['train_target'],sw,level,True,axis)
            theta=np.asarray(doc['theta'])
            assert len(theta)==model.np
            assert doc['hardware_main_JPEG_path_closed'] is False
            assert doc['body_pixel_equation_verified'] is False
            saved={}
            for group,single in singles.items():
                pred=model.predict(theta,groups[group]['x'])
                score=rt.score(data[group+'_base'],pred,data[group+'_target'])
                error=abs(score['de00']['median']-doc['scores'][group]['de00']['median'])
                max_difference=max(max_difference,error)
                assert error<1e-8,(index,axis,level,group,error)
                a,b=single['similarity_percent'],score['similarity_percent']
                row=dict(index=index,name=meta['name'],group=group,axis_hypothesis=axis,body_level=level,
                    label='电脑预测，冻结双程假设复算',single_percent=a,two_pass_percent=b,
                    gain_pp=None if a is None or b is None else b-a,
                    single_de00_median=single['de00']['median'],two_pass_de00_median=score['de00']['median'],
                    baseline_de00_median=score['baseline_de00']['median'],n=score['de00']['n'],
                    hardware_equation_closed=False,main_JPEG_route_closed=False)
                rows.append(row)
                saved[group]=pred.astype(np.uint8)
            np.savez_compressed(output_dir/(axis+'_body_L'+str(level)+'.npz'),**saved)
    print(index,meta['name'],'frozen model replay passed',flush=True)
output=fence.HERE/'predictions.csv'
if output.exists():
    previous=list(csv.DictReader(output.open()))
    previous=[v for v in previous if int(v['index']) not in indices]
else:previous=[]
all_rows=previous+rows
all_rows.sort(key=lambda v:(int(v['index']),v['group'],v['axis_hypothesis'],int(v['body_level'])))
with output.open('w',newline='') as dst:
    writer=csv.DictWriter(dst,fieldnames=list(rows[0]))
    writer.writeheader();writer.writerows(all_rows)
fence.dump(fence.LOCAL/('prediction-check-'+args.indices.replace(':','-').replace(',','_')+'.json'),
    dict(indices=indices,rows=len(rows),max_saved_score_difference=max_difference,
         seconds=time.monotonic()-started,refit=False,physical_new_candidate_equations_closed=0))
rt.finish('prediction_runtime')
fence.finish('predict')
