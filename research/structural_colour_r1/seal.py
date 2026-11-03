"""Verify frozen inputs, evidence identity and study completeness, then remove owned scratch."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime as r
from static import Image
import csv
import hashlib
import re
import time

started=time.monotonic()
checks=[]
def check(label,condition,detail=None):
    checks.append(dict(check=label,passed=bool(condition),detail=detail))
    if not condition:
        r.dump(r.LOCAL/'verification-failure.json',dict(checks=checks))
        raise AssertionError((label,detail))

official=r.json.loads((r.LOCAL/'official.json').read_text())
check('archive SHA256',r.sha(official['archive'])==official['sha256'])
check('29 archive members',len(official['members'])==29)
check('objdump SHA256',r.sha(official['objdump'])==official['objdump_sha256'])
protected=r.json.loads((r.LOCAL/'protected_before.json').read_text())
changed=[key for key,value in protected.items() if not (r.ROOT/key).is_file() or r.sha(r.ROOT/key)!=value]
check('protected input contents unchanged',not changed,dict(count=len(protected),changed=changed))

source_hashes={}
for path in list(r.LOCAL.glob('inputs_*.json'))+list(r.LOCAL.glob('input_hashes_*.json')):
    for key,value in r.json.loads(path.read_text()).items():
        if key in source_hashes:
            check('same source hash across run receipts: '+key,source_hashes[key]==value)
        source_hashes[key]=value
changed=[key for key,value in source_hashes.items() if not (r.ROOT/key).is_file() or r.sha(r.ROOT/key)!=value]
check('read source contents unchanged',not changed,dict(count=len(source_hashes),changed=changed))

copied=r.json.loads((r.LOCAL/'model-copy-manifest.json').read_text())
for item in copied['files']:
    check('model source: '+item['source'],r.sha(r.ROOT/item['source'])==item['source_sha256'])
    check('model copy: '+item['copy'],r.sha(r.HERE/item['copy'])==item['copy_sha256'])
    if 'path_only_replacements' in item:
        raw=(r.ROOT/item['source']).read_text()
        for a,b in item['path_only_replacements'].items():raw=raw.replace(a,b)
        check('runtime has only recorded path adaptations',raw==(r.HERE/item['copy']).read_text())
    else:
        check('copy is byte-identical: '+item['copy'],item['source_sha256']==item['copy_sha256'])

images={}
window_count=0
for path in sorted((r.LOCAL/'disasm').glob('*.json')):
    meta=r.json.loads(path.read_text())
    name=meta['image']
    if name not in images:images[name]=Image(name)
    im=images[name]
    a,b=int(meta['start'],0),int(meta['end'],0)
    expected=im.read(a,b-a)
    check('window source image: '+path.stem,im.digest==meta['image_sha256'])
    check('window mapping: '+path.stem,im.offset(a)==int(meta['file_offset'],0))
    check('window bytes: '+path.stem,path.with_suffix('.bin').read_bytes()==expected)
    check('window digest: '+path.stem,hashlib.sha256(expected).hexdigest()==meta['raw_sha256'])
    check('disassembly digest: '+path.stem,r.sha(path.with_suffix('.asm'))==meta['disassembly_sha256'])
    window_count+=1

indices={name:r.json.loads((r.LOCAL/(name+'-index.json')).read_text())for name in ('ilaunch3','jlaunch3')}
census_specs=r.json.loads((r.LOCAL/'census-specs.json').read_text())
census={}
for name,data in indices.items():
    chosen={}
    for spec in census_specs[name]['entries']:
        label,value=spec['label'],int(spec['address'],0)
        matches=[c for c in data['calls'] if c['target']==value]
        if matches or spec.get('keep_empty'):
            chosen[label]=matches
    dispatch=int(census_specs[name]['dispatcher'],0)
    chosen['recognized_type38_dispatch']=[c for c in data['calls'] if c['target']==dispatch and c['args'].get('r4')==38]
    census[name]=chosen
check('29 recognized body request calls',len(census['ilaunch3']['body_request'])==29)
check('no recognized 50mm MCR submit caller',not census['jlaunch3']['unit_MCR_submit'])
check('type38 recognized call search',all(not v['recognized_type38_dispatch']for v in census.values()))
r.dump(r.LOCAL/'call-census.json',dict(limit='Only direct BL and linearly resolved constant JL. Not all indirect callers or CFG reachability.',images=census))

mcr=r.json.loads((r.LOCAL/'mcr-verified.json').read_text())
check('six MCR images rechecked',len(mcr)==6 and all(v['mcr_slot_absent_in_normal_apply']for v in mcr))
drivers=r.json.loads((r.LOCAL/'drivers-verified.json').read_text())
check('7 x 39 verified driver entries',len(drivers)==7 and all(len(v['entries'])==39 for v in drivers.values()))
tables=r.json.loads((r.LOCAL/'table-facts.json').read_text())
check('624 C040 constant low bytes',tables['c040_low_byte_histogram']=={'64':624})
emulator=r.json.loads((r.LOCAL/'emulator-results.json').read_text())
check('29 isolated CPU fixtures',len(emulator['cases'])==29)
check('ordinary capture and ISP pixels not claimed',emulator['ordinary_capture_executed'] is False and emulator['isp_pixels_executed'] is False)
check('backend library content unchanged',r.sha(r.ROOT/'tools/gxr_emulator_batch/build/libgxr_m32r.dylib')==emulator['library_sha256'])
guards=[v for v in emulator['cases']if 'guard_pass'in v]
check('guard positive and negative fixtures',[(v['width'],v['guard_pass'])for v in guards]==[(128,True),(4288,True),(5121,False)])
cache=[v for v in emulator['cases']if v['kind']=='EXIP apply control cache']
check('EXIP upload cache truth table',[(v['control'],v['cached'],len(v['dispatcher_calls']))for v in cache]==[(1,1,0),(1,0,1),(0,0,1),(0,1,1)])

rows=list(csv.DictReader((r.HERE/'predictions.csv').open()))
expected=set(range(27))|set(range(43,51))
check('35 prediction targets',set(int(v['index'])for v in rows)==expected)
check('280 unique scores',len(rows)==280 and len({(v['index'],v['group'],v['axis_hypothesis'],v['body_level'])for v in rows})==280)
check('prediction scope stays conditional',all(v['hardware_equation_closed']=='False' and v['main_JPEG_route_closed']=='False'for v in rows))
check('04 score denominator is not converted to zero percent',all(v['single_percent']==v['two_pass_percent']==v['gain_pp']=='' for v in rows if int(v['index'])==46))
replay_checks=[r.json.loads(p.read_text())for p in r.LOCAL.glob('prediction-check-*.json')]
check('all score replays match saved medians',all(v['max_saved_score_difference']==0 and not v['refit']for v in replay_checks))
check('replay runs cover all targets',set(i for v in replay_checks for i in v['indices'])==expected)
check('no prediction run exceeded 30 minutes',all(v['seconds']<1800 for v in replay_checks))
check('140 rendered output archives',len(list((r.LOCAL/'replay').glob('*/*.npz')))==140)
check('local data ignored by repository rule','/research/**/local/' in (r.ROOT/'.gitignore').read_text().splitlines())
check('no task-generated firmware or DAT',not any(p.suffix.lower()=='.dat' or p.name in ('ilaunch3','jlaunch3','qlaunch3','l08firm3')for p in r.HERE.rglob('*')if p.is_file()))
check('scratch identity',r.SCRATCH.resolve()==r.SCRATCH and not r.SCRATCH.is_symlink())

r.finish('seal')
# This directory did not exist before this task. Preserve local/ as deliverable evidence.
scratch_files=sum(p.is_file()for p in r.SCRATCH.rglob('*'))
# Path.unlink/rmdir keep absolute paths in the audit event. shutil.rmtree's
# dir_fd-relative names do not carry the parent directory into this fence.
for path in sorted(r.SCRATCH.rglob('*'),key=lambda p:len(p.parts),reverse=True):
    assert not path.is_symlink(),path
    if path.is_dir():path.rmdir()
    else:path.unlink()
r.SCRATCH.rmdir()
check('owned scratch removed',not r.SCRATCH.exists())
r.dump(r.LOCAL/'cleanup.json',dict(path=str(r.SCRATCH),removed=True,owned_files_removed=scratch_files,
    retained=str(r.LOCAL),tools_not_modified=True,no_card_access=True,no_firmware_or_DAT_build=True))
r.dump(r.LOCAL/'verification.json',dict(status='PASS',checks=checks,protected_inputs=len(protected),
    read_source_inputs=len(source_hashes),model_copy_items=len(copied['files']),windows=window_count,
    instruction_byte_records=sum(v['byte_checked']for v in indices.values()),emulator_fixtures=29,
    model_score_rows=280,physical_new_candidate_equations_closed=0,ordinary_capture_executed=False,
    physical_camera_executed=False,scratch_removed=True,nice=15,numerical_threads=1,
    seconds=time.monotonic()-started,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))

def manifest(base,files,path):
    lines=[r.sha(p)+'  '+str(p.relative_to(base))for p in sorted(files)]
    path.write_text('\n'.join(lines)+'\n')
    for line in path.read_text().splitlines():
        digest,rel=line.split('  ',1)
        assert r.sha(base/rel)==digest,rel
    return len(lines)

local_manifest=r.LOCAL/'SHA256SUMS'
local_files=[p for p in r.LOCAL.rglob('*')if p.is_file()and p!=local_manifest]
local_count=manifest(r.LOCAL,local_files,local_manifest)
public_manifest=r.HERE/'SHA256SUMS'
public_files=[p for p in r.HERE.rglob('*')if p.is_file()and not p.is_relative_to(r.LOCAL)and p!=public_manifest]
public_count=manifest(r.HERE,public_files+[local_manifest],public_manifest)
print(r.json.dumps(dict(status='PASS',checks=len(checks),protected_inputs=len(protected),windows=window_count,
    emulator_fixtures=29,model_score_rows=280,local_hash_entries=local_count,public_hash_entries=public_count,
    scratch_removed=not r.SCRATCH.exists()),ensure_ascii=False))
