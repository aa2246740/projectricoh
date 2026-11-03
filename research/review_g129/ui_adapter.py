"""Read the new UI fields and use the frozen r2 reference in retained checks."""
from pathlib import Path
import ctypes as ct
import dis
import hashlib
import json
import os
import struct
import subprocess

ROOT=Path(__file__).resolve().parents[2]
WORK=Path(__file__).resolve().parent

class Stats(ct.Structure):_fields_=[('v',ct.c_int32*7)]

def install(module):
    klass=getattr(module,'Session',None)
    if klass is None or getattr(klass,'review129_fields',False):return
    layout=json.loads((ROOT/'research/g129_knobs/adapter-layout.json').read_text())
    block=(ROOT/'firmware/kv2_modules/data_ui/local/gxkv2r2.bin').read_bytes()
    old_state=klass.state
    instructions=list(dis.get_instructions(old_state));hardware={}
    for index,item in enumerate(instructions):
        if item.opname!='LOAD_CONST' or type(item.argval) is not int or not 0x20000000<=item.argval<0x21000000:continue
        width=4
        if index+1<len(instructions) and instructions[index+1].opname=='LOAD_CONST' and instructions[index+1].argval in (1,2,4):width=instructions[index+1].argval
        hardware[item.argval]=width
    fields={'rows':0x2022f5ac,'native_cursor':0x2022f726,'cursor_cache':0x205a2944}
    remainder=set(hardware)-set(fields.values());assert len(remainder)==1
    fields['overlay']=remainder.pop()
    assert set(fields.values())==set(hardware)
    def state(self):
        h=self.h;b=h.b;n=self.adapter;ui=n+layout['ui']
        result={key:h.u(ui+layout['ui.'+key],1) for key in
                ('screen','cur','top','physical','count','slot','param','group','armed','applied_user')}
        result['levels']=list(struct.unpack('>10h',b.read(ui+layout['ui.levels'],20)))
        result.update({key:h.u(address,hardware[address]) for key,address in fields.items()})
        labels=[]
        for index in range(8):
            raw=b.read(ui+layout['ui.text']+9*index,9);assert 0 in raw
            text=raw.split(bytes(1),1)[0]
            if not (len(text)<=8 and all(32<=value<=126 for value in text)):
                (Path(module.OUT)/'state-field-counts.json').write_text(json.dumps({'text_length':len(text),'outside_ascii_count':sum(not 32<=value<=126 for value in text),'row':index,'adapter':n,'ui':ui,'candidate_hash_match_count':int(hashlib.sha256(self.p.dat).hexdigest()=='b58396748f1d5bba5ed480c1e7a81bc881a9df08968db2b778086c7c1a9cbf48'),'engine_n':self.p.symbol_pc('n'),'module_text_offset':self.layout.get('ui.text'),'module_ui_offset':self.layout.get('ui')},indent=2)+'\n')
            assert len(text)<=8 and all(32<=value<=126 for value in text)
            labels.append(text.decode('ascii'))
        result['labels']=labels;result['failed']=h.u(n+layout['failed'],1)
        return result
    def controls(unit,slot):
        recipe=block[64+16*(unit*8+slot-1):80+16*(unit*8+slot-1)]
        first=struct.unpack_from('>H',recipe,4)[0]
        return [block[448+16*index] for index in range(first,first+recipe[2])]
    from r2_oracle import reference_class
    Reference=reference_class(module.OUT)
    original_init=klass.__init__
    original_match=klass.match
    original_setup=original_init.__globals__['setup']
    def setup_current(*args,**kwargs):
        value=original_setup(*args,**kwargs)
        named=[]
        final_dat=ROOT/'firmware/package_v36_g129/SD_ROOT/GXRCE.DAT'
        assert hashlib.sha256(final_dat.read_bytes()).hexdigest()=='b58396748f1d5bba5ed480c1e7a81bc881a9df08968db2b778086c7c1a9cbf48'
        for constants in [*value,*original_init.__globals__.values()]:
            if not hasattr(constants,'__dict__'):continue
            fields={name:str(item) for name,item in vars(constants).items() if isinstance(item,(Path,str,int)) and name.isupper() and name in ('STAGED','STAGED_SHA','DAT','ELF')}
            if fields:named.append({'name':getattr(constants,'__name__',type(constants).__name__),'fields':fields})
            for name in ('DAT',):
                if isinstance(getattr(constants,name,None),Path):setattr(constants,name,final_dat)
            for name in ('ENGINE_ELF','ELF'):
                if isinstance(getattr(constants,name,None),Path):setattr(constants,name,ROOT/'firmware/engine_v49_knobs/candidate/local/full-r13/engine.elf')
            if hasattr(constants,'STAGED'):
                constants.STAGED=final_dat
                constants.STAGED_SHA='b58396748f1d5bba5ed480c1e7a81bc881a9df08968db2b778086c7c1a9cbf48'
        (Path(module.OUT)/'staged-field-names.json').write_text(json.dumps(named,indent=2)+'\n')
        return value
    original_init.__globals__['setup']=setup_current
    module.Algorithm=Reference
    original_init.__globals__['Algorithm']=Reference
    def initialize(self,*args,**kwargs):
        Reference.default_unit=kwargs.get('unit',args[0] if args else '50mm')
        (Path(module.OUT)/'session-input-names.json').write_text(json.dumps({'args_count':len(args),'keyword_names':list(kwargs),'dat_supplied_count':int(('dat' in kwargs and kwargs['dat'] is not None) or len(args)>2),'module_paths':{name:str(value) for name,value in vars(module).items() if isinstance(value,Path)},'original_paths':{name:str(value) for name,value in original_init.__globals__.items() if isinstance(value,Path)}},indent=2)+'\n')
        original_init(self,*args,**kwargs)
        assert int.from_bytes(self.p.dat[28:32],'big')==129 and len(self.p.dat)==89308
        self.algorithm=Reference()
        self.algorithm.unit=self.unit
        (Path(module.OUT)/'session-field-counts.json').write_text(json.dumps({'adapter':self.adapter,'engine_n':self.p.symbol_pc('n'),'candidate_hash_match_count':int(hashlib.sha256(self.p.dat).hexdigest()=='b58396748f1d5bba5ed480c1e7a81bc881a9df08968db2b778086c7c1a9cbf48'),'dat_generation':int.from_bytes(self.p.dat[28:32],'big'),'dat_bytes':len(self.p.dat),'module_text_offset':self.layout.get('ui.text'),'module_ui_offset':self.layout.get('ui')},indent=2)+'\n')
    def open_numeric(self,param=0):
        assert 0<=param<4
        control=(1,2,3,5)[param]
        if self.state()['screen']!=0:self.reopen()
        self.press('DISP')
        self.goto(1,1);self.press('DISP')
        current=self.state();unit={'50mm':0,'28mm':1,'mount':2}[self.unit]
        recipe=block[64+16*(unit*8+current['slot']-1):80+16*(unit*8+current['slot']-1)]
        display=list(recipe[6:6+recipe[2]]);assert control in display
        self.goto(2,1+display.index(control));self.press('DISP')
        assert self.state()['screen']==3 and self.state()['param']==control
    def match(self,slot=None,levels=None):
        self.algorithm.unit=self.unit
        self.algorithm.slot=self.state()['slot'] if slot is None else slot
        return original_match(self,slot,levels)
    klass.__init__=initialize;klass.state=state;klass.open_numeric=open_numeric;klass.match=match;klass.review129_fields=True
