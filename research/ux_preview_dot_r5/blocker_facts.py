"""Bind the fixed H07 close boundary to exact frozen source and machine bytes."""
from pathlib import Path
import json,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,save,load,sha,file_sha
words=load(ROOT/'research/review_g119b/neutral_terms.py','quality_blocker_terms')
loader=load(ROOT/'tools/native_harness/image_loader.py','quality_blocker_image')
resident=ROOT/'firmware/resident_v36'
body=loader.Image(ROOT/'firmware/package_v36_g119/SD_ROOT/ilaunch3','50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008')
elf=resident/'local/resident/build/resident.elf'
command=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
listing=subprocess.run([str(command),'-d',str(elf)],capture_output=True,text=True,check=True).stdout
(OUT/'native-static/resident.txt').write_text(words.replace(listing))
hooks=(resident/'resident/hooks.c').read_text()
assert 'else if(hook==7&&keep==0)(void)rv_ui_abort(r);' in hooks
assert 'if(hook==7&&(result==RV_CLOSE_AND_PASS||result==RV_FAULT||keep==0))skip=rv_close_07;' in hooks
routines=[]
for address,size,name in ((0x201c06f4,0xec,'layer_register'),(0x2030e8c4,0x60,'native_base_constructor'),(0x20060300,0x1a8,'ui_state_update_complete')):
 data=body.bytes_at(address,size);p=OUT/'native-static'/(name+'.bin');p.write_bytes(data)
 result=subprocess.run([str(command),'-D','-b','binary','-m','m32r','-EB','--adjust-vma='+hex(address),str(p)],capture_output=True,text=True,check=True)
 p.with_suffix('.txt').write_text(result.stdout);routines.append(dict(address=hex(address),bytes=size,sha256=sha(data),file=p.with_suffix('.txt').name))
records=[]
for unit in ('50mm','28mm','mount'):
 path=OUT/'native/cases'/('h07-native-finish-'+unit+'-native-base.json')
 x=json.loads(path.read_text());functions=[r['function'] for r in x['calls']]
 assert functions==['resident_close','native_layer','layer_transfer','layer_show','ui_service'],functions
 assert x['calls'][0]['flags']==3 and x['calls'][0]['kind']==2
 assert x['RPC']==0 and not any(x['file_mutations'].values())
 assert x['before']['list']['current_slot']==4 and x['before']['root']['state']==3
 records.append(dict(unit=unit,file=str(path.relative_to(OUT)),sha256=file_sha(path),boundary_reached='0x2005ff88',RPC=0,
  native_state_created_by='The official part-one constructor arm at 0x2030e8cc..0x2030e8e4 runs before the usual parent/list constructors. No UI field is assigned by the fixture.',
  remaining_flow=x['result'],acceptance='Boundary reachability only. Rendering later reaches an unavailable font/display model; full close acceptance is incomplete.'))
save('h07-close-boundary.json',dict(status='BLOCKED_FIXED_CLOSE_NO_YIELD_REQUIREMENT',body=body.sha256,resident_elf=file_sha(elf),resident_source=file_sha(resident/'resident/hooks.c'),
 record_scope='Real H07 key and fixed close instructions after an official base-layer registration arm. Device, display and RTOS boundaries remain modeled.',
 engine_H07_no_unit_communication=True,all_native_close_calls_no_yield=False,
 native_chain=['0x20052be8','0x201c092c','0x201d83b0','0x201d79f4','0x2005ff88','0x2005fdfc','0x20060300'],
 selection='With flags=3 and kind=2, closing part 2 selects show(part 1), which calls the UI task service before any graphics work.',
 close_contract='For keep=0, all four legal engine return values select the fixed close continuation. No ABI result cancels it.',
 limitation='The RTOS body can reschedule. A real camera reschedule or native menu change during this interval has not been observed here. The required universal no-yield proof is therefore not satisfied.',
 decision_needed='Decide the scope of the no-yield requirement or authorize a change to the fixed close continuation. No resident or native body change was made.',
 native_records=records,additional_routines=routines))
print('BOUNDARY CONFIRMED: fixed H07 close reaches the UI task service in all three unit fixtures; zero unit RPC; full no-yield requirement remains blocked.',flush=True)
