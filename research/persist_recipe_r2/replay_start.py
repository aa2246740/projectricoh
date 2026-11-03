"""Replay original unit calibration readout with explicit stored data."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import study
from facts import UnitImage
sys.path.insert(0, str(study.ROOT/'tools/gxr_emulator'))
from backend import Backend

END = 0x00e00000


class UnitRig:
    def __init__(self, name):
        self.image = UnitImage(name)
        self.cpu = Backend(trace_limit=64, mode='fast')
        self.cpu.map(0x05000000,bytes(0x20000))
        self.cpu.map(0x20000000,bytes(0x1000000))
        for row in self.image.sections:
            self.cpu.write(row['address'],self.image.data[row['file']:row['file']+row['size']])
            if row['zero_size']:
                self.cpu.write(row['zero'],bytes(row['zero_size']))
        self.cpu.set_reg('r15',0x20700000)
        self.cpu.set_reg('psw',0)
        self.events = []

    def call(self, address, args=()):
        for index,value in enumerate(args,4):
            self.cpu.set_reg('r'+str(index),value)
        stop = self.cpu.call(address,[],END,500000)
        assert stop.reason=='return', stop.to_dict()
        return self.cpu.get_reg('r0')

    def model(self, address, label, action):
        def hit(cpu):
            args = [cpu.get_reg('r'+str(i)) for i in range(4,8)]
            self.events.append(dict(name=label,address=hex(address),args=args))
            action(args)
            cpu.set_reg('r0',0)
            cpu.set_reg('pc',cpu.get_reg('lr'))
            return False
        self.cpu.add_breakpoint(address,hit)


def main():
    rows = []
    facts = json.loads((study.OUT/'dat-unit-facts.json').read_text())['modules']
    for index, module in enumerate(facts):
        for control, damaged in ((2,False),(0,False),(0,True)):
            rig = UnitRig(module['name']+'3')
            try:
                cpu = rig.cpu
                base = int(module['initial_t_ram'],16)
                default_at = int(module['t_default_file'],16)
                stored = bytearray(rig.image.data[default_at:default_at+0x4000])
                stored[0] = 0xaa
                stored[0x2444:0x2446] = control.to_bytes(2,'big')
                cpu.write(base,stored)
                delta = 4 if index==2 else 0
                total = rig.call(0x2006595c+delta,[base])
                stored[-4:] = (total ^ int(damaged)).to_bytes(4,'big')
                def all_data(args):
                    assert args[:2]==[base,16384]
                    cpu.write(args[0],stored)
                def sector(args):
                    at = args[1]*512
                    assert 0 <= at < 16384
                    cpu.write(args[0],stored[at:at+512])
                read_all = 0x20075f3c+delta
                read_part = 0x20075f7c+delta
                rig.model(read_all,'unit_storage_read_model',all_data)
                rig.model(read_part,'unit_sector_read_model',sector)
                cpu.write(base,bytes(16384))
                value = rig.call(0x20065ccc+delta)
                actual = int.from_bytes(cpu.read(base+0x2444,2),'big')
                assert actual==(2 if damaged else control)
                assert value==(0xffffffff if damaged else 0)
                rows.append(dict(unit=module['name'],stored_control=control,
                                 damaged_checksum=damaged,actual_control=actual,result=value,
                                 entry=hex(0x20065ccc+delta),native_sum=total,
                                 storage_events=rig.events,firmware_sha256=module['firmware_sha256']))
            except Exception as exc:
                study.save('unit-start-progress.json',dict(completed=rows,
                           unit=module['name'],control=control,damaged=damaged,
                           events=rig.events,error=str(exc),
                           registers={key:rig.cpu.get_reg(key) for key in ('pc','lr','r0','r4','r5','r6','r15')}))
                raise
            finally:
                rig.cpu.close()
    study.save('unit-start-replay.json',dict(status='PASS_FUNCTION_REPLAY',cases=rows,
               limits='Original load, checksum and fallback instructions; unit storage reads are explicit models. No unit MONITOR or physical power cycle.'))
    print(json.dumps(dict(status='PASS_FUNCTION_REPLAY',cases=len(rows))))


if __name__=='__main__':
    main()
