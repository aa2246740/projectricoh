"""Run scoped v3.4c build and host gates. Never uses camera/card paths."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'acceptance'))
import common as c
HERE=c.HERE.parent
IMAGE=c.ROOT/'firmware/image_v34c'
PYTHON=['/usr/bin/python3','-I','-B']

def invoke(path,*args,label=None):
    result=c.run([*PYTHON,path,*args],label or 'finish-'+Path(path).stem+'-'+('-'.join(args) or 'main'),timeout=1200)
    print(result.stdout[-2200:],end='',flush=True)
    return result

def product():
    script=c.HERE/'verify_v34c.py'
    for phase in ('compile','vectors','basic','ctl','quarantine','irom','first','t','rpc-faults',
                  'blackbox','legacy','store-fault','service-quarantine','log-fault','neighbour',
                  'iso','publish-failure','conflict','same-conflict','accepted-f02','daily','rejected','r33'):
        invoke(script,phase)
    invoke(c.HERE/'verify_history34c.py')
    decode()

def resident():
    invoke(HERE/'resident/verify.py')
    invoke(HERE/'machine_checks.py')
    invoke(HERE/'entry_machine.py')
    invoke(HERE/'evidence_v34c.py','loader')

def image():
    hooks=json.loads((HERE/'local/resident/hooks.json').read_text())
    for h in hooks:
        h['enabled']=h['number']<=9
        h['kind']='data' if h['number'] in (3,4) else 'execution'
    (HERE/'local/hooks.json').write_text(json.dumps(hooks,indent=2)+'\n')
    (HERE/'local/patch-manifest.json').write_bytes((HERE/'local/resident/patch-manifest.json').read_bytes())
    common=['--elf',str(HERE/'local/resident/build/resident.elf'),
        '--hooks',str(HERE/'local/hooks.json'),'--patch-manifest',str(HERE/'local/patch-manifest.json')]
    package=IMAGE/'local/body-final-v34c'
    invoke(IMAGE/'build.py','--official',str(c.ROOT/'artifacts/firmware/gxr-1.51/ilaunch3'),
        *common,'--output',str(package),label='body-build-v34c')
    invoke(IMAGE/'verify.py','--package',str(package),*common,
        '--output',str(IMAGE/'local/verification-v34c'),label='body-verify-v34c')
    for phase in ('body','constructor','stack'):invoke(HERE/'evidence_v34c.py',phase)

def decode():
    spec=c.load(HERE/'decode_blackbox.py','blackbox_decoder')
    data={str(unit):spec.read_log((c.LOCAL/f'v34c-host/GXRBX-{unit}.BIN').read_bytes()) for unit in (0,2)}
    for value in data.values():
        assert value['publish']['engine_generation']==113
        assert value['publish']['rows']==8 and value['events']
    (HERE/'local/blackbox-decoded.json').write_text(json.dumps(data,indent=2)+'\n')
    print('PASS two blackbox receipts, CRCs and 64-slot event ring')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('product','resident','image','decode','size'))
    phase=parser.parse_args().phase;c.guard()
    if phase=='size':invoke(c.HERE/'size_probe.py')
    else:globals()[phase]()
