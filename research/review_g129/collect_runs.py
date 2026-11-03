"""Collect completed manual commands and retain the selected retry names."""
from pathlib import Path
import json

WORK=Path(__file__).resolve().parent

def main():
    plan=json.loads((WORK/'plan.json').read_text());scheduled={job['name'] for job in plan['jobs']}
    runs=[]
    for path in sorted((WORK/'local').glob('*/*/result.json')):
        folder=path.parent.parent;data=json.loads(path.read_text());name=folder.name
        if data.get('name')!=name or name in scheduled:continue
        state_file=path.parent/'session-field-counts.json';identity=None
        if state_file.exists():identity=json.loads(state_file.read_text()).get('candidate_hash_match_count')
        seconds=data.get('seconds')
        if seconds is None:seconds=round(path.stat().st_mtime-getattr(folder.stat(),'st_birthtime',folder.stat().st_ctime),3)
        runs.append({'name':name,'kind':'manual','state':'FINISHED','returncode':data.get('returncode'),
                     'seconds':seconds,'duration_scope':'wrapper_elapsed' if 'seconds' in data else 'folder_creation_to_result_write',
                     'dat_sha256':data.get('dat_sha256'),'runtime_candidate_hash_match_count':identity,
                     'result':str(path.relative_to(WORK.parents[1]))})
    (WORK/'manual-results.json').write_text(json.dumps(runs,indent=2)+'\n')
    aliases={f'settings_cases-{unit}':f'settings-r6-{unit}' for unit in ('50mm','28mm','mount')}
    (WORK/'retry-map.json').write_text(json.dumps(aliases,indent=2)+'\n')
    print(json.dumps({'name':'manual_result_collection','returncode':0,'completed':len(runs)}))

if __name__=='__main__':main()
