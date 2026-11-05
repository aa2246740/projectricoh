"""Summarize frozen forward evaluations, with explicit target-convention differences."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from r2_common import C, PLANNED, decision
import statistics


def main():
    while True:
        try:
            C.admit('r2-summary')
            break
        except SystemExit as e:
            if e.code!=75:raise
            C.time.sleep(10)
    styles=C.read(C.LOCAL/'styles.json')
    results={r['name']:C.read(C.LOCAL/'results'/r['id']/'result.json') for r in styles}
    table=[]
    for name,position,slot in PLANNED:
        r=results[name];p=r['results'][position]
        source_delta=p['source_target_today']['similarity_percent']-p['source_holdout']['similarity_percent']
        table.append(dict(name=name,placement=position,slot=slot,
            original_holdout=p['source_holdout']['similarity_percent'],
            comparable_scene_holdout=p['same_scene_holdout']['similarity_percent'],
            real55=p['scores']['all55']['similarity_percent'],
            lunch44=p['scores']['lunch44']['similarity_percent'],morning11=p['scores']['morning11']['similarity_percent'],
            strict96=p['scores']['strict96']['similarity_percent'],r1held=p['scores']['r1held']['similarity_percent'],
            target_de00=p['scores']['all55']['de00'],change_pp=p['change_pp'],
            original_convention_change_pp=source_delta,
            full_minus_Look_pp=r['full_minus_Look_pp'],
            target_convention_changed=r['source_target_uses_04'],drop_over_10=p['drop_more_than_10pp'],
            record_sha256=p['record_sha256']))
    planned_change=statistics.mean(r['change_pp'] for r in table)
    original_change=statistics.mean(r['original_convention_change_pp'] for r in table)
    immutable_scene=[r for r in table if not r['target_convention_changed']]
    mean_unchanged=statistics.mean(r['change_pp'] for r in immutable_scene)
    primary_safe=[];robust_safe=[];conditional=[]
    for name,r in results.items():
        gap=r['full_minus_Look_pp']
        if gap['all55']<=2:
            primary_safe.append(name)
            if gap['strict96']<=2 and gap['r1held']<=2:
                robust_safe.append(name)
            else:conditional.append(name)
    C.dump('summary.json',dict(planned_count=len(table),evaluated_styles=len(styles),planned_table=table,
        mean_change_pp=planned_change,mean_unchanged_target_change_pp=mean_unchanged,
        mean_original_convention_change_pp=original_change,
        drops_over_10=[r['name'] for r in table if r['drop_over_10']],
        primary_Look_safe=primary_safe,sampling_robust_Look_safe=robust_safe,sampling_sensitive_Look_safe=conditional,
        all_results=results,created_utc=C.utc(),
        comparison_rule='Equal weight per planned style; every delta uses the same scene-light goal on old and new scenes. Original source holdout numbers are separate columns.',
        no_fitting_or_tuning=True))
    decision('summary','把目标改口径与新场景变化分别列出','三种数字风格的旧表含04后处理，不能把目标更换当性能退化',
             'local/r2/summary.json',f'{len(table)} planned, mean {planned_change:+.3f} pp')
    print('MEAN',planned_change,'UNCHANGED TARGET MEAN',mean_unchanged,'ORIGINAL-CONVENTION MEAN',original_change,flush=True)
    for r in table:
        print(r['name'],r['placement'],'original/comparable/new/delta',round(r['original_holdout'],2),
            round(r['comparable_scene_holdout'],2),round(r['real55'],2),round(r['change_pp'],2),
            'strict/held',round(r['strict96'],2),round(r['r1held'],2),'Look loss',
            {k:round(r['full_minus_Look_pp'][k],2) for k in ('all55','strict96','r1held')},flush=True)
    k=results['Kodachrome25']
    for key,old in k['old_g157_k25_actual_regions'].items():
        new=k['results']['full']['k25_regions'][key]
        print('K25 REGION',key,'DE',round(old['de00']['median'],3),round(new['de00']['median'],3),
            'L',round(old['actual_minus_target_Lab_median'][0],3),round(new['actual_minus_target_Lab_median'][0],3),
            'similarity',round(old['similarity_percent'],2),round(new['similarity_percent'],2),flush=True)
    print('LOOK SAFE',primary_safe,'ROBUST',robust_safe,'CONDITIONAL',conditional,flush=True)


if __name__=='__main__':main()
