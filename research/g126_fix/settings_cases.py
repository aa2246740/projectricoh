"""Check settings repair and failure returns through native publication and H07."""
from pathlib import Path
import argparse
import os
import struct
import sys
import traceback
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ui_test_support import *
from cold_reentry import full_plan

def run(s, action, field, failure, record):
    before = s.state()
    slot = before['slot']
    settings = s.h.u(0x200c0dac)
    expected = full_plan(s.h, s.p, slot)
    assert expected['matches']
    offsets = (0x36e, 0x6dd, 0x6de) if field == 'all' else (int(field, 16),)
    s.h.phase = 'model:settings_input'
    for offset in offsets:
        old = s.h.u(settings + offset, 1)
        s.h.put(settings + offset, 5 if offset == 0x36e else (old % 17) + 1, 1)
    s.h.phase = 'cpu'
    wrong = full_plan(s.h, s.p, slot)
    assert not wrong['matches']
    previews = []
    entries = []
    failures = []
    releases = []
    s.h.b.add_breakpoint(0x202d6f38, lambda b:previews.append(full_plan(s.h,s.p,slot)) or False)
    s.h.b.add_breakpoint(s.p.symbol_pc('eng_check_settings'), lambda b:entries.append(dict(
        inflight=s.h.u(s.pe.ROOT_ADDR+6,1), rows=s.h.u(0x2022f5ac,1))) or False)
    enabled=[True]
    def service(b):
        service_id, operation = b.core.r[0], b.core.r[1]
        if service_id == 6 and operation == 3:
            releases.append(operation)
        selected = (failure in ('set_once','set_always') and service_id==6 and operation==2 or
                    failure=='preview_once' and service_id==5 and operation==1)
        if not enabled[0] or not selected or failure.endswith('once') and failures:
            return False
        reply = b.core.r[3]
        b.write(reply, struct.pack('>HHi',1,32,-1))
        b.core.r[0] = 0xffffffff
        b.set_reg('pc', b.core.r[14])
        failures.append(dict(service=service_id, operation=operation))
        return False
    if failure:
        s.h.b.add_breakpoint(s.p.symbol_pc('rv_call'), service)
        # A deliberate external mismatch exists before the new boundary runs.
        # Keep ASCII observations, and compare the complete plan after return.
        callbacks=s.h.b.breakpoints[s.p.symbol_pc('rv_native_ascii')]
        callbacks[:]=[cb for cb in callbacks if cb!=s._ascii]
        s.h.b.add_breakpoint(s.p.symbol_pc('rv_native_ascii'),lambda b:s.ascii.append(
            b.read(b.core.r[0],b.core.r[1]).decode('ascii')) or False)
    at = len(s.p.rpc.log)
    result = s.press(action)
    actual = full_plan(s.h,s.p,slot)
    diagnostic = s.ux.diagnostic(s.h,s.p)
    record.update(action=action, field=field, failure=failure, before=before, wrong=wrong,
                  after=result, final_plan=actual, previews=previews, check_entries=entries,
                  simulated_failures=failures, settings_releases=len(releases), diagnostic=diagnostic,
                  RPC=len(s.p.rpc.log)-at, rpc_log=s.p.rpc.log, unit=s.unit, dat_sha256=sha(s.p.dat),
                  file_mutations=s.m.no_writes(s.p), native_UI=ui_audit(s.h),
                  input_scope='Explicit external settings model input; no UI or engine-state assignment.')
    assert entries and all(row['inflight']==1 for row in entries)
    assert not diagnostic['busy'] and not diagnostic['uncertain']
    assert not result['failed'], 'Settings-only service errors must retain the inherited latch rule'
    if failure:
        assert failures and releases
    if not failure:
        assert actual['matches'] and previews and previews[-1]['matches']
        s.match(slot, before['levels'])
    else:
        if not actual['matches']:
            assert result['rows']==7, 'A failed restore must withdraw the unchecked eight-row view'
        record['expected_service_failure_boundary']=True
        record['successful_preview_observed']=bool(previews and previews[-1]['matches'])
        enabled[0]=False
        s.reopen()
        record['next_open_plan']=full_plan(s.h,s.p,slot)
        assert record['next_open_plan']['matches']
        s.match(slot,before['levels'])
    record['status'] = 'PASS'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--unit',choices=('50mm','28mm','mount'),default='50mm')
    parser.add_argument('--only-failures',action='store_true')
    args=parser.parse_args()
    s=Session(args.unit,'settings-cases')
    results=[]
    def cases(phase):
        choices=[] if args.only_failures else [(action, field, '') for action in ('DISP','OK','ADJ') for field in ('36e','6dd','6de','all')]
        choices += [(action,'all',failure) for action in ('DISP','OK') for failure in ('set_once','set_always','preview_once')]
        for action,field,failure in choices:
            label='-'.join((args.unit,phase,action,field,failure or 'normal'))
            sys.stdout.flush()
            pid=os.fork()
            if pid==0:
                record=dict(case=label);code=0
                try:run(s,action,field,failure,record)
                except BaseException:record.update(status='FAIL',error=traceback.format_exc());code=1
                save('local/settings-cases/'+label+'.json',record)
                print(label,record['status'],record.get('error','')[-700:],flush=True)
                os._exit(code)
            _,status=os.waitpid(pid,0)
            results.append(dict(case=label,wait_status=status))
    cases('stock04')
    s.press('DOWN');s.press('OK');s.reopen()
    cases('confirmed05')
    if args.only_failures:
        previous=json.loads((OUT/('evidence/settings-cases-'+args.unit+'.json')).read_text())
        replaced={row['case'] for row in results}
        results=[row for row in previous['cases'] if row['case'] not in replaced]+results
    save('evidence/settings-cases-'+args.unit+'.json',dict(status='PASS' if all(r['wait_status']==0 for r in results) else 'FAIL',
         dat_sha256=sha(s.p.dat),unit=args.unit,cases=results))
    assert all(r['wait_status']==0 for r in results),results

if __name__=='__main__':
    main()
