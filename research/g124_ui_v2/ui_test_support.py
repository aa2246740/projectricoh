"""Observe compiled UI state; drive only native constructors and native keys."""
from pathlib import Path
import json
from support import *
from algorithm_check import Algorithm, unpack, effect

SCREENS = ('L1','card','items','value','groups','entries','ERR')

class Session:
    def __init__(self, unit='50mm', tag='ui', dat=None):
        self.unit=unit
        self.ux,self.m,self.fr,self.pe,self.v=setup(unit=unit,tag=tag)
        if dat:
            path=Path(dat)
            self.m.DAT=self.pe.STAGED=path
            self.pe.STAGED_SHA=file_sha(path)
        from runtime_guard import install
        install(self.v)
        self.h,self.p,self.w=self.m.boot(unit)
        self.m.published(self.h,self.p,self.w)
        self.layout=json.loads((OUT/'local/layout/current-adapter-layout.json').read_text())
        self.adapter=self.p.symbol_pc('n')
        self.events=[]
        self.coverage=set()
        self.draws=[]
        self.ascii=[]
        self.h.b.add_breakpoint(self.p.symbol_pc('rv_native_ascii'),self._ascii)
        self.h.b.add_breakpoint(0x201ffb2c,self._draw)
        self.algorithm=Algorithm()

    def _ascii(self,b):
        label=b.read(b.core.r[0],b.core.r[1]).decode('ascii')
        assert 0<len(label)<=8 and all(32<=ord(c)<=126 for c in label),label
        self.ascii.append(label)
        if label.startswith('>'):
            self.match()
        return False

    def _draw(self,b):
        state=b.core.r[13]
        self.draws.append(dict(state=hex(state),marker=self.h.u(state+9,1),cursor=self.h.u(state+10,1),rows=self.h.u(0x2022f5ac,1)))
        return False

    def state(self):
        fields=('screen','cur','top','physical','count','slot','param','group','armed','applied_user')
        result={name:self.h.u(self.adapter+self.layout['ui.'+name],1) for name in fields}
        levels=self.h.b.read(self.adapter+self.layout['ui.levels'],11)
        result['levels']=[v-256 if v>=128 else v for v in levels]
        result['rows']=self.h.u(0x2022f5ac,1)
        result['native_cursor']=self.h.u(0x2022f726,1)
        result['cursor_cache']=self.h.u(0x205a2944,1)
        result['labels']=[self.h.b.read(self.adapter+self.layout['ui.text']+9*i,9).split(b'\0')[0].decode('ascii') for i in range(8)]
        result['failed']=self.h.u(self.adapter+self.layout['failed'],1)
        result['overlay']=self.h.u(0x2037f3bc)
        return result

    def press(self,key):
        before=self.state()
        self.coverage.add((SCREENS[before['screen']],key))
        at=len(self.p.rpc.log)
        draws=len(self.draws)
        if key in ('UP','DOWN'):
            result=self.fr.move_key(self.h,0x1f if key=='UP' else 0x20,steps=30000000)
        elif key=='DISP':
            result=self.fr.native(self.h,0x202be220,steps=30000000)
        elif key in ('OK','ADJ'):
            result=self.fr.press(self.h,0x23 if key=='OK' else 0x2b,steps=30000000)
        elif key=='HALF':
            result=self.fr.native(self.h,0x2029fdc4,(0x29,0),steps=30000000)
            self.ux.need(result)
            result=self.fr.native(self.h,0x202bd724,(0x29,0),steps=30000000)
        else:
            raise ValueError(key)
        self.ux.need(result)
        after=self.state()
        record=dict(key=key,before=before,after=after,result=result,RPC=len(self.p.rpc.log)-at,
                    W=sum(e['cmd']==22 for e in self.p.rpc.log[at:]),draws=self.draws[draws:])
        self.events.append(record)
        if after['rows']==8:
            assert after['native_cursor']==after['physical']+1==after['cursor_cache'],after
            assert after['cur']==after['top']+after['physical'],after
            assert 0<=after['cur']<after['count']<=33,after
            assert all(0<len(t)<=8 and all(32<=ord(c)<=126 for c in t) for t in after['labels']),after
        return after

    def goto(self,screen,row):
        assert self.state()['screen']==screen,self.state()
        for _ in range(70):
            state=self.state()
            if state['cur']==row:
                return state
            self.press('DOWN' if state['cur']<row else 'UP')
        raise AssertionError(('unreachable logical row',screen,row,self.state()))

    def open_numeric(self,param=0):
        assert self.state()['screen']==0
        self.press('DISP')
        self.press('DISP')
        self.goto(2,1+param)
        self.press('DISP')
        assert self.state()['screen']==3 and self.state()['param']==param

    def match(self,slot=None,levels=None):
        state=self.state()
        slot=slot or state['slot']
        levels=state['levels'] if levels is None else levels
        base,mapping=unpack(self.p.dat,self.m.INDEX[self.unit],slot)
        stock,_=unpack(self.p.dat,self.m.INDEX[self.unit],4)
        expected=self.algorithm.compute(base,stock,levels)
        digests=[]
        for i in range(9):
            desc=mapping[32+12*i:44+12*i]
            address,size,off=struct.unpack_from('>IHH',desc)
            actual=bytes((self.p.rpc.half(a&~1)>>(0 if a&1 else 8))&255 for a in range(address,address+size))
            assert actual==expected[off:off+size],(self.unit,slot,levels,i,sha(actual),sha(expected[off:off+size]))
            digests.append(sha(actual))
        assert self.p.rpc.t==int.from_bytes(expected[445:447],'big')
        return dict(base=slot,levels=levels,nine_rows_sha256=digests,T=self.p.rpc.t)

    def reopen(self):
        self.m.reopen(self.h,self.p,self.w)
        assert self.state()['screen']==0
        return self.state()

    def report(self):
        audit=ui_audit(self.h)
        assert not audit['host_ui_writes'] and not audit['getter_callback_present']
        return dict(dat_sha256=sha(self.p.dat),unit=self.unit,events=self.events,
                    key_coverage=sorted(self.coverage),ascii_labels=sorted(set(self.ascii)),
                    native_UI=audit,file_mutations=self.m.no_writes(self.p),rpc_log=self.p.rpc.log)

import struct
