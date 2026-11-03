#!/usr/bin/env python3
"""Bounded official-instruction replay. No RTOS, media or camera execution."""
from pathlib import Path
import importlib.util
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collect

spec = importlib.util.spec_from_file_location('r3_native_base', collect.ROOT / 'research/user_storage_r2/host_native.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)

class Stop(Exception):
    pass

class CPU(native.CPU):
    def __init__(self, program):
        super().__init__(program)
        self.control = {'spu': 0x206e0000}

    def op(self, name, args, pc):
        if name == 'neg':
            self.visits.append(pc)
            self.r[native.p.reg(args[0])] = -self.r[native.p.reg(args[1])] & 0xffffffff
            return
        if name == 'srai':
            self.visits.append(pc)
            d = native.p.reg(args[0])
            self.r[d] = native.signed(self.r[d]) >> int(args[1].lstrip('#'), 0) & 0xffffffff
            return
        if name == 'mvfc' and args[1] in self.control:
            self.visits.append(pc)
            self.r[native.p.reg(args[0])] = self.control[args[1]]
            return
        if name == 'mvtc' and args[1] in self.control:
            self.visits.append(pc)
            self.control[args[1]] = self.r[native.p.reg(args[0])]
            return
        return super().op(name, args, pc)

def stop(c):
    raise Stop()

def run_until(c, address, stops, args=(), regs=None):
    entry_sp = c.r[15]
    for target in stops:
        c.stubs[target] = stop
    if regs:
        for r, value in regs.items():
            c.r[r] = value & 0xffffffff
    try:
        c.call(address, args, bound=100000)
    except Stop:
        # Each kernel fragment is entered with a fresh synthetic trap frame.
        # Only RAM persists; scheduler/trap return is outside this model.
        c.r[15] = entry_sp
        return
    raise AssertionError('expected boundary not reached')

def fixture(program, task=6):
    c = CPU(program)
    c.psw = 0x8000
    c.seed(0x200d1838, task, 2)
    c.seed(0x200d0ea8+4, 0)
    c.seed(0x200d0eb4, 0)
    c.seed(0x200d1842, 0, 1)
    c.seed(0x200d1c88, 0, 2)
    c.seed(0x200d211a, 0, 2)
    marker = -(0x13f+47)
    for base in (0x200d1c2e, 0x200d20c0):
        c.seed(base+2*marker, marker, 2)
        c.seed(base+2*task, task, 2)
    c.seed(0x200d2594+4*(task-1), 0)
    return c

def kernel_create(program):
    c = fixture(program)
    param = 0x20640000
    c.seed(param, 0)
    c.seed(param+4, 1)
    c.seed(param+8, 1)
    run_until(c, 0x05003adc, [0x0500c784], regs={1:47, 2:param})
    assert c.read(0x200d2ab0+2*46, 2) == 1
    assert c.read(0x200d0f58+2*46, 2) == 1
    return c

def kernel_cases(program):
    rows = []
    c = kernel_create(program)
    rows.append({'case':'kernel_create_sem47', 'initial':1, 'maximum':1})
    c.psw = 0x8000
    run_until(c, 0x0500a514, [0x0500c784], regs={1:47, 4:10000})
    assert c.read(0x200d2ab0+92,2) == 0
    assert 0x0500a818 in c.visits
    rows.append({'case':'first_acquire_decrements_count', 'task':6, 'count':0})
    c.psw = 0x8000
    run_until(c, 0x0500a514, [0x0500c784], regs={1:47, 4:10000})
    marker = -(0x13f+47)
    assert c.read(0x200d1c2e+2*marker,2) == 6
    assert c.read(0x200d2224+4*5) == 10001
    assert c.read(0x200d2594+4*5) & 4
    rows.append({'case':'same_task_second_acquire_queues', 'task':6, 'count':0,
        'waiter':6, 'timeout_request':10000, 'timeout_slot':10001, 'scheduler_boundary':'0x0500c784',
        'limits':'No elapsed time, timeout delivery or scheduling replay.'})
    frame = 0x206d0000
    c.seed(0x200d2224+4*5,1)
    c.seed(0x200d2174+4*5,frame)
    c.seed(frame+16,0)
    c.seed(c.r[15],0x8000)
    run_until(c,0x050087dc,[0x05008a2c])
    assert native.signed(c.read(frame+16)) == -50
    assert c.read(0x200d2ab0+92,2) == 0
    rows.append({'case':'semaphore_wait_expiry_writes_minus50','saved_return':-50,'count':0,
        'limits':'Actual timer-list expiry instructions, with remaining timeout set to one tick and a synthetic saved frame. Interrupt entry, real elapsed time and rescheduling are not replayed.'})
    c = kernel_create(program)
    c.psw = 0x8000
    run_until(c, 0x0500a514, [0x0500c784], regs={1:47, 4:10000})
    c.psw = 0x8000
    run_until(c, 0x0500a514, [0x0500c784], regs={1:47, 4:0})
    assert native.signed(c.read(c.control['spu']+16)) == -50
    rows.append({'case':'busy_semaphore_zero_timeout_returns_minus50','saved_return':-50,
        'limits':'Zero-timeout path only; finite-time timeout delivery is not replayed.'})
    c = kernel_create(program)
    c.psw = 0x8000
    run_until(c, 0x0500a514, [0x0500c784], regs={1:47, 4:10000})
    c.seed(0x200d1838, 8, 2)
    c.psw = 0x8000
    run_until(c, 0x0500740c, [0x0500c784], regs={1:47})
    assert c.read(0x200d2ab0+92,2) == 1
    rows.append({'case':'different_task_can_signal', 'acquiring_task':6, 'signalling_task':8, 'count':1})
    c = kernel_create(program)
    c.psw = 0x8000
    run_until(c, 0x0500740c, [0x0500c784], regs={1:47})
    assert c.read(c.control['spu']+16) == (0xffffffff-42)
    assert c.read(0x200d2ab0+92,2) == 1
    rows.append({'case':'signal_at_maximum', 'saved_return':-43, 'count':1})
    return rows

def wrapper_cases(program):
    rows = []
    for address, target, args in (
        (0x0500d4cc,0x2005e228,(47,0,1,1)),
        (0x0500d4e4,0x2005e360,(47,10000)),
        (0x0500d4fc,0x2005e31c,(47,))):
        c = CPU(program)
        native.stub(c,target,'rtos_boundary',value=-50)
        result = c.call(address)
        assert c.trace[0]['args'][:len(args)] == list(args)
        assert result == -50
        rows.append({'case':'lock_wrapper_parameters', 'entry':hex(address), 'target':hex(target),
            'args':list(args), 'return':result, 'boundary':'RTOS wrapper stub'})
    for lock_result in (0,-25,-50):
        c = CPU(program)
        c.seed(0x204c8668,0)
        native.stub(c,0x0500d4e4,'lock',value=lock_result)
        native.stub(c,0x0500d4fc,'unlock')
        native.stub(c,0x200a531c,'path')
        native.stub(c,0x200a65f8,'lower_open',value=-1)
        result = c.call(0x200a40b4,(0x20640000,0))
        assert [r['name'] for r in c.trace] == ['lock','path','lower_open','unlock']
        assert result == -1
        rows.append({'case':'open_ignores_lock_result', 'lock_result':lock_result,
            'trace':c.trace, 'return':result, 'limits':'Lower open is an error-returning stub; no device I/O.'})
        c = CPU(program)
        c.seed(0x204c8668,0)
        native.stub(c,0x0500d4e4,'lock',value=lock_result)
        native.stub(c,0x0500d4fc,'unlock')
        native.stub(c,0x200a531c,'path')
        native.stub(c,0x200a554c,'lower_create',value=-1)
        result = c.call(0x200a41ac,(0x20640000,0,512,512))
        assert [r['name'] for r in c.trace] == ['lock','path','lower_create','unlock']
        assert result == -1
        rows.append({'case':'photo_create_ignores_lock_result','lock_result':lock_result,
            'trace':c.trace,'return':result,'limits':'Shared factory create wrapper; lower create is a stub.'})
    for lock_result in (0,-50):
        c = CPU(program)
        c.seed(0x200d80b8,1)
        native.stub(c,0x0500d4e4,'lock',value=lock_result)
        native.stub(c,0x0500d4fc,'unlock')
        native.stub(c,0x200aa7e8,'lower_format',value=-1)
        assert c.call(0x200a3e64,(0,)) == -1
        assert [r['name'] for r in c.trace] == ['lock','lower_format','unlock']
        rows.append({'case':'format_ignores_lock_result','lock_result':lock_result,
            'trace':c.trace,'limits':'Format core is an error-returning stub. No format or media access occurs.'})
    return rows

def message_cases(program):
    rows = []
    for code, expected in ((0x1f02,0),(0x1f03,1),(0x1f04,3),(0x1f08,4),
                           (0x1f09,6),(0x1f0a,7),(0x1f0b,8),(0x1f12,10),(0x7ffe,9)):
        c = CPU(program)
        c.seed(0x204f41ba,code,2)
        c.seed(0x204f41c4,1)
        c.seed(0x204f41c8,1)
        result = c.call(0x2010e094)
        assert result == expected
        rows.append({'case':'storage_message_classification','message':hex(code),'event':result})
    for code in (0x1f04,0x1f09):
        c = CPU(program)
        c.seed(0x204f41ba,code,2)
        c.seed(0x204f41c4,7)
        c.seed(0x204f41c8,7)
        result = c.call(0x2010e094)
        assert result == (2 if code==0x1f04 else 5)
        rows.append({'case':'storage_message_type7_classification','message':hex(code),'event':result})
    return rows

def dispatch_cases(program):
    rows = []
    table = 0x201427b4
    for code, event, state, target in (
        (0x1f03,1,1,0x2010e5c8), (0x1f03,1,2,0x2010e5c8),
        (0x1f0b,8,1,0x20111810), (0x1f12,10,1,0x2010e064),
        (0x7ffe,9,1,0x201106d4), (0x7ffe,9,2,0x201106d4)):
        c = CPU(program)
        c.seed(0x204f41e8,state,1)
        c.seed(0x204f41ea,0,1)
        c.seed(0x204f41c4,1)
        seen = []
        def receive(cc):
            if seen:
                raise Stop()
            cc.seed(0x204f41ba,code,2)
            seen.append('received')
            return 48
        native.stub(c,0x20109b28,'receive_boundary',hook=receive)
        native.stub(c,0x2005ff88,'scheduler_hint_boundary')
        assert c.read(table+12*event+4*state) == target
        if target not in (0x201106d4,0x2010e064):
            native.stub(c,target,'selected_handler_boundary',value=state)
        try:
            c.call(0x2010de04,bound=10000)
        except Stop:
            pass
        else:
            raise AssertionError('second receive was not reached')
        assert target in c.visits or target in c.calls
        final = c.read(0x204f41e8,1)
        assert final == (0 if target == 0x201106d4 else state)
        rows.append({'case':'task8_dispatch','message':hex(code),'event':event,'initial_state':state,
            'handler':hex(target),'final_state':final, 'trace':c.trace,
            'limits':'Single loop with synthetic message delivery; named job and scheduler boundaries are stubs.'})
    return rows

def constructor_cases(program):
    rows = []
    for state in (0,1,2):
        c = CPU(program)
        c.seed(0x204f41e8,state,1)
        c.seed(0x205d9bf8,8)
        native.stub(c,0x20372d30,'ui_helper_boundary',value=1)
        run_until(c,0x202be220,[0x202be24c])
        assert c.read(0x204f41e8,1) == state
        rows.append({'case':'H06_entry_has_no_local_storage_check','storage_state':state,'reached':'0x202be24c',
            'limits':'Constructor-local reachability only. Earlier UI event admission and physical menu reachability are not replayed.'})
        c = CPU(program)
        c.seed(0x204f41e8,state,1)
        run_until(c,0x202bb960,[0x202bb968],regs={3:8})
        rows.append({'case':'H08_image_branch_has_no_local_storage_check','storage_state':state,'reached':'0x202bb968',
            'limits':'Image branch only, native r3=8 is supplied; earlier event/dispatcher predicates are outside this case.'})
    return rows

def ui_pump_cases(program):
    rows = []
    for paused in (0,1):
        c = CPU(program)
        c.seed(0x201bc1d0,paused)
        c.seed(0x204f41e8,2,1)
        c.seed(0x204c8668,1)
        if paused:
            run_until(c,0x20332c58,[0x2005de00],args=(0x20640000,0xffffffff))
            assert c.r[4] == 100
            target = 'native_delay_boundary'
        else:
            native.stub(c,0x2037280c,'receive_boundary',value=42)
            assert c.call(0x20332c58,(0x20640000,0xffffffff)) == 42
            target = 'receive_boundary'
        rows.append({'case':'ui_pump_pause_flag_is_not_storage_state','pause_flag':paused,
            'storage_state':2,'file_count':1,'reached':target,
            'limits':'Predicate-local fixture. No claim that the entire camera menu is reachable in this seeded state.'})
    return rows

def job_boundary_cases(program):
    rows = []
    c = CPU(program)
    observed = []
    def create_queue(cc):
        observed.append({'boundary':'create_message_buffer','args':cc.r[4:8],
            'buffer':hex(cc.read(cc.r[15]))})
        return 0
    def create_task(cc):
        observed.append({'boundary':'create_task','args':cc.r[4:8]})
        return 0
    native.stub(c,0x2005df34,'rtos_create_message_buffer',hook=create_queue)
    native.stub(c,0x2005d924,'rtos_create_task',hook=create_task)
    assert c.call(0x20109a04) == 0
    assert observed == [
        {'boundary':'create_message_buffer','args':[2,0,140,12320],'buffer':'0x204f0cdc'},
        {'boundary':'create_task','args':[8,0x2010ddc4,70,10240]}]
    assert [c.read(a) for a in (0x204f0cc4,0x204f0cc8,0x204f0ccc,0x204f0cd0)] == [2,1,15,6]
    rows.append({'case':'storage_queue_and_task_creation','observed':observed,
        'limits':'RTOS create calls stop at their argument boundaries; no real task is created.'})
    for entry, extras, expected in (
        (0x20109bb4,[],{28:0,36:0,40:0}),
        (0x20109c44,[0x20660000],{28:0,32:0x20660000,36:0,40:0}),
        (0x20109cdc,[0x20660000,0x200,0x20670000,0x20680000],
            {28:0,32:0x20670000,36:0x20680000,40:0x20660000,44:0x200})):
        c = CPU(program)
        c.seed(0x204f0cc4,2)
        c.seed(0x204f0c90,123)
        for i, value in enumerate(extras):
            c.seed(c.r[15]+4*i,value)
        captured = []
        def send(cc):
            msg = cc.r[5]
            captured.append({'queue':cc.r[4], 'bytes':cc.r[6], 'mode':cc.r[7],
                'u16':{str(k):cc.read(msg+k,2) for k in (0,2,6)},
                'u32':{str(k):cc.read(msg+k) for k in (12,16,20,24,*expected)}})
            return 0
        native.stub(c,0x20069490,'native_mode_boundary',value=0)
        native.stub(c,0x20396594,'native_submit_admission_boundary',value=1)
        native.stub(c,0x2010ac50,'native_send_boundary',hook=send)
        assert c.call(entry,(28,22,0x20650000,4096)) == 0
        assert len(captured) == 1
        packet = captured[0]
        assert packet['queue'] == 2 and packet['bytes'] == 48
        assert packet['u16'] == {'0':48,'2':28,'6':0x1f03}
        assert {k:packet['u32'][str(k)] for k in (12,16,20,24)} == {
            12:123,16:22,20:0x20650000,24:4096}
        assert {k:packet['u32'][str(k)] for k in expected} == expected
        assert c.read(0x204f0c90) == 124
        rows.append({'case':'native_photo_builder_payload','entry':hex(entry),'packet':packet,
            'limits':'Admission/mode/send are named boundary stubs. Payload addresses are fixtures, not real image buffers.'})
    for origin, queue, destination in ((28,15,28),(17,6,17)):
        c = CPU(program)
        c.seed(0x204f0ccc,15)
        c.seed(0x204f0cd0,6)
        message = 0x20640000
        c.seed(message+2,origin,2)
        captured = []
        def send_completion(cc):
            msg = cc.r[5]
            captured.append({'queue':cc.r[4],'bytes':cc.r[6],
                'origin':cc.read(msg+2,2),'destination':cc.read(msg+4,2),
                'message':hex(cc.read(msg+6,2)),'payload12':cc.read(msg+12)})
            return 0
        native.stub(c,0x2010ac50,'native_completion_send_boundary',hook=send_completion)
        assert c.call(0x2010a638,(message,0x12345678)) == 0
        assert captured == [{'queue':queue,'bytes':48,'origin':8,'destination':destination,
            'message':'0x1003','payload12':0x12345678}]
        rows.append({'case':'native_photo_completion_route','request_origin':origin,
            'completion':captured[0],'limits':'Checks message construction only; no consumer, durability or success semantics assumed.'})
    return rows

def photo_tail_case(program):
    c = CPU(program)
    c.seed(0x204f41e8,2,1)
    c.seed(0x204f41d8,0)
    run_until(c,0x2010ef0c,[0x20117264],regs={8:0,12:22,13:0x20650000})
    assert c.read(0x204f41e8,1) == 1
    assert 0x2010ef14 in c.visits and 0x2010ef68 in c.visits
    return [{'case':'storage_state1_precedes_photo_job_postprocessing','format':22,
        'state':1,'reached':'0x20117264',
        'limits':'Job-tail fragment starts after close; it proves state 1 does not imply handler return. DCF/physical writes at the postprocessing boundary are not replayed.'}]

def main():
    collect.preflight()
    program = native.Program()
    rows = (wrapper_cases(program) + kernel_cases(program) + message_cases(program)
            + dispatch_cases(program) + constructor_cases(program) + ui_pump_cases(program)
            + job_boundary_cases(program) + photo_tail_case(program))
    result = {'status':'PASS_BOUNDED_OFFICIAL_INSTRUCTIONS','cases':rows,
        'limitations':['No camera, disk, firmware execution, interrupts or concurrent scheduling.',
            'Kernel stops at scheduler entry; semaphore/task RAM is a synthetic fixture.',
            'Open timeout results are explicit boundary injections, not measured device timeouts.']}
    collect.save('replay-results.json',result)
    print('PASS',len(rows),'bounded instruction cases')

if __name__ == '__main__':
    try:
        main()
    except Exception:
        import hashlib
        import traceback
        raw = traceback.format_exc()
        collect.preflight()
        collect.save('failure-'+hashlib.sha256(raw.encode()).hexdigest()[:12]+'.json', {'error':raw})
        raise
