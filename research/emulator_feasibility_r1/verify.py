#!/usr/bin/env python3
"""Verify literal CPU effects, real-entry boundaries, sources, and frozen inputs."""
import argparse
import json
from pathlib import Path
import runpy
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--rerun', action='store_true')
    p.add_argument('--check-sums', action='store_true')
    args = p.parse_args()
    manage = runpy.run_path(str(HERE/'manage.py'))
    frozen = manage['verify']()
    core = runpy.run_path(str(HERE/'prototype/boot_probe.py'))
    image = core['Image']()
    Cpu, Boundary = core['Cpu'], core['Boundary']
    checks = []

    def check(name, actual, expected):
        assert actual == expected, (name, actual, expected)
        checks.append(name)

    check('official MAIN entry from header', image.entry, 0x2004b000)
    check('section 15 instruction VMA maps independently', image.offset(0x0500c584), 0x3cbb84)
    check('H01 maps into section 9', image.offset(0x2028709c), 0x23c29c)
    check('H40 maps into section 6', image.offset(0x2015f9d8), 0x114bd8)
    descriptor=int.from_bytes(image.data(0x20051a2c+60*2,2),'big')
    check('GPIO 60 descriptor comes from official image',descriptor,0x74)
    port=((descriptor<<23)&0xffffffff)>>27
    check('independent GPIO address calculation', (2*port-0x8fbf90)&0xffffffff,0xff70407e)
    c = Cpu(image, 'strict')
    c.r[3] = 0x1234567b
    check('JL aligns target and links next bundle', c.op('jl', ('r3',), 0x1002), 0x12345678)
    check('JL right slot link', c.r[14], 0x1004)
    c.r[8],c.r[0] = 1000,256
    c.op('remu', ('r8','r0'), 0x1000)
    check('unsigned remainder instruction', c.r[8], 232)
    c.r[0] = 0
    c.op('remu', ('r8','r0'), 0x1000)
    check('GNU REMU zero divisor leaves destination', c.r[8], 232)
    c.set_cr('spi', 0x05017ffc)
    c.set_cr('spu', 0x05016ffc)
    check('system stack is active at PSW SM zero', c.r[15], 0x05017ffc)
    c.set_psw(0x80)
    check('user stack switch', c.r[15], 0x05016ffc)
    c.r[15] -= 16
    c.set_psw(0)
    check('system stack restored', c.r[15], 0x05017ffc)
    check('user stack saved', c.get_cr('spu'), 0x05016fec)
    c.r[15] = 0x05017000
    c.current_pc = 0x1000
    c.op('push', ('sp',), 0x1000)
    check('push SP stores original value', c.read(0x05016ffc,4), 0x05017000)
    try:
        c.op('unimplemented-test-op', (), 0x1000)
    except Boundary as e:
        check('unknown instructions stop', e.kind, 'unsupported_instruction')
    else:
        raise AssertionError('unknown instruction was accepted')

    profiles = ['strict','monitor-null','gpio-latch','gpio-high','gpio-low','init-latch','serial-ready']
    results = {}
    out = HERE/'local/runs'
    for profile in profiles:
        if args.rerun:
            result = subprocess.run(['/usr/bin/python3','-I','-B',str(HERE/'prototype/boot_probe.py'),
                                     '--profile',profile], capture_output=True,text=True,check=True)
            (out/(profile+'.stdout.txt')).write_text(result.stdout)
            (out/(profile+'.stderr.txt')).write_text(result.stderr)
        results[profile] = json.loads((out/(profile+'.json')).read_text())
    check('strict entry execution reaches absent monitor vector', results['strict']['stop'],
          {'kind':'unmapped_instruction_fetch','pc':'0x48'})
    check('strict entry completes six real bundles', results['strict']['completed_bundles'], 6)
    check('strict active interrupt stack logged correctly', results['strict']['control_registers']['spi'], '0x5017ffc')
    check('first peripheral after monitor shim', results['monitor-null']['stop']['address'], '0xff70407e')
    check('first peripheral instruction is official GPIO read', results['monitor-null']['stop']['pc'], '0x2004d9c4')
    check('GPIO-only stub reaches boot serial config', results['gpio-latch']['stop']['address'], '0xff703404')
    check('zero-latch profile cannot escape serial wait', results['init-latch']['stop']['kind'], 'repeated_cpu_state_bound')
    check('ready assumption reaches real NAND command port', results['serial-ready']['stop']['address'], '0x10000')
    check('NAND command port instruction', results['serial-ready']['stop']['pc'], '0x20050bb0')
    for profile,result in results.items():
        check(profile+' did not reach application/UI milestones', result['milestones'], [])
        check(profile+' firmware identity', result['official_sha256'], core['EXPECTED'])
    sources = json.loads((HERE/'local/sources.json').read_text())
    downloaded = 0
    for row in sources:
        if row.get('status') == 200:
            check('download '+row['path'], manage['sha'](ROOT/row['path']), row['sha256'])
            downloaded += 1
    static = json.loads((HERE/'local/static/summary.json').read_text())
    check('all 16 sections inventoried', static['sections'], 16)
    check('byte checks cover recorded disassembly', static['byte_checked'], 3858192)
    if args.check_sums:
        for line in (HERE/'SHA256SUMS').read_text().splitlines():
            digest,name = line.split('  ',1)
            check('delivery '+name, manage['sha'](HERE/name), digest)
    if not args.check_sums:
        result = {'status':'CHECKS_PASS_PROTOTYPE_BOUNDARIES_ONLY','checks':len(checks),
                  'protected_files_verified':frozen,'downloads_verified':downloaded,
                  'official_firmware_changed':False,'boot_ui_reached':False,
                  'names':checks}
        (HERE/'local/verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'CHECKS_PASS_PROTOTYPE_BOUNDARIES_ONLY','checks':len(checks),
                      'protected_files_verified':frozen,'downloads_verified':downloaded,'boot_ui_reached':False}))


if __name__ == '__main__':
    main()
