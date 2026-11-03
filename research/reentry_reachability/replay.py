"""Replay the native key producer and message construction in one host process."""
from pathlib import Path
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit


def main():
    audit.preflight()
    sources=['tools/native_harness/python_backend.py','tools/native_harness/backend_api.py',
        'tools/native_harness/image_loader.py','research/emulator_feasibility_r1/prototype/boot_probe.py']
    identities=[dict(path=rel,sha256=audit.digest(audit.ROOT/rel)) for rel in sources]
    previous=audit.OUT/'replay-inputs.json'
    if previous.exists():assert json.loads(previous.read_text())==identities,'replay source changed'
    else:audit.save('replay-inputs.json',identities)
    sys.path.insert(0,str(audit.ROOT/'tools/native_harness'))
    import python_backend
    from image_loader import Image
    python_backend.CACHE=audit.LOCAL/'replay-decode'
    b=python_backend.PythonBackend()
    image=Image(audit.ROOT/audit.IMAGES['v36'][0],audit.IMAGES['v36'][1])
    image.load(b)
    b.map(0x20600000,bytes(0x20000))
    b.map(0x206e0000,bytes(0x10000))
    end=0x2061fff0
    def u(pc,size=4):return int.from_bytes(b.read(pc,size),'big')
    def put(pc,value,size=4):b.write(pc,value.to_bytes(size,'big'))
    visits=[]
    for pc in (0x202b1100,0x202c25b8,0x202c2880,0x202bb968,0x20268768,0x20268774):
        b.add_breakpoint(pc,lambda cpu,pc=pc:visits.append(pc) or False)
    modeled=[]
    notifications=[]
    def boundary(pc,name,callback):
        def hit(cpu):
            modeled.append(dict(pc=pc,name=name,args=list(cpu.core.r[4:8])))
            result=callback(cpu)
            cpu.set_reg('r0',result&0xffffffff)
            cpu.pc=cpu.core.r[14]
            return False
        b.add_breakpoint(pc,hit)
    for pc,name in ((0x20060bb4,'event_mutex_enter'),(0x20060c10,'event_mutex_leave'),
                    (0x2005ff88,'gear_accounting')):
        boundary(pc,name,lambda cpu:0)
    boundary(0x2005f164,'time_value',lambda cpu:0x1234)
    boundary(0x2005f1cc,'task_number_fixture',lambda cpu:3)
    boundary(0x200694a0,'mode_policy_default_branch',lambda cpu:-1)
    def send(cpu):
        notifications.append(dict(queue=cpu.core.r[4],size=cpu.core.r[6],wait=cpu.core.r[7],
            contents=cpu.read(cpu.core.r[5],cpu.core.r[6]).hex()))
        return 0
    boundary(0x2005e034,'message_buffer_send',send)
    def run(pc,args):
        b.set_reg('r15',0x206eff00)
        b.core.psw=0xc0
        for i,value in enumerate(args):b.set_reg('r'+str(4+i),value)
        result=b.call(pc,(),end,200000)
        assert result.reason=='return',(hex(pc),result)
        assert b.get_reg('r15')==0x206eff00,hex(pc)
        return b.get_reg('r0')
    rows=[]
    for key,base_event in ((0x0f,2),(0x10,3)):
        for phase,expected in ((1,base_event+29),(2,base_event+87),(0,base_event+58)):
            controller=0x204a9e88
            definitions=0x20600000
            item=0x20600100
            node=0x20600200
            free=0x20414bbc
            head=0x20412ba0
            event=0x20600800
            message=0x20600900
            b.write(controller,bytes(0xb80))
            b.write(definitions,bytes(0x200))
            put(controller,definitions)
            put(definitions,item)
            put(controller+4,1)
            put(controller+24+4,key)
            put(controller+24+16,1 if phase==2 else phase)
            put(controller+24+20,1000 if phase==2 else 0)
            for pc,value in ((head,head),(head+4,head),(head+12,0x2006929c),(head+16,0),
                             (free,node),(free+4,node),(node,free),(node+4,free),
                             (0x2041289c,1),(0x204128a0,600),(0x204128a4,400)):
                put(pc,value)
            notifications.clear();visits.clear();modeled.clear()
            producer=run(0x20071fc0,(controller,0))
            assert producer==0 and len(notifications)==1
            assert notifications[0]==dict(queue=1,size=2,wait=0,contents='0000')
            node_fields=[u(node+i) for i in (8,12,16,24,28)]
            assert node_fields[0]==2 and node_fields[1]>>24==key
            popped=run(0x2006aab8,(event,0))
            assert popped==0
            constructed=run(0x20069018,(event,message))
            assert constructed==0 and u(message+6,2)==0x700b,(key,phase,constructed,node_fields)
            assert u(message+12)==key and u(message+16)==phase
            # Run the literal default key-map loop only. Its surrounding mode
            # selection and later UI dispatch are deliberately outside this slice.
            b.set_reg('r10',message)
            b.set_reg('r11',0)
            b.set_reg('r9',0)
            slice_end=0x202b001c
            b.add_breakpoint(slice_end,lambda cpu:True)
            stop=b.call(0x202affa4,(),end,10000)
            assert stop.reason=='breakpoint' and stop.pc==slice_end,stop
            logical=b.get_reg('r9')
            assert logical==expected,(key,phase,logical,expected)
            b.breakpoints.pop(slice_end)
            assert not visits,visits
            rows.append(dict(key=key,phase=phase,logical_event=logical,node_fields=node_fields,
                queue_notification=notifications[0],message=b.read(message,24).hex(),
                watched_native_entries=visits,modeled_boundaries=list(modeled)))
    result=dict(status='PASS_HOST_FRAGMENTS',image_sha256=image.sha256,cases=rows,
        limitation='Synthetic HID records, event-list setup, mutex/time/gear/send/mode-policy boundaries; no RTOS task creation, scheduling, actual GPIO or camera execution.')
    audit.save('local/key-fragments.json',result)
    print(json.dumps(dict(status=result['status'],cases=len(rows),logical_events=[r['logical_event'] for r in rows],
        queue=1,notification_bytes=2,rtos_scheduling=False)))


if __name__=='__main__':main()
