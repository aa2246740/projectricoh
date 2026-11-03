#!/usr/bin/env python3
"""Single-process-at-a-time checks; never builds a DAT or touches a device."""
from pathlib import Path
import argparse
import contextlib
import io
import json
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import collect

PYTHON = ['/usr/bin/python3','-I','-B']

def command(label, script, *args):
    argv = [*PYTHON,str(HERE/script),*args]
    result = subprocess.run(argv,cwd=collect.ROOT,text=True,capture_output=True)
    (collect.OUT/(label+'.stdout')).write_text(result.stdout)
    (collect.OUT/(label+'.stderr')).write_text(result.stderr)
    assert result.returncode == 0, (label,result.returncode,result.stderr[-2000:])
    return {'label':label,'argv':argv,'returncode':result.returncode,
        'stdout':label+'.stdout','stderr':label+'.stderr'}

def full():
    im = collect.Image()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        for row in json.loads((HERE/'windows.json').read_text()):
            start, end = int(row['start'],16), int(row['end'],16)
            if row['mode'] == 'equal':
                im.dump(start,end,row['label'])
            else:
                collect.compare(im,start,end,row['label'])
    (collect.OUT/'windows-final.stdout').write_text(output.getvalue())
    argv = [str(collect.r2.OBJDUMP),'-d','-EB',str(collect.ROOT/
        'firmware/resident_v36/local/resident/build/resident.elf')]
    disasm = subprocess.run(argv,cwd=collect.ROOT,text=True,capture_output=True)
    (collect.OUT/'resident-disasm.txt').write_text(disasm.stdout)
    (collect.OUT/'resident-disasm.stderr').write_text(disasm.stderr)
    assert disasm.returncode == 0
    commands = [{'label':'resident_disassembly','argv':argv,'returncode':disasm.returncode},
        command('scan-final','scan.py'),command('replay-final','replay.py'),
        command('evidence-final','evidence.py','check'),
        command('protected-final','collect.py','after'),
        command('extra-final','evidence.py','extra-after')]
    result = json.loads((collect.OUT/'replay-results.json').read_text())
    evidence = json.loads((collect.OUT/'evidence-check.json').read_text())
    sources = {p.name:collect.sha(p) for p in sorted(HERE.glob('*.py'))}
    collect.save('verification.json',{'status':'PASS_STATIC_AND_BOUNDED_HOST',
        'replay_cases':len(result['cases']),'evidence':evidence,'commands':commands,
        'source_sha256':sources,'scope':'No RTOS scheduling, physical camera, media, DAT generation or product acceptance.'})
    print('PASS',len(result['cases']),'bounded host cases;',evidence['windows'],'static windows')

def delivered_files():
    return sorted(p for p in HERE.rglob('*') if p.is_file() and
        p.name != 'SHA256SUMS' and '__pycache__' not in p.parts)

def seal():
    first = (HERE/'REPORT.md').read_text().splitlines()[0]
    assert first.startswith(('只改 DAT 不可行：','找到可用门禁：'))
    for name in ('protected-check.json','extra-check.json'):
        assert json.loads((collect.OUT/name).read_text())['status'] == 'PASS', name
    verified = json.loads((collect.OUT/'verification.json').read_text())
    assert verified['status'] == 'PASS_STATIC_AND_BOUNDED_HOST'
    assert verified['source_sha256'] == {p.name:collect.sha(p) for p in sorted(HERE.glob('*.py'))}
    files = delivered_files()
    target = HERE/'SHA256SUMS'
    target.write_text(''.join(collect.sha(p)+'  '+str(p.relative_to(collect.ROOT))+'\n' for p in files))
    print('sealed',len(files),'root-relative entries')

def check_seal():
    manifest = HERE/'SHA256SUMS'
    listed = []
    for line in manifest.read_text().splitlines():
        digest, rel = line.split(maxsplit=1)
        assert re.fullmatch('[0-9a-f]{64}',digest)
        path = collect.ROOT/rel
        assert path.resolve().is_relative_to(HERE.resolve())
        assert path.is_file() and collect.sha(path) == digest, rel
        listed.append(path)
    assert len(listed) == len(set(listed))
    assert set(listed) == set(delivered_files()), 'unlisted or removed delivery files'
    print('PASS SHA256SUMS',len(listed),'entries',collect.sha(manifest))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action',choices=('full','seal','check-seal'))
    a = ap.parse_args()
    collect.preflight()
    {'full':full,'seal':seal,'check-seal':check_seal}[a.action]()

if __name__ == '__main__':
    main()
