"""Persist the exact A/B/C inventory and every unresolved compiled outcome."""
from pathlib import Path
import collections,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,save,file_sha
import codegen as c
inventory=json.loads((OUT/'codegen-inventory.json').read_text())
identity=json.loads((OUT/'implementation-candidate/identity.json').read_text())
old_previous=json.loads((OUT/'previous_delta/rv-coverage-current.json').read_text())
proofs={};unresolved=[];obligations=[]
for path in sorted((OUT/'pairs').glob('*-results.json')):
 x=json.loads(path.read_text());assert x['status']=='PASS' and not x['failures']
 assert x['random']>=10000 and x['boundary']>=64
 for g in (119,120):
  assert x['artifacts'][str(g)]['elf']==identity[str(g)]['elf']
  assert x['artifacts'][str(g)]['dat']==identity[str(g)]['dat']
  fn=x['names'][g-119];atoms=c.atoms(g,fn)[0]
  for branch in x['coverage'][str(g)]['uncovered']:
   pc=int(branch['pc'],16);index=next(i for i,a in enumerate(atoms) if a['pc']==pc)
   unresolved.append(dict(function=fn,generation=g,pc=branch['pc'],taken=branch['taken'],status='OPEN_DISPOSITION',evidence=str(path.relative_to(OUT)),context=[dict(pc=hex(a['pc']),asm=a['asm']) for a in atoms[max(0,index-3):index+3]]))
 proofs[x['function']]=dict(file=str(path.relative_to(OUT)),sha256=file_sha(path),random=x['random'],boundary=x['boundary'],observed_body_comparison='PASS',branch_disposition='INCOMPLETE')
by_new={'apply_impl.constprop.0':'apply_impl','eng_current.constprop.0':'eng_current'}
literals={}
for name in ('accept_preview','start_view','view_owned'):
 p=OUT/'literal'/(name+'-results.json');x=json.loads(p.read_text());assert x['status']=='PASS'
 literals[name]=dict(file=str(p.relative_to(OUT)),sha256=file_sha(p),random=x['random'],boundary=x['boundary'],status='PASS_LITERAL_EXPECTATIONS')
for row in inventory:
 name=row['name'];canonical=by_new.get(name,name);evidence=[]
 if row.get('local_A'):
  method='A';status='LOCAL_A_PASS_DEPENDENCIES_PENDING';evidence=['codegen-inventory.json']
 elif canonical in proofs:
  method='B+C' if name not in ('eng_current','eng_current.constprop.0','apply_impl','apply_impl.constprop.0') else 'B'
  status='BODY_COMPARISON_PASS_BRANCH_DISPOSITIONS_OPEN';evidence=[proofs[canonical]['file']]
 elif name in literals:
  method='C';status='LITERAL_CHECK_PASS';evidence=[literals[name]['file']]
 elif name in ('eng_apply','recover_confirmed','eng_preview_saved'):
  method='C+B';status='SOURCE_CHANGE_RECORDED_CALLER_PROOF_OPEN';evidence=['source.patch','pairs/apply-body-results.json','pairs/preview_cached-results.json']
 else:method='C+B';status='OPEN';evidence=['source.patch']
 if name=='rv_call':status='LOCAL_A_PASS_PREVIOUS_DELTA_OPEN';evidence.append('previous_delta/rv-coverage-current.json')
 obligations.append(dict(function=name,change=row['status'],method=method,status=status,local_A=bool(row.get('local_A')),dependencies=row.get('dependencies',[]),evidence=evidence))
names={x['name'] for x in inventory};assembly={x['name'] for x in json.loads((OUT/'assembly-leaves.json').read_text())}
unknown=sorted({n for x in inventory for n in x.get('dependencies',[]) if n not in names|assembly})
assert not unknown,unknown
save('codegen-open-outcomes.json',dict(status='INCOMPLETE',outcomes=unresolved,count=len(unresolved),inherited_count=old_previous['open_outcomes'],inherited_file='previous_delta/rv-coverage-current.json'))
save('codegen-closure.json',dict(status='INCOMPLETE',reason='Work stopped at the fixed H07 close boundary; no full per-PC disposition or recursive closure is claimed.',artifacts=identity,obligations=obligations,local_A=sum(x['local_A'] for x in obligations),B=proofs,literal=literals,B_pairs=sum(x['random']+x['boundary'] for x in proofs.values()),unresolved_dependency_names=unknown,open_current_outcomes=len(unresolved),open_previous_outcomes=old_previous['open_outcomes']))
(OUT/'codegen-closure.tsv').write_text('function\tchange\tmethod\tstatus\tevidence\n'+''.join('\t'.join((x['function'],x['change'],x['method'],x['status'],','.join(x['evidence'])))+'\n' for x in obligations))
print('INCOMPLETE compiled closure:',len(obligations),'symbols;',sum(x['local_A'] for x in obligations),'local A;',len(proofs),'B groups;',len(unresolved),'current outcomes;',old_previous['open_outcomes'],'previous outcomes',flush=True)
