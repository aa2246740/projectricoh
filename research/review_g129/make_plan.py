"""Expand the exact regression table and prioritize missing acceptance."""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent

def main():
    previous=json.loads((ROOT/'research/review_g127/plan.json').read_text())['jobs']
    indexed={job['name']:job for job in previous}
    jobs=[]
    def retained(name,arguments,kind='focus'):
        jobs.append({'name':name,'kind':kind,'args':['research/review_g129/retained.py','--job',name,'--crc-mode','host',*arguments]})
    retained('focus-cold-mount',['research/review_g126/cold_reentry.py','--generation','129','--unit','mount'])
    retained('focus-product-mount',['--postcheck','research/review_g129/product_post.py','research/review_g126/ownership_settings.py','--generation','129','--unit','mount'])
    retained('focus-cold-28mm',['research/review_g126/cold_reentry.py','--generation','129','--unit','28mm'])
    retained('focus-product-50mm',['--postcheck','research/review_g129/product_post.py','research/review_g126/ownership_settings.py','--generation','129','--unit','50mm'])
    jobs.append({'name':'integrated-host','kind':'knobs','args':['research/review_g129/artifact.py','host']})
    for unit in range(3):jobs.append({'name':f'integrated-target-{unit}','kind':'knobs','args':['research/review_g129/artifact.py','target','--unit',str(unit)]})
    for unit in ('50mm','28mm','mount'):
        retained('history123-'+unit,['research/review_g123/run_cases.py','suite','--generation','129','--unit',unit],'history123')
        retained('settings_cases-'+unit,['research/review_g126/settings_cases.py','--unit',unit],'settings_cases')
        retained('history122-'+unit,['--reference-expectations','research/review_g122/run_cases.py','suite','--generation','121','--unit',unit],'history122')
    rows=[]
    for line in (ROOT/'research/review_g127/REGRESSIONS.md').read_text().splitlines():
        match=re.match(r'\| (124|126) \| (50mm|28mm|mount) \| ([a-z-]+) \|',line)
        if not match:continue
        family,unit,group=match.groups();name=f'group{family}-{unit}-{group}'
        if name in indexed:arguments=indexed[name]['args']
        else:
            file={'safety':'safety_cases.py','cutpoints':'lock_cutpoints.py','project':'project_boundary.py','labels':'label_acceptance.py','half':'official_half.py'}[group]
            arguments=[f'research/review_g{family}/{file}']
            if group=='cutpoints':arguments+=['--irq-enabled']
            if group=='half':arguments+=['--hook-trace']
            arguments+=['--unit',unit]
        retained(name,arguments,'regression')
        rows.append({'name':name,'family':int(family),'unit':unit,'group':group})
    assert len(rows)==81 and len({r['name'] for r in rows})==81
    value={'workers':3,'timeout_seconds':4200,'deadline_utc':'2026-10-29T03:14:00+00:00','jobs':jobs,'matrix':rows}
    (WORK/'plan.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({'name':'regression_plan','returncode':0,'groups':len(rows),'jobs':len(jobs)}))

if __name__=='__main__':main()
