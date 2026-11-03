"""g155 的主机入口。只在模型 RAM 装载 resident ELF，不生成机身映像。"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys
import types

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g155-boot-r1')
os.environ['TMPDIR']=str(TMP);sys.dont_write_bytecode=True
os.environ.setdefault('GXR_HARNESS_BACKEND','c')
sys.path.insert(0,str(ROOT/'tools/native_harness_c'))
import python_backend as PB
PB.CACHE=TMP/'decode'
assert Path(PB.__file__).parent==ROOT/'tools/native_harness_c'
if os.environ['GXR_HARNESS_BACKEND']=='c':assert PB.PythonBackend.native_api==5
import harness,field_replay,product_execute,engine_bridge
sys.path.insert(0,str(ROOT/'research/v39_g153'))
from dat_format import expand,expand_effect,CRC_FIELDS

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module

def adapted(path,name,replacements):
    source=Path(path).read_text()
    for old,new in replacements:
        assert source.count(old)>=1,(path,old);source=source.replace(old,new)
    mod=types.ModuleType(name);mod.__file__=str(path);sys.modules[name]=mod
    exec(compile(source,str(path),'exec'),mod.__dict__);return mod

H=load(ROOT/'research/v39_g153/tests/v39_host.py','g155_v39_host')
CONTROL=False
OVERLAY=True
H.LOCAL=TMP/'native'/str(os.getpid());H.TMP=H.LOCAL/'tmp'
H.PACKAGE=ROOT/'firmware/package_v310_g155_test'
H.DAT=H.PACKAGE/'GXRCE.DAT'
H.BODY=ROOT/'firmware/package_v39_g154/local/SD_ROOT/ilaunch3'
H.RESIDENT=HERE/'evidence/resident/neutral/resident.elf'
H.ENGINE=ROOT/'firmware/engine_v64_g155/candidate/local/boot-on/engine.elf'
H.LAYOUT=json.loads((HERE/'layout.json').read_text());H.UI=H.LAYOUT['ui'];H.setup=lambda:None
H.BODY_SHA=hashlib.sha256(H.BODY.read_bytes()).hexdigest()

def accepted():
    old=adapted(ROOT/'research/g135_v37/accept.py','g155_accept',[
        ("    h.b.add_breakpoint(h.symbols['rv_invoke'], image_entered)",
         "    if 'rv_invoke' in h.symbols:h.b.add_breakpoint(h.symbols['rv_invoke'], image_entered)")])
    old.HERE=H.LOCAL;old.PACKAGE=H.PACKAGE;old.BODY=H.BODY;old.DAT=H.DAT
    old.RESIDENT=H.RESIDENT;old.ENGINE=H.ENGINE;old.GENERATION=155;old.TAG=''
    old.freeze=lambda:None;old.save=lambda *a:None
    prior=old.load
    def loaded(path,name):
        if name!='accept_integration':return prior(path,name)
        mod=adapted(path,name,[
            ('        self.h.b.add_breakpoint(self.h.symbols["rv_header"], header_seen)',
             '        if "rv_header" in self.h.symbols:self.h.b.add_breakpoint(self.h.symbols["rv_header"], header_seen)'),
            ('h.b.visits[h.symbols["rv_load"]]','h.b.visits.get(h.symbols.get("rv_load"),0)')])
        from image_loader import Elf,Image as native
        elf=Elf(H.RESIDENT)
        patches=json.loads((HERE/'evidence/resident/neutral/patch-manifest.json').read_text())
        class ModelImage(native):
            def load(self,backend):
                super().load(backend)
                if not OVERLAY:return
                for section in elf.sections:
                    if section['flags']&2 and section['size']:backend.write(section['base'],section['data'])
                for patch in patches:backend.write(int(patch['address'],16),bytes.fromhex(patch['replacement']))
        mod.v.Image=ModelImage
        defaults=list(mod.v.V35Harness.__init__.__defaults__);defaults[1]=PB.PythonBackend
        mod.v.V35Harness.__init__.__defaults__=tuple(defaults)
        PB.CACHE=TMP/'decode'
        return mod
    old.load=loaded;return old
H.accept_module=accepted

class Camera(H.Camera):
    def __init__(self,unit,normal=True,dat=None):
        super().__init__(unit,normal,dat)
        raw=self.dat_path.read_bytes();offset=int.from_bytes(raw[132:136],'big')
        def code(event):
            address=self.h.u(0x20054770)
            if 0x20000000<=address<0x21000000:self.p.image_base=address-offset
        self.h.b.add_write_trace(0x20054770,0x20054774,code)
        PB.CACHE=TMP/'decode'
    def symbol(self,name):
        if name not in self.p.elf.symbols:
            found=[s for s in self.p.elf.symbols if s.startswith(name+'.')]
            assert len(found)==1,(name,found);name=found[0]
        return self.p.symbol_pc(name)
    def state(self):
        result=super().state();result['effect']=self.ui('effect');return result
    def engine_ref(self,which='current'):return self.engine_bytes(H.LAYOUT['g.'+which],56)
    def select_effect(self,number):self.goto(7+number);return self.check_frame()
    def select_user(self,number):self.goto(17+number);return self.check_frame()
    def open_looks(self):return self.check_frame()

def expected(cam,entry):return [entry[a:a+n] for a,n,_ in CRC_FIELDS],int.from_bytes(entry[445:447],'big')
def snapshot(cam):
    rows,t=cam.unit_rows();return dict(rows=rows,T=t,S=cam.s_bytes(0,4096),ref=cam.engine_ref() if cam.p.image_base else None,W=cam.writes())
def exit_menu(cam,kind):
    if kind=='ok':cam.press('OK')
    elif kind=='half':
        for address in (0x2029fdc4,0x202bd724):
            result=cam.m.fr.native(cam.h,address,(0x29,0),steps=30000000);assert result['ok'],result
    else:
        result=cam.m.fr.press(cam.h,0x29,steps=30000000);assert result['ok'],result

def boot(cam):
    h=cam.h
    h.b.write(0x205d9aa3,b'\0');h.b.write(0x205da00b,b'\0')
    return boot_current(cam)

def boot_current(cam):
    h=cam.h
    for value in (0,2,32,63,32):h.invoke(0x202b0a74,(value,),native=True,max_steps=100000)
    h.b.set_reg('r0',0x202b0a74);h.b.set_reg('r12',5)
    h.run_slice(0x2029ebc0,0x2029ebc4,100000)
    assert h.u(0x200547ec)==1
    h.b.set_reg('r0',0);h.run_slice(0x202b1310,0x202b1314,90000000)
    block=h.u(0x20054738)
    if not block:return dict(root=h.u(0x20054705,1),word=h.u(0x200547ec),status=None,detail=None)
    layout=json.loads((HERE/'evidence/resident/neutral/measurement.json').read_text())['layout']
    address=block+layout['RvSession']['offsets']['call_reply'];status=h.u(address+4)
    return dict(root=h.u(0x20054705,1),word=h.u(0x200547ec),status=status if status<2**31 else status-2**32,detail=h.u(address+28))
