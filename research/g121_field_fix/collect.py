"""Collect final-artifact results, communication counts and native epoch evidence."""
from pathlib import Path
from collections import Counter,defaultdict
import csv
import datetime
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,DAT,TREE,save,file_sha

UNITS=('50mm','28mm','mount')
PARSE_GAPS=[]

def read(path):
    if not path.exists():return None
    try:return json.loads(path.read_text())
    except json.JSONDecodeError as error:
        PARSE_GAPS.append(dict(path=str(path.relative_to(OUT)),error=str(error)))
        return dict(status='INCOMPLETE_PARTIAL_RECORD')

def binding(value):
    if not isinstance(value,dict):return None
    return value.get('dat_sha256') or value.get('dat') or value.get('artifacts',{}).get('dat')

def result(name,expected=None):
    path=OUT/name;x=read(path)
    if x is None:return dict(status='INCOMPLETE',path=name)
    bound=binding(x)
    if bound and bound!=file_sha(DAT):return dict(status='INCOMPLETE_ARTIFACT',path=name,sha256=bound)
    status=x.get('status','INCOMPLETE')
    if status=='RUNNING':status='INCOMPLETE'
    return dict(status=status,path=name,sha256=bound)

def visit(value,path,files,audits):
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ('file_mutations','zero_file_mutations') and isinstance(item,dict):
                files.append(dict(path=path,counts=item))
            elif key=='native_state_audits' and isinstance(item,list):
                audits.extend(dict(path=path,**row) for row in item)
            else:visit(item,path,files,audits)
    elif isinstance(value,list):
        for item in value:visit(item,path,files,audits)

def main():
    digest=file_sha(DAT);groups=[];files=[];audits=[];counts=[];epoch_rows=[];field_rows=[];reopens=[]
    for unit in UNITS:
        names=[('review_matrix','native/matrix-'+unit+'.json'),
               ('four_parameters','native/fn2-four-parameters-'+unit+'.json'),
               ('step_counts','native/fn2-step-counts-'+unit+'.json'),
               ('list_counts','native/list-counts-'+unit+'.json'),
               ('write_boundaries','native/write-boundaries-'+unit+'.json'),
               ('allocation_retry','native/allocation-retry-'+unit+'.json'),
               ('diagnostic','native/notice-details-'+unit+'.json'),
               ('merge_limit','native/bounded-moves-'+unit+'.json'),
               ('recovery_limits','native/recovery-limits-'+unit+'.json'),
               ('settings_retry','native/settings-retry-'+unit+'.json'),
               ('next_move_rebind','native/next-move-'+unit+'.json')]
        for group,name in names:groups.append(dict(unit=unit,group=group,**result(name)))
        remaining=read(OUT/('remaining-'+unit+'.json')) or {}
        steps=result('native/fn2-step-counts-'+unit+'.json')
        commands=[]
        for row in remaining.get('commands',[]):
            effective='PASS' if row['returncode']==0 else 'FAIL'
            if row['command'][:2]==['fn2_quality.py','measure'] and row['returncode']!=0:
                effective='PASS_RERUN' if steps['status']=='PASS' else 'INCOMPLETE_RERUN'
            commands.append(dict(**row,effective_status=effective))
        completed=sum(x['effective_status'] in ('PASS','PASS_RERUN') for x in commands)
        complete=len(commands)==remaining.get('total',24) and completed==len(commands)
        groups.append(dict(unit=unit,group='remaining_review',status='PASS' if complete else 'INCOMPLETE',
            completed=completed,total=remaining.get('total',24),commands=commands))
        matrix=read(OUT/'native'/('matrix-'+unit+'.json')) or {}
        list_counts=read(OUT/'native'/('list-counts-'+unit+'.json')) or read(OUT/'native'/('list-counts-progress-'+unit+'.json')) or {}
        if not matrix and binding(list_counts)==digest:
            for i,x in enumerate(list_counts.get('steps',[])):
                counts.append(dict(unit=unit,group='list',label='adjacent/'+str(i),before=x['before'].get('cursor'),after=x['after'].get('cursor'),
                    key=x.get('key'),RPC=x['rpc_calls'],W=x.get('W_attempts'),write_bytes=x.get('unit_write_bytes'),preview=x.get('refreshes')))
        if binding(matrix)==digest:
            reset=read(OUT/'field'/('121-'+unit+'-row_reset.json')) or {}
            row=dict(unit=unit,cold_RPC=matrix.get('cold',{}).get('state',{}).get('rpc'))
            if 'adj' in matrix:
                row.update(reopen_RPC=matrix['adj']['reopened']['rpc']-matrix['adj']['after']['rpc'],
                    reopen_W=matrix['adj']['reopened']['W']-matrix['adj']['after']['W'])
            if reset.get('status')=='PASS' and binding(reset)==digest:
                row.update(reset_reopen_RPC=reset['after']['rpc']-reset['selected']['rpc'],
                    reset_reopen_W=reset['after']['W']-reset['selected']['W'])
            reopens.append(row)
            def moves(x,trail=''):
                if isinstance(x,dict):
                    if 'rpc_calls' in x and 'before' in x and 'after' in x:
                        counts.append(dict(unit=unit,group='list',label=trail,
                            before=x['before'].get('cursor'),after=x['after'].get('cursor'),
                            key=x.get('key'),RPC=x['rpc_calls'],W=x.get('W_attempts'),
                            write_bytes=x.get('unit_write_bytes'),preview=x.get('refreshes')))
                    else:
                        for k,y in x.items():moves(y,trail+'/'+k)
                elif isinstance(x,list):
                    for i,y in enumerate(x):moves(y,trail+'/'+str(i))
            moves(matrix.get('fast_moves',[]),'fast_moves')
        measured=read(OUT/'native'/('fn2-step-counts-'+unit+'.json')) or {}
        if binding(measured)==digest and measured.get('status')=='PASS':
            for row in measured['steps']:
                counts.append(dict(unit=unit,group='panel',label=row['label'],before=row['before'],after=row['after'],
                    key=row['key'],RPC=row['RPC'],W=row['W'],write_bytes=row['write_bytes'],preview=row['preview']))
        for path in sorted((OUT/'field').glob('121-'+unit+'-*.json')):
            x=read(path)
            if binding(x)!=digest:continue
            snapshots={key:value for key,value in x.items() if isinstance(value,dict) and 'epochs' in value}
            epochs={key:value['epochs'] for key,value in snapshots.items()}
            status=x.get('status','INCOMPLETE')
            field_rows.append(dict(unit=unit,case=x.get('case'),status=status,path=str(path.relative_to(OUT)),
                failed_writes=x.get('failed_writes',[]),error=x.get('error'),
                states={key:dict(failed=value.get('adapter',{}).get('failed'),
                    rows=value.get('rows'),RPC=value.get('rpc'),W=value.get('W'),
                    stage=value.get('list',{}).get('stage'),reason=value.get('adapter',{}).get('reason'))
                    for key,value in snapshots.items()}))
            epoch_rows.append(dict(unit=unit,case=x.get('case'),status=status,epochs=epochs,
                changed=[i for i in range(12) if len({v[i] for v in epochs.values()})>1] if epochs else []))
    paths=list((OUT/'native').rglob('*.json'))+list((OUT/'field').glob('121-*.json'))
    gate=read(OUT/'machine-gates.json')
    if gate:paths.append(OUT/'machine-gates.json')
    for path in paths:
        x=read(path);bound=binding(x)
        if bound and bound!=digest:continue
        visit(x,str(path.relative_to(OUT)),files,audits)
    file_failures=[x for x in files if any(x['counts'].values())]
    audit_failures=[x for x in audits if x.get('host_writes') or x.get('getter_callback_present')]
    save('zero-file-write-audit.json',dict(status='PASS' if files and not file_failures and not audit_failures else 'FAIL',
        dat_sha256=digest,records=len(files),native_state_audits=len(audits),file_failures=file_failures,
        native_state_failures=audit_failures,scope='Observed engine sessions and final file dispatcher. No camera or card acceptance.'))
    save('epoch-sequences.json',dict(dat_sha256=digest,epochs=['boot','heap','link','unit','SD','IROM','view','settings','mode','segment','power','IO'],sequences=epoch_rows))
    save('field-sequences.json',dict(dat_sha256=digest,cases=field_rows))
    with (OUT/'communication-steps.tsv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['unit','group','label','before','after','key','RPC','W','write_bytes','preview'],delimiter='\t')
        writer.writeheader();writer.writerows(counts)
    reduced=defaultdict(list)
    for row in counts:reduced[(row['unit'],row['group'],row['label'] if row['group']=='panel' else 'all')].append(row['RPC'])
    ranges=[dict(unit=k[0],group=k[1],label=k[2],operations=len(v),RPC_min=min(v),RPC_max=max(v)) for k,v in sorted(reduced.items())]
    save('communication-summary.json',dict(dat_sha256=digest,ranges=ranges,steps=len(counts),
        scope='Actual modeled RPC calls. No camera timing measurement.'))
    save('reopen-counts.json',dict(dat_sha256=digest,units=reopens))
    save('collection-gaps.json',dict(status='INCOMPLETE' if PARSE_GAPS else 'PASS',records=PARSE_GAPS))
    all_statuses=[x['status'] for x in groups]+[x['status'] for x in field_rows]
    overall='FAIL' if any(s.startswith('FAIL') for s in all_statuses) else (
        'PASS' if all(s=='PASS' for s in all_statuses) and len(field_rows)==63 else 'INCOMPLETE')
    save('acceptance.json',dict(status=overall,
        time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),dat_sha256=digest,groups=groups,
        field_statuses=dict(Counter(x['status'] for x in field_rows)),field_cases=len(field_rows),
        file_write_status='PASS' if files and not file_failures else 'FAIL',
        camera_acceptance=False,physical_button_identity='INCOMPLETE',capture_completion='INCOMPLETE'))
    print('Collected final DAT',digest,'groups',len(groups),'field cases',len(field_rows),'communication rows',len(counts),flush=True)

if __name__=='__main__':main()
