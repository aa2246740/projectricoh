"""Assert the delivered body against reviewer baselines and raw native evidence."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];R=HERE/'local/review'
def read(name):return json.loads((R/name).read_text())
def records(name):
 rows=read(name)
 assert all('error' not in x for x in rows),[(x['name'],x.get('error')) for x in rows]
 assert all('final' in x for x in rows),name
 for x in rows:assert not x.get('stub_hits',{}).get('image_mode_getter',0),x['name']
 return rows

def main():
 expected={x['name']:x for x in json.loads((ROOT/'research/review_v35_body/adversarial.json').read_text())}
 matrix={x['name']:x for x in records('adversarial.json')}
 assert set(matrix)==set(expected)
 for name in ('i','ii','iii','iv','v','vii','viii','28mm_retry','never_ready'):
  a,b=matrix[name]['final'],expected[name]['final']
  actual_steps=matrix[name]['steps'];old_steps=expected[name]['steps']
  assert len(actual_steps)==len(old_steps),name
  for current,old in zip(actual_steps,old_steps):
   assert current['action']==old['action'],name
   assert current['result'].get('ok',True)==old['result'].get('ok',True),(name,current['action'])
   for key in ('mode','deep_sha256'):
    assert current['after'][key]==old['after'][key],(name,current['action'],key)
   assert current['after']['ui']['rows']==old['after']['ui']['rows'],(name,current['action'],'rows')
  for key in ('mode','deep_sha256','deep_cells'):
   assert a[key]==b[key],(name,key,a[key],b[key])
  for key in ('state','flags'):assert a['root'][key]==b['root'][key],(name,key)
  for key in ('H07_native','H08_native'):
   assert a['native_visits'][key]==b['native_visits'][key],(name,key)
  assert a['diag_early']=='0x0',name
 assert matrix['v']['final']['deep_sha256']!=matrix['i']['final']['deep_sha256']
 assert matrix['vii']['nested']['before']['root']['inflight']==1
 assert matrix['vii']['nested']['result']['ok']
 ii=next(x for x in matrix['ii']['steps'] if x['action']=='scroll to 02')
 assert ii['result']['ok'] is False
 retry=matrix['28mm_retry'];assert retry['steps'][0]['after']['ui']['rows']==7 and retry['final']['ui']['rows']==8
 assert retry['steps'][0]['after']['root']['state']==0 and retry['steps'][0]['after']['root']['flags']==2
 for name in ('h08-retire-adversarial.json','h08-first-adversarial.json','scroll-both-adversarial.json'):
  x=records(name)[-1];f=x['final']
  assert f['mode']==1 and f['native_visits']['H08_native']==0,(name,f)
  assert f['root']['state']==6 and f['root']['flags']==163 and f['ui']['rows']==7,name
 fault=read('h08-retire-adversarial.json')[-1]
 assert fault['final']['deep_sha256']==matrix['i']['final']['deep_sha256']
 assert fault['final']['deep_sha256']==fault['steps'][2]['after']['deep_sha256']
 first=read('h08-first-adversarial.json')[-1];assert first['final']['deep_cells']==0
 gates=records('p2-adversarial.json');assert len(gates)==5
 for x in gates:
  assert x['final']['root']['state']==0 and x['final']['root']['flags']==2 and x['final']['ui']['rows']==7
  assert not x['files_opened'] and x['final']['rpc_writes']==0
 extra={x['name']:x for x in records('extra-adversarial.json')}
 n=extra['nested_h08_negative']['nested_H08']
 assert n['before']['root']['inflight']==1 and n['before']['ui']['rows']==8
 assert n['result']['ok'] and n['after']['mode']==1 and n['after']['native_visits']['H08_native']==0
 retired=extra['retired_native_move'];moves=[x for x in retired['steps'] if x['action']=='scroll down']
 assert [x['after']['mode'] for x in moves]==[10,3]
 assert retired['final']['mode']==3 and retired['final']['native_visits']['H08_native']==2
 assert all(x['before']['ui']['rows']==7 for x in moves)
 n=records('reachability-adversarial.json')[-1]['nested']
 assert n['hook']==6 and n['before']['root']['inflight']==1 and n['before']['ui']['rows']==8
 assert n['result']['ok'] and n['after']['native_visits']['H06_native']==0
 assert not n['settings_writes']
 own=records('ownership-adversarial.json')[-1];assert own['final']['mode']==1 and own['final']['native_visits']['H08_native']==0
 old=records('ownership-v35-adversarial.json')[-1];assert old['final']['mode']!=1 and old['final']['native_visits']['H08_native']>0
 h06=records('h06-fault-adversarial.json')[-1];assert h06['final']['mode']==1 and h06['final']['native_visits']['H06_native']==0
 menu=records('menu-native-adversarial.json')[-1]
 assert menu['blocked']['callbacks'][0]['result']['pc']=='0x2005f4c0'
 assert menu['blocked']['callbacks'][0]['result']['detail']=='unmapped memory 0x8/4'
 deep=read('deep-rows-comparison.json');assert [x['slot'] for x in deep]==[1,2,4]
 assert all(x['all_bytes_equal'] and x['mode']==1 and x['t']==x['expected_t'] for x in deep)
 inherited=read('inherited.json');assert len(inherited)==20
 assert not any(x['violations'] or x.get('error') for x in inherited)
 for group in ('matrix','faults','guards','supplement'):
  status=read('executions-'+group+'.json')
  expected_count={'matrix':1,'faults':4,'guards':4,'supplement':2}[group]
  assert len(status)==expected_count and all(x['returncode']==0 for x in status),group
 binding=read('fixture-binding.json');assert binding['payload_unchanged'] and not binding['emitted_dat']
 abi=read('abi-and-linker.json');assert all(x['identical'] for x in abi.values())
 protect=read('protected-after.json');assert protect['all_unchanged'] and not protect['changed']
 host=(ROOT/'firmware/resident_v36/local/host.stdout.log').read_text();assert 'PASS_HOST checks=157249 ASan+UBSan=1' in host
 verify=(HERE/'local/verify.stdout.log').read_text();assert 'VERIFICATION_PASS' in verify and 'rejections=14/14' in verify
 assert 'PASS python backend conformance' in (R/'conformance.stdout.log').read_text()
 table=[]
 for name in ('i','ii','iii','iv','v','vii','viii'):
  x=matrix[name];f=x['final'];table.append(dict(sequence='viii-a' if name=='viii' else name,mode=f['mode'],deep_sha256=f['deep_sha256'],native=f['native_visits'],root=f['root']['state'],flags=hex(f['root']['flags']),diag=f['diag_early'],verdict='PASS'))
 for name,x in (('vi',menu),('viii-b',fault),('first_fault',first)):
  f=x['final'];table.append(dict(sequence=name,mode=f['mode'],deep_sha256=f['deep_sha256'],native=f['native_visits'],root=f['root']['state'],flags=hex(f['root']['flags']),diag=f['diag_early'],verdict='BLOCKED_EXISTING_MODEL' if name=='vi' else 'PASS'))
 result=dict(status='HOST_NATIVE_P0_FIXED_REBIND_PENDING',scenario_table=table,matrix_matches_reviewer=True,p0_mode=1,p0_H08_native=0,p2_gate_cases=5,inherited_cases=20,menu_blocked_existing_model=True,hardware_executed=False,container_emitted=False)
 (R/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');(R/'scenario-table.json').write_text(json.dumps(table,indent=2)+'\n')
 print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
