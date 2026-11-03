"""Observe original RTOS state from an existing offline checkpoint."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study
sys.path.insert(0, str(study.ROOT/'tools/gxr_emulator'))
from backend import REGS
from speed_snapshot import load

LOCK = 0x204104f0
SEM = 0x200d2ab0+2*54
END = 0x00dff000


def integer(cpu, address, count=4):
    return int.from_bytes(cpu.read(address, count), 'big')


def context(machine):
    cpu = machine.cpu
    address = integer(cpu, 0x200c0dac)
    return dict(task=machine.task(), pc=hex(cpu.get_reg('pc')),
                psw=hex(cpu.get_reg('psw')), sp=hex(cpu.get_reg('r15')),
                count=integer(cpu, LOCK), semaphore_id=integer(cpu, LOCK+4),
                semaphore_count=integer(cpu, SEM, 2),
                s_address=hex(address), mode=integer(cpu,address+0x36e,1),
                wb=[integer(cpu,address+0x6dd,1),integer(cpu,address+0x6de,1)],
                power_state=integer(cpu, 0x20412ad0),
                power_flags=integer(cpu, 0x20412ad8), steps=cpu.steps)


def native_call(machine, address, args, bound=100000):
    cpu = machine.cpu
    saved = {key:cpu.get_reg(key) for key in REGS if key not in ('sp','lr','fp')}
    before = context(machine)
    for index, value in enumerate(args, 4):
        cpu.set_reg('r'+str(index), value)
    stop = cpu.call(address, [], END, bound)
    row = dict(entry=hex(address), args=args, before=before, after=context(machine),
                result=cpu.get_reg('r0'), stop=stop.to_dict(),
                stack_equal=cpu.get_reg('r15')==saved['r15'])
    if stop.reason == 'return':
        cpu.set_reg('psw', saved['psw'])
        for key,value in saved.items():
            if key != 'psw':
                cpu.set_reg(key,value)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('census','locks','power','wait'))
    parser.add_argument('--task6', action='store_true')
    args = parser.parse_args()
    path = study.ROOT/'tools/gxr_emulator/local/speed/no-card.snap.z'
    if not path.exists():
        candidates = list(path.parent.glob('no-card.snap.*'))
        path = next(p for p in candidates if p.suffix != '.json')
    machine, metadata = load(path, allow_idle_task=True)
    try:
        cpu = machine.cpu
        rows = []
        if args.task6:
            machine.panel.set_key('OK', True)
            def on_event(c):
                return machine.task()==6 and bool(c.get_reg('psw')&0x80)
            machine.observer.breakpoint(0x202b0b18, on_event)
            stop = cpu.run(2000000)
            rows.append(dict(case='task6_event', stop=stop.to_dict(), context=context(machine)))
            if stop.reason != 'breakpoint':
                study.save('probe-'+args.action+'-task6.json',dict(status='INCOMPLETE',rows=rows))
                print(json.dumps(dict(status='INCOMPLETE',stop=stop.to_dict())))
                return
        initial = context(machine)
        if args.action=='wait':
            for timeout in (0,1):
                row = native_call(machine,0x2005e360,[55,timeout],bound=350000)
                assert row['stop']['reason']=='return' and row['result']==0xffffffce
                assert row['after']['count']==0xffffffff and row['after']['semaphore_count']==0
                rows.append(row)
        elif args.action=='locks':
            rows.append(native_call(machine,0x20060bb4,[LOCK]))
            assert rows[-1]['after']['count']==0
            rows.append(native_call(machine,0x20060c10,[LOCK]))
            assert rows[-1]['after']['count']==0xffffffff
            rows.append(native_call(machine,0x20060bb4,[LOCK]))
            rows.append(native_call(machine,0x20060bb4,[LOCK],bound=300000))
        elif args.action=='power':
            def at_save(c):
                rows.append(dict(case='save_entry',context=context(machine),
                                 lr=hex(c.get_reg('lr'))))
                return True
            machine.observer.breakpoint(0x20067bb4,at_save)
            rows.append(native_call(machine,0x2006a0f4,[1<<27],bound=300000))
        result = dict(status='OBSERVED', initial=initial, rows=rows,
                      checkpoint=str(path.relative_to(study.ROOT)),
                      checkpoint_sha256=study.sha(path), accepted=metadata['accepted'],
                      image_sha256=machine.image.sha256,
                      task_entries={str(k):hex(v) for k,v in machine.observer.task_entries.items()},
                      limits='Host-initiated bounded function calls after checkpoint restore; not a power-key flow or cold boot.')
        name = 'probe-'+args.action+('-task6' if args.task6 else '')+'.json'
        study.save(name,result)
        print(json.dumps(dict(status='OBSERVED',initial=initial,rows=rows)))
    finally:
        machine.close()


if __name__ == '__main__':
    main()
