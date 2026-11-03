"""Assemble acceptance only from completed observations tied to the final candidate."""
from pathlib import Path
import collections
import hashlib
import json
import struct
import sys
import zipfile
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import ROOT,OUT,sha,save

FINAL='d11e88eae677f7ee3aeba4dc602c2085ef92b9c81f5c70286c8eb038211e4bbc'
BODY='50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008'

def read(name):return json.loads((OUT/name).read_text())

def runtime_binding(raw,state):
    """Corroborate cases whose original record lacks a top-level DAT digest.

    This is the resident's observed 16-word code guard, plus the code span and
    generation, not an invented embedded SHA. Command provenance is separate.
    """
    root=state['root'];off,n=struct.unpack_from('>II',raw,132)
    assert root['code_bytes']==n and state['generation']==119
    base=root['code_address']-off;relocated=bytearray(raw)
    ro,rz=struct.unpack_from('>II',raw,144)
    for at in range(ro,ro+rz,8):
        patch,target=struct.unpack_from('>II',raw,at)
        struct.pack_into('>I',relocated,patch,base+target)
    code=relocated[off:off+n];step=((n-4)>>4)&~3
    sample=b''.join(code[(n-4 if i==15 else i*step):(n-4 if i==15 else i*step)+4] for i in range(16))
    assert zlib.crc32(sample)==root['code_crc']
    return dict(method='observed resident code span/16-word guard + completed command input path',
        code_bytes=n,code_crc=root['code_crc'],image_base=hex(base),generation=119,embedded_sha_present=False)

def main():
    identity=read('identity.json')['119'];assert identity['dat']==FINAL
    built=ROOT/'firmware/engine_v40_ux/candidate/local/full-r13'
    sd=ROOT/'firmware/package_v36_g119/SD_ROOT';raw=(sd/'GXRCE.DAT').read_bytes()
    assert sha(raw)==FINAL and raw==(built/'GXRCE.DAT').read_bytes()
    assert sha((built/'engine.elf').read_bytes())==identity['elf']
    assert sha((sd/'ilaunch3').read_bytes())==BODY
    cases=[];commands=[]
    def command(label):
        name='local/commands/'+label+'/command.json';d=read(name)
        assert d['returncode']==0,(label,d['returncode']);commands.append(name);return d
    def case(name,expected='PASS',label=None):
        d=read(name);assert d['status']==expected,(name,d.get('status'))
        if d.get('dat_sha256'):
            assert d['dat_sha256']==FINAL,(name,'wrong DAT')
            if d.get('elf_sha256'):assert d['elf_sha256']==identity['elf'],(name,'wrong ELF')
            binding=dict(method='recorded SHA-256',dat=d['dat_sha256'])
        else:binding=runtime_binding(raw,d['after'])
        if label:command(label)
        cases.append(dict(file=name,status=d['status'],binding=binding))
        return d
    for unit in ('50mm','28mm','mount'):
        for group in ('matrix','perf','ah','exits'):
            label=('resumed-' if group=='matrix' else 'verified-')+group+'-'+unit
            d=case('native/'+group+'-'+unit+'.json',label=label)
            assert d['getter_fixed_return_stub_removed'] and not d['native_ui_hand_seeded']
            if group=='matrix':
                assert len(d['fast_moves'])==41 and len(d['faults'])==3
                assert d['reboot']['state']['cursor']==4 and d['reboot']['state']['W']==0
            if group=='perf':
                assert len(d['moves'])==32
                assert all(x['crc_accelerated_calls']==x['rpc_errors']==0 for x in d['moves'])
    for at in (1,16,140):
        d=case(f'native/adversarial-foreign-50mm-at{at}-reopen-fn2.json',label=f'verified-foreign-at{at}')
        assert d['complete_slots']==([4] if at==1 else [5])
        assert d['after']['root']['state']==3 and d['after']['native_activity']==7 and d['after']['native_overlay']==21
        assert d['foreign_followthrough']['new_engine_entries']==d['foreign_followthrough']['new_engine_core_calls']==0
        assert d['reopened_fn2']['state']['root']['state']==3 and d['reopened_fn2']['actual']['contrast']==1
        cases[-1]['primary_late_ui_write_count']=dict(value=0,basis='Executed assertion before foreign_followthrough; completed command exit=0. Raw write array also includes subsequent legitimate native/own-view operations.')
    for point in ('redraw','cache'):
        d=case('native/ui-cutpoint-'+point+'.json',label='verified-ui-'+point)
        assert not d['writes_after_takeover']
        assert d['after']['W']==d['after']['preview_calls']==0
    d=case('native/persistent-50mm.json','PASS_NOTICE_LATCHED_MIXED_RAM','verified-persistent-50mm')
    assert not d['matching_complete_slots'] and d['after']['list']['uncertain']==1
    assert d['notice']['rows']==d['notice']['cursor']==d['notice']['dot_row']==1
    assert d['notice_ascii']=='ERR POWER OFF/ON' and d['notice_glyph_hex'] and d['latched_no_more_rpc']
    for unit in ('50mm','28mm','mount'):
        d=case('native/coalescing-119-'+unit+'-at1.json',label='verified-coalesce-'+unit+'-at1')
        assert d['transactions'][0]['W']==0 and d['step']['rpc_calls']==161 and d['step']['refreshes']==1
    d=case('native/coalescing-119-50mm-at16.json',label='verified-coalesce-50mm-at16')
    assert d['transactions'][0]['W']>0 and d['step']['rpc_calls']==376 and d['step']['refreshes']==2
    baseline=read('native/coalescing-118-50mm-at1.json')
    assert baseline['status']=='PASS' and baseline['dat_sha256']==read('identity.json')['118']['dat']
    assert baseline['step']['rpc_calls']==376 and baseline['step']['refreshes']==2
    command('verified-machine-static');command('verified-machine-gates');command('verified-reproduce')
    gates=read('machine-gates.json');assert gates['status']=='PASS' and gates['capabilities']=='0xe7fff'
    assert not any(gates['zero_file_mutations'].values())
    repro=read('reproducibility.json');assert repro['status']=='PASS'
    assert repro['files']['GXRCE.DAT']['sha256']==FINAL and repro['files']['engine.elf']['sha256']==identity['elf']
    costs=read('measurements.json');assert costs['moves']==96
    assert all(x['dat_sha256']==FINAL and x['elf_sha256']==identity['elf'] for x in costs['author_comparison'])
    closure=read('codegen-closure.json');assert closure['status']=='ACCOUNTED_A_B_C' and not closure['unresolved']
    selfcheck=read('codegen-selfcheck.json')
    assert selfcheck['artifacts']['119']['dat']==FINAL
    assert selfcheck['status']=='INCOMPLETE_GEN117_BRANCH_CLOSURE' and selfcheck['open_outcomes']>0
    command('resumed-codegen-closure');command('resumed-branch-coverage');command('resumed-codegen-selfcheck')
    for name,data in closure['B'].items():
        b=read(data['file'])
        assert b['artifacts']['119']['dat']==FINAL and b['artifacts']['119']['elf']==identity['elf']
        assert b['random']>=10000 and b['boundary']>=64 and not b['failures']
    counters=[]
    def walk(value,path):
        if isinstance(value,dict):
            if {'create','write','rename','delete','write_open'}<=value.keys():
                record={k:value[k] for k in ('create','write','rename','delete','write_open')}
                assert all(v==0 for v in record.values()),(path,record);counters.append(dict(path=path,counters=record))
            for k,v in value.items():walk(v,path+'/'+k)
        elif isinstance(value,list):
            for i,v in enumerate(value):walk(v,path+'/'+str(i))
    for c in cases:walk(read(c['file']),c['file'])
    card=[]
    for line in (sd.parent/'CARD_SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ',1);p=(sd.parent/name).resolve();assert p.is_relative_to(sd)
        assert sha(p.read_bytes())==digest;card.append(name)
    assert len(card)==30 and set(card)=={'SD_ROOT/'+p.name for p in sd.iterdir()}
    assert read('data-equality.json')['equal']
    inputs=read('protected-input-integrity.json');assert inputs['unchanged'] and not inputs['changes']
    result=dict(status='PASS_NATIVE_CODEGEN_INCOMPLETE',native_status='PASS',codegen_status=selfcheck['status'],
        codegen_open_outcomes=selfcheck['open_outcomes'],dat_sha256=FINAL,elf_sha256=identity['elf'],body_sha256=BODY,cases=cases,completed_commands=commands,
        independent_perf_moves=96,ordinary_matrix_moves=123,B_pairs=closure['B_pairs'],zero_file_write_observations=counters,
        card_sha256sums='30/30 OK',card_manifest_sha256=sha((sd.parent/'CARD_SHA256SUMS').read_bytes()),
        frozen_files=inputs['files'],global_snapshot_unchanged=inputs['global_snapshot_unchanged'],global_snapshot_changes=inputs['global_snapshot_changes'],persistent_mixed_ram_remains=True,
        limitations=['No camera/card/flash/LCD/power-cycle acceptance.','A/B/C inventory is complete, but per-PC B branch closure is incomplete under the gen117 standard; see codegen-selfcheck.json.','Error notice is proved for the persistent RPC model with live resident/session.'])
    save('acceptance.json',result)
    print('PASS native/artifact checks:',len(cases),'native result files;',len(counters),'zero-file-write observations; B',closure['B_pairs'],'pairs; CARD 30/30; CODEGEN INCOMPLETE',flush=True)

if __name__=='__main__':main()
