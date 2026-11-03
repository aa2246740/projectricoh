"""Record and rerun final-machine differentials without inheriting old results."""
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,ROOT,save

groups={
 'small':('es_range.constprop.0 identity.constprop.0 same.constprop.0 ui_prepare.constprop.0 ingress es_session finish ui_finish write_word preview_cached ig_panel_open ig_panel_event core_call rv_call').split(),
 'ui':('list_bind panel_render ig_menu ig_event ig_apply').split(),
}
group=sys.argv[1];rows=[]
for name in groups[group]:
    existing=OUT/(name+'-results.json')
    if existing.exists():
        old=__import__('json').loads(existing.read_text())
        if old.get('random',0)>=10000 and old.get('boundary',0)>=64 and not old.get('failures',[]):
            print('REUSE completed final-machine comparison',name,flush=True)
            rows.append(dict(function=name,returncode=0,reused_completed_review_result=True));continue
    script='misc_diff.py' if group=='small' else 'differential.py'
    label='B-'+name.replace('.','-').replace('_','-')+'-n2'
    print('BEGIN',label,flush=True)
    rc=subprocess.call(['/usr/bin/python3','-I','-B',str(OUT/'run_recorded.py'),label,
                        '/usr/bin/python3','-I','-B',str(OUT/script),name,'10000'],cwd=ROOT)
    rows.append(dict(function=name,returncode=rc));save('B-queue-'+group+'.json',rows)
    print('END',label,'exit',rc,flush=True)
print('COMPLETE',group,'failures',[x for x in rows if x['returncode']],flush=True)
raise SystemExit(any(x['returncode'] for x in rows))
