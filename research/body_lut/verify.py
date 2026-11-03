"""Read-only final verification, including actual input hashes and grouped-CV arithmetic."""
import ast
import argparse
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,HERE,LOCAL,guard,sha,tree_state
from seal import paths
import numpy as np


def manifest(base,public=False):
    lines=(base/'SHA256SUMS').read_text().splitlines()
    expected={}
    for line in lines:
        if not line or line.startswith('#'):
            continue
        m=re.fullmatch(r'([0-9a-f]{64})  (.+)',line)
        assert m, line
        rel=m[2];p=(base/rel).resolve()
        assert p.is_relative_to(base) and p!=base/'SHA256SUMS' and rel not in expected
        assert p.is_file() and sha(p)==m[1],f'checksum mismatch: {rel}'
        expected[rel]=m[1]
    actual={str(p.relative_to(base)) for p in paths(base,public)}
    assert actual==set(expected),{'missing':sorted(actual-set(expected)),
        'stale':sorted(set(expected)-actual)}
    return len(expected)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--strict-workspace',action='store_true',
        help='Fail also on unrelated outside-tree changes; never replace the original baseline.')
    args=parser.parse_args()
    guard()
    public_n=manifest(HERE,True);local_n=manifest(LOCAL)
    public=paths(HERE,True)
    for p in public:
        assert p.name=='.gitignore' or p.suffix in ('.py','.md'),p
        text=p.read_text()
        assert not re.search(r'[0-9a-fA-F]{96,}',text),f'long raw hex: {p}'
        assert not re.search(r'(?:\\x[0-9a-fA-F]{2}){48,}',text),f'escaped raw byte string: {p}'
        assert not re.search(r'(?:\b[0-9a-fA-F]{2}[ \t]+){48,}',text),f'raw byte list: {p}'
        if p.suffix=='.py':
            ast.parse(text,filename=str(p))
    assert (HERE/'.gitignore').read_text()=='local/\n'
    check=subprocess.check_output(['git','check-ignore','-v','research/body_lut/local/x'],cwd=ROOT,text=True)
    assert 'research/body_lut/.gitignore:1:local/' in check
    inputs=json.loads((LOCAL/'inputs.json').read_text())
    for rel,h in inputs.items():
        p=(ROOT/rel).resolve()
        assert p.is_relative_to(ROOT) and not p.is_relative_to(HERE)
        assert p.is_file() and sha(p)==h,f'input changed: {rel}'
    assert sha(ROOT/'artifacts/firmware/gxr-1.51/ilaunch3')=='da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7'
    before=json.loads((LOCAL/'tree_before.json').read_text());after=tree_state()
    changed=sorted(k for k in set(before)|set(after) if before.get(k)!=after.get(k))
    pre=json.loads((LOCAL/'preflight.json').read_text())
    status=subprocess.check_output(['git','status','--porcelain=v1','-uall'],cwd=ROOT,text=True)
    strip=lambda s:sorted(line for line in s.splitlines() if not line[3:].startswith('research/body_lut/'))
    git_before=set(strip(pre['git_status']));git_after=set(strip(status))
    git_delta={'added':sorted(git_after-git_before),'removed':sorted(git_before-git_after)}
    if args.strict_workspace:
        assert not changed and not any(git_delta.values()),{'outside_body_lut_changed':changed,'git_delta':git_delta}
    # Exercise the real table runner against literal identity and packed 4:2:2 expectations.
    from simulate import table_apply,apply422,fit,omitted,predict
    grid=np.stack(np.meshgrid(*([np.linspace(0,255,17)]*3),indexing='ij'),axis=-1)
    rng=np.random.default_rng(20261021)
    codes=rng.integers(0,256,(2048,3))
    assert np.array_equal(table_apply(grid,codes,True,True),codes)
    pair=np.array([[[255,0,0],[0,0,255]],[[0,0,0],[255,255,255]]])
    expected=np.array([[[76,170,181],[29,170,181]],[[0,128,128],[255,128,128]]])
    assert np.array_equal(apply422(grid,pair),expected)
    ds=json.loads((LOCAL/'dataset.json').read_text());rr=ds['rows']
    x=np.asarray([r['ycc'] for r in rr]);groups=np.array([r['group'] for r in rr])
    y=np.array([[r['targets'][s] for s in ('01','02','05','06')] for r in rr]).reshape(len(rr),12)
    ii=np.flatnonzero(groups==groups[0]);keep=np.setdiff1d(np.arange(len(x)),ii)
    aa=omitted(fit(x,y,24,.01),ii);bb=fit(x[keep],y[keep],24,.01)
    deletion=float(np.max(np.abs(predict(aa,x[ii])-predict(bb,x[ii]))))
    altered=y.copy();altered[ii]+=71
    perturb=float(np.max(np.abs(predict(omitted(fit(x,altered,24,.01),ii),x[ii])-predict(aa,x[ii]))))
    assert deletion<1e-8 and perturb<1e-8,(deletion,perturb)
    nr=json.loads((LOCAL/'nested_results.json').read_text())
    ar=json.loads((LOCAL/'nested422_results.json').read_text())
    # Load only the frozen color math definitions; no target constructor or source CLI runs.
    src=ROOT/'research/closed_loop/local/vendor/research/color_table_fit/fit_sectors.py'
    spec=importlib.util.spec_from_file_location('body_lut_verify_colour',src)
    fs=importlib.util.module_from_spec(spec);spec.loader.exec_module(fs)
    counts={}
    for mode,folds in nr['folds'].items():
        seen=[]
        for fold in folds:
            test=np.array(fold['test'],int);seen.extend(test.tolist())
            if mode in ('patch_loo','hue_30deg'):
                assert set(test)==set(np.flatnonzero(np.isin(groups,groups[test])))
            else:
                assert all(rr[i]['domain']=='physical' for i in test)
        assert len(seen)==len(set(seen))
        counts[mode]=len(seen)
        with np.load(LOCAL/f'nested422_predictions_{mode}.npz') as z:
            mask=z['mask'];t=z['target'];base=z['baseline']
            for n in (9,17,33):
                rgb=z[f'n{n}_rgb']
                for j,s in enumerate(('01','02','05','06')):
                    e=fs.delta_e00(fs.lab_from_codes(rgb[mask,j]),t[mask,j])
                    record=ar['scores'][mode][f'n{n}'][s]
                    assert abs(float(np.median(e))-record['median'])<1e-10
                    assert abs(float(np.percentile(e,90))-record['p90'])<1e-10
                    assert abs((1-float(np.median(e))/float(np.median(base[mask,j])))-record['similarity'])<1e-10
                    for k in (1,2,3):
                        assert float(np.mean(e<k))==record[f'under_{k}']
    assert counts=={'patch_loo':668,'hue_30deg':668,'screen_to_physical':48}
    # Imports and verification must not change a sealed artifact.
    assert public_n==manifest(HERE,True) and local_n==manifest(LOCAL)
    print(json.dumps({'result':'PASS_WITH_WORKSPACE_CHANGES' if changed or any(git_delta.values()) else 'PASS',
        'artifact_checksums_and_actual_inputs':'PASS','public_files':public_n,'local_files':local_n,
        'input_hashes_unchanged':len(inputs),'outside_tree_baseline_entries':len(before),
        'outside_tree_changes':changed,'outside_changes_not_attributed_by_this_verifier':True,
        'ignore_rule':check.strip(),'outside_git_state_unchanged':not any(git_delta.values()),
        'outside_git_delta':git_delta,
        'identity_and_literal422':'PASS','deletion_vs_refit_max_code_error':deletion,
        'heldout_target_perturbation_max_code_error':perturb,'CV_observations':counts,
        'checksum_bases':['research/body_lut/','research/body_lut/local/']},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
