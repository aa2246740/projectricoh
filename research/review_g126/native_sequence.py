"""Replay raw key messages and the original shooting dispatch instructions."""
import struct

def prepare_input(h):
    saved=list(h.b.core.r);saved_psw=h.b.core.psw
    h.b.map(0x20698000,bytes(0x8000))
    h.field_stack_ready=True
    h.b.set_reg('r15',0x2069f0a8)
    active=[True]
    h.b.add_breakpoint(0x202b1158,lambda b:None if active[0] else False)
    try:
        stop=h.b.call(0x202b1100,(),0x0bad0000,1000000)
        assert stop.reason=='breakpoint' and stop.pc==0x202b1158,stop
        assert h.b.core.r[15]==0x2069f000
        return dict(entry='0x202b1100',stop=hex(stop.pc),steps=stop.steps,stack=hex(h.b.core.r[15]))
    finally:
        active[0]=False;h.b.core.r=saved;h.b.core.psw=saved_psw

def device_edges(h,p):
    records=[]
    # Match the existing pixel-output model at two additional graphics leaves.
    h.stub(0x2016fdd4,'image_rectangle',value=0)
    h.stub(0x201d2204,'raster_text',value=0)
    h.stub(0x2005e360,'task_wait',value=0)
    original=list(h.b.breakpoints.get(0x2009005c,[]))
    def route(b):
        sp=b.core.r[15];slot=b.core.r[4]
        command=h.u(sp+4);value=h.u(sp+8)
        if slot==8 and command in (21,22,23):
            for callback in original:callback(b)
        else:
            records.append(dict(pc=hex(b.pc),slot=slot,command=command,value=value,return_address=hex(b.core.r[14]),result=0))
            b.core.r[0]=0;b.set_reg('pc',b.core.r[14])
        return False
    h.b.breakpoints[0x2009005c]=[route]
    return records

def open_image_from_adj(h, p, fr):
    h.stub(0x2005f454, 'event_flags', value=0)
    h.field_task_edges_ready = True
    before = h.u(h.settings+0x39f,1)
    moved = fr.native(h,0x202c1fd4)
    assert moved['ok'] and moved['r0']==1, moved
    assert h.u(h.settings+0x39f,1)==2
    h.parent()
    opened = fr.native(h,0x202ba5c8,(1,),steps=30000000)
    assert opened['ok'], opened
    fr.accelerate(p)
    assert h.u(0x205d9c00)==56 and h.u(0x205d9bf8)==8
    assert h.u(0x2022f5ac,1)==8
    return dict(initial_adj_slot=before,adj_slot=h.u(h.settings+0x39f,1),constructor=opened)

def raw_key(h, fr, raw, phase=1, kind=0x700b):
    address = 0x20690000
    if not getattr(h, 'field_message_ready', False):
        h.b.map(address, bytes(512))
        h.field_message_ready = True
    message = bytearray(140)
    struct.pack_into('>H', message, 6, kind)
    struct.pack_into('>II', message, 12, raw, phase)
    h.b.origin = 'model:key_message'
    h.b.write(address, message)
    flow=[];active=[True]
    for pc in (0x202affd8,0x202b001c,0x202b05d8,0x202b0654,0x202b0670,0x202b0744,0x202b09c4):
        def observe(b,pc=pc):
            if active[0]:flow.append(dict(pc=hex(pc),logical=b.core.r[9],counter=h.u(0x2037f814),camera=h.u(0x205d9b70,1)))
            return False
        h.b.breakpoints.setdefault(pc,[]).insert(0,observe)
    result = fr.native(h, 0x202afe98, (address,), steps=1000000)
    active[0]=False
    result['flow']=flow
    assert result['ok'], result
    return result['r0'], bytes(message), result

def dispatch(h, event, message):
    if not getattr(h, 'field_task_edges_ready', False):
        h.stub(0x2005f454, 'event_flags', value=0)
        h.field_task_edges_ready = True
    saved = list(h.b.core.r)
    saved_psw = h.b.core.psw
    sp = 0x2069f000
    if not getattr(h, 'field_stack_ready', False):
        h.b.map(0x20698000, bytes(0x8000))
        h.field_stack_ready = True
    h.b.origin = 'model:task_message'
    h.b.write(sp+28, message)
    h.b.set_reg('r15', sp)
    h.b.set_reg('r11', event)
    h.b.set_reg('r8', 0)
    h.b.set_reg('r9',0)
    h.b.set_reg('r10',0)
    h.b.set_reg('r13',1)
    before = h.b.total_steps
    try:
        if event == 0:
            return dict(ok=True, steps=0, next_event=0)
        try:
            h.run_slice(0x202b1160, 0x202b1360, max_steps=12000000)
        except RuntimeError as error:
            raise RuntimeError(str(error)+' registers='+repr(h.b.core.r)+' tail='+repr(list(h.b.tail)[-12:])) from error
        return dict(ok=True, steps=h.b.total_steps-before, next_event=h.b.core.r[11] if h.b.core.r[13] else 0,
                    task_exit=not bool(h.b.core.r[13]),task_result=h.b.core.r[10])
    finally:
        h.b.core.r = saved
        h.b.core.psw = saved_psw

def key(h, fr, raw, phase=1, kind=0x700b):
    event, message, converted = raw_key(h, fr, raw, phase, kind)
    results = []
    for _ in range(4):
        result = dispatch(h, event, message)
        results.append(result)
        if result['next_event'] == 0:
            break
        event = result['next_event']
    else:
        raise AssertionError('Native dispatch did not settle in four rounds')
    return dict(raw=raw, phase=phase, kind=kind, logical=converted['r0'], conversion=converted, dispatch=results)
