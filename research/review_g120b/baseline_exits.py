"""Count gen117 H07 communication with the unchanged resident close code."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_cases as nc
from common import OUT, save, sha

n, ux, m, fr, v = nc.n, nc.ux, nc.m, nc.fr, nc.v

def run(unit):
    n.configure(unit, 'baseline-exits')
    dat, elf = ux.configure(True, unit+'-baseline-exits')
    v.python_backend.CACHE = OUT/'decode'/(unit+'-baseline-exits')
    h, p, w = m.boot(unit)
    m.published(h, p, w)
    m.deep(p, 4)
    context = nc.stamp(h, p)
    rows = []
    for keep in (0, 1):
        for key in (0x23, 0x2b):
            def check(record, keep=keep, key=key):
                ux.need(fr.native(h, 0x20265818, (keep,)))
                at, preview = len(p.rpc.log), h.stub_hits.get('preview', 0)
                result = ux.need(fr.press(h, key))
                calls = p.rpc.log[at:]
                record.update(keep=keep, key=hex(key), result=result, RPC=len(calls),
                    W=sum(c['cmd']==22 for c in calls), rpc_log=calls,
                    preview=h.stub_hits.get('preview', 0)-preview,
                    after=ux.snap(h, p), actual=m.deep(p, 4), file_mutations=m.no_writes(p))
            rows.append(nc.case('gen117-exit-'+unit+'-k'+str(keep)+'-'+hex(key), check, context))
    save('native/gen117-exits-'+unit+'.json', dict(status='PASS', unit=unit,
        dat_sha256=sha(dat.read_bytes()), elf_sha256=sha(elf.read_bytes()), cases=rows))
    print('PASS baseline exits', unit, [(x['key'],x['keep'],x['RPC']) for x in rows], flush=True)

if __name__ == '__main__':
    for unit in ('50mm', '28mm', 'mount'):
        run(unit)
