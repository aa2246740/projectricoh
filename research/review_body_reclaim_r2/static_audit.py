#!/usr/bin/python3
"""Bind the source, final link, frames and native reads to local inputs."""
import hashlib, json, re, subprocess, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=HERE/'local/static'
OUT.mkdir(exist_ok=True)
records=[]
def run(name,args):
    start=time.monotonic()
    p=subprocess.run(['/usr/bin/nice','-n','10',*map(str,args)],capture_output=True,text=True,timeout=600)
    (OUT/(name+'.txt')).write_text(p.stdout+p.stderr)
    records.append(dict(name=name,returncode=p.returncode,elapsed_seconds=round(time.monotonic()-start,3),timeout_seconds=600))
    assert p.returncode==0,(name,p.stderr)
    return p.stdout
objdump=ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
for variant in ['base','r3','f_inl','r6a','r7']:
    directory=HERE/'local/rebuild/v'/variant/'build'
    for unit in ['hooks','loader']:
        run(f'{variant}-{unit}',[objdump,'-dr',directory/(unit+'.o')])
    if (directory/'resident.elf').exists():
        run(f'{variant}-elf',[objdump,'-d',directory/'resident.elf'])
        run(f'{variant}-symbols',[objdump,'-t',directory/'resident.elf'])
        run(f'{variant}-sections',[objdump,'-h',directory/'resident.elf'])
        run(f'{variant}-relocations',[objdump,'-r',directory/'resident.elf'])
for name,begin,end in [('outer',0x2015f854,0x2015f9dc),('wrapper',0x2016583c,0x20165ab4),
                       ('stack_records',0x2006dbb8,0x2006dcd0)]:
    run(name,['/usr/bin/python3','-I','-B',HERE/'tools/dis.py',hex(begin),hex(end)])
frames={}
for variant in ['base','r3','f_inl','r6a','r7']:
    table={}
    for su in (HERE/'local/rebuild/v'/variant/'build').glob('*.su'):
        for line in su.read_text().splitlines():
            name,size,*tail=line.split('\t'); assert tail==['static'],(su,line)
            table[name.split(':')[-1]]=int(size)
    frames[variant]=table
assert frames['r7']['rv_load']==frames['r6a']['rv_load']==88
assert frames['r7']['rv_hook_observe']==frames['r6a']['rv_hook_observe']==44
assert frames['r6a']['discard_main']==16 and frames['r6a']['ui_call']==24
assert 'discard_main' not in frames['r7'] and 'ui_call' not in frames['r7']
for name in ('discard_main','ui_call'):
    assert re.search(r'\bl\s+F\s+\.resident\s+[0-9a-f]+\s+'+name+r'\b',(OUT/'r3-symbols.txt').read_text())
    assert '<'+name+'>:' not in (OUT/'r7-elf.txt').read_text()
outer=(OUT/'outer.txt').read_text()
pushes=re.findall(r'\bpush\s+(\w+)',outer)
assert pushes==['r8','r9','r10','r11','r12','lr','fp'],pushes
rows=json.loads((HERE/'local/sizes.json').read_text())
assert rows==json.loads((ROOT/'research/body_next_steps/prototype/sizes.json').read_text())
r7=next(r for r in rows if r['variant']=='r7')
assert r7['code_bytes']==8040 and r7['code_end']=='0x200546d4' and r7['free_above_24B_gate']==20
assert r7['sha256']=='a6cd3c09c48efd3c08be02278fc0c5074a8aa6232ac63437340a745680360ae1'
for row in rows:
    if row['strict_link_ok']:
        assert row['root']==244 and row['root_pins']==12 and row['root_vma']=='0x20054700'
        assert not row['nonempty_sections_outside_allowed'] and not row['margin_defined_elsewhere']
for name,accepted in [('neg44',True),('neg45',False)]:
    assert next(r for r in rows if r['variant']==name)['strict_link_ok']==accepted
ld=(HERE/'local/rebuild/v/r7/resident.ld').read_text()
assert ld.count('RV_PLANNING_MARGIN =')==1
assert 'SIZEOF(.forbidden)==0' in ld and 'SIZEOF(.relocations)==0' in ld
prefix=4+64+44
def ledger(f):
    chain=f['rv_engine']+f['rv_check']+f['rv_session']+f['rv_allocation']
    return dict(h40_peak=prefix+chain,h40_dat=prefix+f['rv_engine']+f['rv_invoke'],
                h10_peak=prefix+f.get('ui_call',0)+chain,h10_dat=prefix+f.get('ui_call',0)+f['rv_engine']+f['rv_invoke'],
                h01_peak=prefix+f['rv_load']+chain,h01_dat=prefix+f['rv_load']+f['rv_engine']+f['rv_invoke'],
                h01_discard_chain=prefix+f['rv_load']+f.get('discard_main',0)+f['rv_session']+f['rv_allocation'])
result=dict(classification='static source, official bytes and exact linked artifacts',commands=records,frames=frames,
            stack_ledger={v:ledger(frames[v]) for v in ['r3','r6a','r7']},strict_variant=r7,
            outer_saved_registers=pushes,outer_lr_from_native_sp=4,
            noinline_original_reason='No reason recorded in searched reports, decisions or available commit messages.',
            scope_limits=['No native full call-chain or IRQ depth measurement','No paired production DAT or camera'])
(HERE/'local/static-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(variants=len(rows),r7_bytes=r7['code_bytes'],stack_ledger=result['stack_ledger']),indent=2))
