#!/usr/bin/env python3
"""Synthetic protocol exploration, independent of instruction replay and camera."""
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import evidence as e

DEPS={
 'raw_close':set(),
 'raw_send_completion':{'raw_close'},
 'raw_completion_consumed':{'raw_send_completion'},
 'raw_handler_return':{'raw_send_completion'},
 'jpeg_submit':set(),
 'jpeg_close':{'raw_handler_return','jpeg_submit'},
 'jpeg_send_completion':{'jpeg_close'},
 'jpeg_completion_consumed':{'jpeg_send_completion'},
 'jpeg_handler_return':{'jpeg_send_completion'},
}

def orders(done=(),remaining=None):
    remaining=set(DEPS) if remaining is None else remaining
    if not remaining:
        yield done
        return
    for step in sorted(remaining):
        if DEPS[step]<=set(done):
            yield from orders(done+(step,),remaining-{step})

def observation(done):
    done=set(done)
    raw_active='raw_handler_return' not in done
    jpeg_active='jpeg_close' in done and 'jpeg_handler_return' not in done
    queue=int('jpeg_submit' in done and 'jpeg_close' not in done)
    files_open=int('raw_close' not in done)
    native_state=2 if files_open else 1
    retired={'raw_completion_consumed','jpeg_completion_consumed'}<=done
    naive=(queue==0 and files_open==0 and native_state==1)
    guarded=(naive and not raw_active and not jpeg_active and retired and 'jpeg_submit' in done)
    return dict(queue2=queue,high_handles=files_open,native_state=native_state,
        task8_active=raw_active or jpeg_active,accepted_exposure=int(not retired),
        producer_sealed='jpeg_submit' in done,naive_grant=naive,guarded_grant=guarded)

def explore():
    schedules=list(orders())
    witnesses={}
    checked=0
    guarded_grants=0
    for schedule in schedules:
        for i in range(len(schedule)+1):
            prefix=schedule[:i]
            obs=observation(prefix)
            checked+=1
            if obs['naive_grant'] and not obs['guarded_grant'] and not obs['task8_active']:
                label='upstream_member_not_submitted' if 'jpeg_submit' not in prefix else 'task28_completion_inflight'
                if label not in witnesses or len(prefix)<len(witnesses[label]['trace']):
                    witnesses[label]=dict(trace=prefix,observation=obs)
            if obs['guarded_grant']:
                guarded_grants+=1
                assert {'raw_handler_return','jpeg_handler_return','raw_completion_consumed',
                        'jpeg_completion_consumed','jpeg_submit'}<=set(prefix)
    assert len(witnesses)==2 and guarded_grants>0
    return dict(schedules=len(schedules),observations=checked,guarded_grants=guarded_grants,
                naive_counterexamples=witnesses)

def faults():
    rows=[]
    # A different request cannot reuse an old completion's generation/cookie.
    for current in (1,2,0xffffffff):
        for incoming in (0,1,2,0xffffffff):
            for cookie in (17,18):
                accepted=incoming==current and cookie==17
                rows.append(dict(case='completion_identity',current=current,incoming=incoming,
                                 cookie=cookie,publishes_current=accepted))
    # Epoch changes before any next API call cancel without entering that call.
    stages=('before_open','after_open','before_write','after_write','before_close','after_close')
    for media_changed in (False,True):
        for step in stages:
            after=step.startswith('after_')
            native_call_may_have_run=after or step in ('before_write','before_close')
            can_release=step=='before_open'
            can_next_io=False
            can_close_owned=(not media_changed and native_call_may_have_run and step!='after_close')
            rows.append(dict(case='epoch_revoke',stage=step,media_changed=media_changed,
                next_data_io=can_next_io,owned_close_budget=int(can_close_owned),
                healthy_release_without_further_evidence=can_release,
                prior_native_call_cannot_be_undone=native_call_may_have_run))
    # Timeouts never imply that a native call has returned.
    for returned in (False,True):
        for high_count in (0,1):
            for free_slots in (1,2):
                healthy_release=returned and high_count==0 and free_slots==2
                if not returned or free_slots<2:assert not healthy_release
                rows.append(dict(case='timeout_and_slot_health',native_returned=returned,
                    high_count=high_count,free_slots=free_slots,healthy_release=healthy_release,
                    latch_fault=returned and not healthy_release))
    rows.append(dict(case='block_all_senders_deadlock',accepted_exposure=1,
        missing_member='JPEG',gate_blocks_continuation=True,can_drain=False,
        recovery='Reject user save before native I/O; allow accepted continuations.'))
    return rows

def main():
    e.preflight()
    result=dict(status='PASS_SYNTHETIC_ORDER_EXPLORATION',ordering=explore(),fault_policy_table=faults(),
      assumptions=['A future gate atomically rejects NEW captures before exposure acceptance.',
        'Previously accepted captures retain permission to send ALL continuations.',
        'The future exposure ledger knows expected members and seals production.',
        'Other storage actors and lifecycle transitions use the same ownership protocol.',
        'These hooks and the ledger do not exist in the current firmware.'],
      limits=['Finite synthetic schedule exploration, not a camera or RTOS proof.',
        'No upper bound on actual native I/O or drain time is assumed.',
        'Fault rules are design expectations, not native recovery observations.'])
    e.save('protocol-model.json',result)
    print(json.dumps(dict(status=result['status'],ordering=result['ordering'],
        fault_policy_rows=len(result['fault_policy_table'])),indent=2))

if __name__=='__main__':main()
