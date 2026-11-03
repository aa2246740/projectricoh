#!/usr/bin/env python3
"""Verify input immutability, artifact hashes, flat ROIs and evidence gates."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import prepare
import engine as e
import numpy as np
import scipy
from PIL import Image, __version__ as PIL_VERSION

PUBLIC_NAMES={'.gitignore','prepare.py','engine.py','measure_models.py','metering.py',
              'write_report.py','verify.py','REPORT.md','SHA256SUMS'}
LOCAL_EXCLUDED={'SHA256SUMS','verification.json'}


def files(base,local=False):
    return sorted(p for p in base.rglob('*') if p.is_file()
                  and (local or not p.is_relative_to(e.LOCAL))
                  and (str(p.relative_to(base)) not in LOCAL_EXCLUDED if local else p.name!='SHA256SUMS'))


def manifest(base,path,local=False):
    path.write_text(''.join(f'{prepare.sha(p)}  {p.relative_to(base).as_posix()}\n' for p in files(base,local)))


def check_manifest(base,path,local=False):
    expected={p.relative_to(base).as_posix() for p in files(base,local)}
    recorded=set()
    for line in path.read_text().splitlines():
        digest,name=line.split('  ',1)
        assert re.fullmatch('[a-f0-9]{64}',digest)
        p=(base/name).resolve()
        assert p.is_relative_to(base.resolve()) and not (base/name).is_symlink()
        assert name not in recorded and prepare.sha(p)==digest,name
        recorded.add(name)
    assert recorded==expected,{'missing':sorted(expected-recorded),'extra':sorted(recorded-expected)}
    return len(recorded)


def numerical_checks():
    de=float(e.cm.delta_e00([50.,2.6772,-79.7751],[50.,0.,-82.7485]))
    assert abs(de-2.0425)<5e-5,de
    summary=e.read(e.LOCAL/'model_summary.json')
    jpg_count=0
    max_jpeg_difference=0.
    for name in e.SCENES:
        md=e.read(e.LOCAL/f'{name}_metadata.json');data,_=e.load_scene(name)
        check=md['decoder']
        assert check.get('prefix_rows_mismatch',0)==0
        rec=e.read(e.LOCAL/f'{name}_samples.json')
        assert len(rec['chart'])==24
        assert len(rec['flats'])==summary['scenes'][name]['distribution']['all_flat']['n']
        target=e.read(e.LOCAL/f'{name}_model_only_targets.json')
        assert target['training_approved'] is False
        assert target['gxr_training_pair_available'] is False and target['metering_anchor_available'] is False
        assert target['measured_styled_IR_available'] is False
        assert len(target['labels'])==len(target['raw'])==len(target['targets']['positive'])==len(target['targets']['negative'])
        assert data['rgb'].shape==(2000,3000,3) and data['clip'].shape==(2000,3000)
        with Image.open(e.DATA/e.SCENES[name][1]) as image:
            jpg=np.asarray(image.convert('RGB'))
        for row in rec['chart']:
            # The bastibe boxes are aligned down to even CFA coordinates in this run.
            x0,y0,x1,y1=(np.array(row['box'])//2*2).astype(int)
            actual=jpg[y0:y1,x0:x1].mean((0,1))/255
            diff=float(np.max(np.abs(actual-np.array(row['jpeg']))))
            assert diff<1e-12,(name,row['label'],diff)
            max_jpeg_difference=max(max_jpeg_difference,diff);jpg_count+=1
            predicted=e.render(row['raw'],data['neutral'])
            calculated=float(e.cm.delta_e00(e.cm.rgb_lab(predicted),e.cm.rgb_lab(actual)))
            assert abs(calculated-row['de00'])<1e-10
        for row in rec['flats']:
            assert max(row['jpeg_std'])<=3 and row['jpeg_max']<251
            assert row['raw_clip_fraction']==0 and row['raw_min']>0 and 10<=row['lab'][0]<=95
        for row in rec['semantic']:
            assert max(row['jpeg_std'])<=3 and row['jpeg_max']<251 and row['raw_clip_fraction']==0
        observed=np.array([r['de00'] for r in rec['chart']])
        assert abs(float(np.median(observed))-summary['scenes'][name]['chart']['median'])<1e-12
    meter=e.read(e.LOCAL/'metering_summary.json');anchor=e.read(e.LOCAL/'anchor_diagnostic.json')
    assert meter['trusted_metering_anchor_available'] is False and meter['point_metering_u_be'] is None
    assert anchor['approved_for_gr_round6'] is False and anchor['credible_anchor'] is False
    assert anchor['anchor_u_be'] is None and anchor['anchor_jpeg_standard'] is None
    reproduction={}
    for slot,expected in [('01',.306761387428),('02',.420008079852)]:
        actual=meter['target_sensitivity'][slot]['frozen_generator_vs_current_targets_colour']['median']
        assert abs(actual-expected)<1e-9,(slot,actual)
        reproduction[slot]=actual
    return dict(ciede2000_reference=de,original_jpeg_chart_rois_checked=jpg_count,
                jpeg_max_absolute_difference=max_jpeg_difference,round5_target_reproduction=reproduction)


def public_checks():
    actual={p.name for p in e.HERE.iterdir() if p.is_file()}
    assert actual<=PUBLIC_NAMES,actual-PUBLIC_NAMES
    nested=[p for p in e.HERE.iterdir() if p.is_dir() and p!=e.LOCAL]
    assert not nested,nested
    for path in files(e.HERE):
        assert not path.is_symlink()
        text=path.read_text()
        assert not re.search(r'(?i)(?<![0-9a-f])[0-9a-f]{96,}(?![0-9a-f])',text),path
        if path.suffix=='.py':
            tree=ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node,ast.Constant) and isinstance(node.value,bytes):
                    assert len(node.value)<48,path
    assert not list(e.HERE.rglob('__pycache__')),'bytecode was written'
    return len(actual)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seal',action='store_true');args=parser.parse_args()
    prepare.gate();prepare.check_data_manifest()
    inputs=e.read(e.LOCAL/'inputs.sha256.json')
    for name,digest in inputs.items():
        assert prepare.sha(e.ROOT/name)==digest,'input modified: '+name
    for name in prepare.VENDOR:
        assert prepare.sha(e.LOCAL/'vendor'/Path(name).relative_to('research'))==inputs[name],name
    tracked=subprocess.check_output(['git','ls-files','--','research/gr_evalsets/local'],cwd=e.ROOT,text=True,
                                    env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'})
    assert not tracked,'local files are tracked'
    if args.seal:
        environment=dict(python=sys.version,platform=platform.platform(),numpy=np.__version__,scipy=scipy.__version__,
                         pillow=PIL_VERSION,compiler=subprocess.check_output(['cc','--version'],text=True).splitlines()[0])
        e.dump(e.LOCAL/'environment.json',environment)
    public_count=public_checks()
    numerical=numerical_checks()
    if args.seal:
        manifest(e.HERE,e.HERE/'SHA256SUMS')
        manifest(e.LOCAL,e.LOCAL/'SHA256SUMS',True)
    public_hash_count=check_manifest(e.HERE,e.HERE/'SHA256SUMS')
    local_hash_count=check_manifest(e.LOCAL,e.LOCAL/'SHA256SUMS',True)
    result=dict(passed=True,input_files_unchanged=len(inputs),original_manifest_files_verified=18,
                vendor_copies_verified=len(prepare.VENDOR),public_hashes_verified=public_hash_count,
                local_hashes_verified=local_hash_count,public_files_inspected=public_count,
                local_ignored=True,local_tracked_files=0,public_no_long_raw_byte_strings=True,
                numerical=numerical,credible_metering_anchor_available=False,
                writes_confined_to='research/gr_evalsets/',
                excluded_from_local_manifest=sorted(LOCAL_EXCLUDED))
    e.dump(e.LOCAL/'verification.json',result)
    print(json.dumps(e.jsonable(result),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
