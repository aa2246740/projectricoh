"""Check every application entry after both continuous communication failures."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_cases as nc
from common import save, sha

n, ux, m, fr = nc.n, nc.ux, nc.m, nc.fr

def run(unit):
    n.configure(unit, 'latch-two-states')
    h, p, w = m.boot(unit)
    m.published(h, p, w)
    context = nc.stamp(h, p)
    results = []
    for failure_at in (1, 16):
        def check(record, failure_at=failure_at):
            nc.persistent(h, p, failure_at)
            before = ux.snap(h, p)
            root_n = p.symbol_pc('n')
            assert h.u(root_n+3712, 1) == 1 and before['root']['state'] == 3
            assert before['list']['uncertain'] == (0 if failure_at == 1 else 1)
            at, preview = len(p.rpc.log), h.stub_hits.get('preview', 0)
            rows = []
            for slot, args in ((0, []), (3, []), (4, [0]), (4, [10]), (5, []),
                               (6, [0]), (6, [7]), (2, [7, 1]), (2, [7, 0]), (2, [0, 0])):
                result = p.engine(slot, args)
                assert result['ok'], result
                assert len(p.rpc.log) == at and h.stub_hits.get('preview', 0) == preview
                assert h.u(root_n+3712, 1) == 1
                assert ux.snap(h, p)['list']['uncertain'] == before['list']['uncertain']
                rows.append(dict(slot=slot, args=args, result=result, failed=1,
                                 RPC=0, W=0, preview=0))
            shown = nc.notice(h, p, w)
            assert len(p.rpc.log) == at and h.stub_hits.get('preview', 0) == preview
            assert h.u(root_n+3712, 1) == 1
            record.update(unit=unit, failure_at=failure_at, before=before, cases=rows,
                          notice=shown, RPC=0, W=0, preview=0,
                          file_mutations=m.no_writes(p))
        result = nc.case('latch-'+unit+'-at'+str(failure_at), check, context)
        results.append(result)
    save('native/latch-paths-'+unit+'.json', dict(status='PASS', unit=unit,
        dat_sha256=sha(m.DAT.read_bytes()), states=results,
        reset_scope='No tested application entry clears the latch. Physical power cycling remains untested.'))
    print('PASS both latch states', unit, flush=True)

if __name__ == '__main__':
    run(sys.argv[1])
