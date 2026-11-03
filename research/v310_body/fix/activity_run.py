#!/usr/bin/python3
"""Observe the native activity word from MAIN through ordinary panel input."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import cold_run as C
import panel


def main():
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument('--photo',action='store_true')
    extra,rest=parser.parse_known_args()
    sys.argv=[sys.argv[0],*rest]
    name=rest[rest.index('--name')+1]
    output=HERE/'evidence'/f'{name}-activity.json'
    assert not output.exists()
    events=[];controls=[];held={}
    Base=C.storage_run.Machine
    Panel=panel.Panel
    class NativePanel(Panel):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);held['panel']=self
    panel.Panel=NativePanel
    class ActivityMachine(Base):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            c=self.cpu
            def integer(at,n=4):return int.from_bytes(c.read(at,n),'big')
            self.integer=integer
            def event(label,**fields):
                row=dict(label=label,step=c.steps,pc=hex(c.get_reg('pc')),
                    activity=integer(0x205d9bf8),state=integer(0x205d9c00),
                    my=integer(0x205d9aa3,1),pending=integer(0x205da00b,1))
                row.update(fields)
                if len(events)<1000:events.append(row)
            self.event=event
            c.add_write_trace(0x205d9bf8,0x205d9bfc,lambda at,data:event('activity-write',writer=hex(c._pc)))
            c.add_write_trace(0x205d9c00,0x205d9c04,lambda at,data:event('state-write',writer=hex(c._pc)))
            for at,label in ((0x2029ebc0,'H50'),(0x202b1310,'H51'),(0x2028709c,'H01'),
                             (0x202afe98,'native-key')):
                prior=c.breakpoints.get(at)
                def observe(current,label=label,prior=prior):
                    old=prior(current) if prior else False
                    fields={}
                    if label=='native-key':
                        q=current.get_reg('r4')
                        if 0x20000000<=q<=0x207ffff0:
                            fields=dict(raw=integer(q+12),pressed=integer(q+16))
                    event(label,**fields)
                    return old
                c.add_breakpoint(at,observe)
        def close(self):
            c=self.cpu
            try:
                if extra.photo and self.integer(0x205d9c00)==5:
                    for key,down,budget in [('HALF',True,400000),('FULL',True,400000),
                                           ('FULL',False,700000),('HALF',False,700000)]:
                        self.event('physical-input',key=key,pressed=down)
                        held['panel'].set_key(key,down)
                        stop=c.run(budget)
                        controls.append(dict(key=key,pressed=down,steps=c.steps,stop=stop.to_dict()))
                        if stop.reason!='max_steps':break
            finally:
                self.event('final')
                output.write_text(json.dumps(dict(cold_origin=True,native_state_presets=[],
                    events=events,controls=controls,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2)+'\n')
                super().close()
    C.storage_run.Machine=ActivityMachine
    C.main()


if __name__=='__main__':main()
