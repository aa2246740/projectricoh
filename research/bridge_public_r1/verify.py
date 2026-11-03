"""Check real inputs, independent decode, color-family splits and final artifacts."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
from common import np
import ast
import json
import subprocess


def main():
    results=[]
    def check(label,value):
        assert value,label
        results.append(dict(check=label,passed=True))
    for p in sorted(c.HERE.glob('*.py')):ast.parse(p.read_text(),filename=str(p))
    check('all delivered Python source parses',True)
    check('local evidence is ignored by Git',subprocess.run(
        ['git','check-ignore','-q',str(c.LOCAL/'summary.json')],cwd=c.ROOT).returncode==0)
    check('checksum manifest is ignored by Git',subprocess.run(
        ['git','check-ignore','-q',str(c.HERE/'SHA256SUMS')],cwd=c.ROOT).returncode==0)
    sources=c.read(c.LOCAL/'sources.json');listed=set()
    for row in sources:
        if not row.get('file'):continue
        path=c.ROOT/row['file'];check('source hash '+row['label'],c.sha(path)==row['sha256'])
        if path.is_relative_to(c.DOWNLOADS):listed.add(path)
    actual={p for p in c.DOWNLOADS.rglob('*') if p.is_file() and p.name!='receipt.json'}
    check('every downloaded response is listed in sources.json',actual==listed)
    check('only read-only GETs acquired reference sources',all(v['method']=='GET' for v in sources))
    public=c.arrays(c.LOCAL/'public_data.npz');s=c.arrays(c.LOCAL/'sensitivities.npz')
    check('public spectral dimensions',public['camera_sensitivities'].shape==(28,3,33)
          and public['natural'].shape==(219,33) and public['munsell'].shape==(1269,33))
    from estimate import spd
    for camera in ('gxr','griv'):
        check(camera+' spectra are nonnegative and D65 normalized',
            (s[camera]>=0).all() and np.max(abs(s[camera]@spd('D65')-1))<1e-10)
        hold=c.read(c.LOCAL/f'chart_holdout_{camera}.json')
        ids=[v for fold in hold['folds'] for v in fold['held_ids']]
        patches=c.read(c.LOCAL/('patches.json' if camera=='gxr' else 'patches_griv.json'))
        override=c.LOCAL/f'chart_override_{camera}.json'
        if override.exists():patches=c.read(c.read(override)['patch_file'])
        expected=[v['index']+1 for v in patches if v['chart']=='ColorChecker' and v['usable'] and v['index']<18]
        check(camera+' holdout covers each usable colored patch exactly once',sorted(ids)==sorted(expected) and len(ids)==len(set(ids)))
    independent=c.read(c.LOCAL/'independent_raw_decode.json')
    check('new GR IV independently decoded pixels match exactly',independent['mismatches']==0
          and independent['samples']==6304*4224
          and independent['input_sha256']=='2e438c7e9945591ed2a897a6a4df40da23adf0cb45b89b1a7a1ab7f2d6a967c4')
    check('GXR independent 12-bit packing checks',all(r['mismatches']==0 for r in c.read(c.LOCAL/'gxr_packing_check.json')))
    for row in c.read(c.LOCAL/'bridge_behavior_checks.json'):
        check(row['kind']+' preserves neutral and exposure scaling',row['neutral_error']<1e-12 and row['exposure_homogeneity_error']<1e-12)
    sim=c.read(c.LOCAL/'bridge_simulation.json')
    check('GR IV chart is used in final bridge',sim['target_camera_has_chart_measurement'])
    check('simulated metamers have identical GXR response',sim['conditional_metamer_examples']['same_gxr_max_abs_difference']<1e-12)
    propagation=c.read(c.LOCAL/'ceiling_propagation.json')
    for slot in ('01','02'):
        case=c.arrays(c.LOCAL/f'propagation_{slot}.npz')
        row=next(r for r in propagation['results'] if r['slot']==slot and r['scheme']=='patch' and r['subset']=='all_style_supported')
        frozen=c.arrays(f'research/gr4_lut_ceiling/local/lut/body_{slot}_patch_pixel33.npz')
        mask=case['model_support'].all(axis=0)&case['original_support']
        membership=np.zeros(len(mask),bool);membership[frozen['index']]=True;mask&=membership
        pred=np.zeros_like(case['current_target']);pred[frozen['index']]=c.lab(frozen['prediction'])
        observed=[]
        for target in case['modeled_targets']:
            num=np.median(c.cm.delta_e00(pred[mask],target[mask]))
            den=np.median(c.cm.delta_e00(case['baseline'][mask],target[mask]));observed.append(1-num/den)
        recorded=[v['score']['similarity_median'] for v in row['scenarios']]
        check(slot+' metric independently recomputed from delivered per-point targets',np.max(abs(np.array(observed)-recorded))<1e-12)
    summary=c.read(c.LOCAL/'summary.json')
    check('unavoidable physical gap share is not invented',summary['actual_01_02_unavoidable_gap_share'] is None)
    check('prior-only intermediate is distinct from current results',(c.LOCAL/'prior_only_r0/sensitivity_fit.json').exists())
    check('both requested Chinese reports delivered',(c.HERE/'REPORT.md').stat().st_size>1000 and (c.LOCAL/'CEILING_PRIVATE.md').stat().st_size>1000)
    check('decisions.tsv excluded from inputs',not any(Path(k).name=='decisions.tsv' for k in c._inputs))
    count=c.verify();results.append(dict(check='frozen protected inputs hash-verified',passed=True,count=count))
    c.dump('verification.json',dict(all_passed=True,checks=results,
         scope='host-only files and numerical behavior; not live camera acceptance',
         no_build_card_camera_or_USB=True,network_used_only_for_public_readonly_GET=True))
    print('verification passed',len(results),'checks;',count,'frozen protected files')


if __name__=='__main__':main()
