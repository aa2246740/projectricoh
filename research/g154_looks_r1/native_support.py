"""复用 v3.9 的场景和按键驱动，明确选择 C 主机后端。"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g154-looks-r1')
os.environ['TMPDIR']=str(TMP)
sys.dont_write_bytecode=True
os.environ.setdefault('GXR_HARNESS_BACKEND','c')
sys.path.insert(0,str(ROOT/'tools/native_harness_c'))
import python_backend
python_backend.CACHE=TMP/'decode'
import harness,field_replay,product_execute,engine_bridge
sys.path.insert(0,str(ROOT/'research/v39_g153'))
from dat_format import expand,expand_effect,CRC_FIELDS


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


H=load(ROOT/'research/v39_g153/tests/v39_host.py','g154_v39_host')
CONTROL=os.environ.get('G154_CONTROL')=='g153'
H.LOCAL=TMP/'native'/('p'+str(os.getpid()))
H.TMP=H.LOCAL/'tmp'
H.PACKAGE=ROOT/('firmware/package_v39_g153_test/local/SD_ROOT' if CONTROL else 'firmware/package_v39_g154_looks18_test/local/SD_ROOT')
H.DAT=H.PACKAGE/'GXRCE.DAT';H.BODY=H.PACKAGE/'ilaunch3'
H.ENGINE=ROOT/('firmware/engine_v62_g153/candidate/local/full-r13/engine.elf' if CONTROL else 'firmware/package_v39_g154_looks18_test/local/build/engine.elf')
H.RESIDENT=ROOT/'research/v39_g153/local/body/local/resident/build/resident.elf'
H.LAYOUT=json.loads((ROOT/'research/v39_g153/layout.json' if CONTROL else HERE/'layout.json').read_text())
H.UI=H.LAYOUT['ui'];H.setup()
assert Path(python_backend.__file__).parent==ROOT/'tools/native_harness_c'
if os.environ['GXR_HARNESS_BACKEND']=='c':assert python_backend.PythonBackend.native_api==5


class Camera(H.Camera):
    def symbol(self,name):
        if name not in self.p.elf.symbols:
            matches=[s for s in self.p.elf.symbols if s.startswith(name+'.')]
            assert len(matches)==1,(name,matches);name=matches[0]
        return self.p.symbol_pc(name)

    def state(self):
        result=super().state();result['effect']=self.ui('effect');return result

    def engine_ref(self,which='current'):return self.engine_bytes(H.LAYOUT['g.'+which],56)

    def open_looks(self):
        if CONTROL:
            self.goto(8);self.press('DISP')
        else:assert self.ui('screen')==0
        return self.check_frame()

    def select_effect(self,number):
        if CONTROL:
            if self.ui('screen')!=7:
                self.goto(8);self.press('DISP')
            self.goto(number)
        else:
            assert self.ui('screen')==0,self.state();self.goto(7+number)
        return self.check_frame()

    def select_user(self,number):
        if CONTROL:
            entry=H.DAT_BYTES[self.dat_path][int.from_bytes(H.DAT_BYTES[self.dat_path][204:208],'big')+1408+1216+24*(number-1):][:24]
            self.goto(9);self.press('DISP');self.goto(entry[0]);self.press('DISP')
            users=int.from_bytes(H.DAT_BYTES[self.dat_path][int.from_bytes(H.DAT_BYTES[self.dat_path][204:208],'big')+1432:][:2],'big')
            positions=[i+1 for i in range(users) if H.DAT_BYTES[self.dat_path][int.from_bytes(H.DAT_BYTES[self.dat_path][204:208],'big')+2624+24*i]==entry[0]][::-1]
            self.goto(positions.index(number)+1)
        else:
            raw=H.DAT_BYTES[self.dat_path]
            shared=int.from_bytes(raw[192:196],'big')
            area=shared+int.from_bytes(raw[shared+64:shared+68],'big')
            count=int.from_bytes(raw[area+10:area+12],'big')
            self.goto(7+count+number)
        return self.check_frame()


def expected(cam,entry):
    return [entry[a:a+n] for a,n,_ in CRC_FIELDS],int.from_bytes(entry[445:447],'big')


def snapshot(cam):
    rows,t=cam.unit_rows()
    return dict(rows=rows,T=t,S=cam.s_bytes(0,4096),ref=cam.engine_ref() if getattr(cam.p,'image_base',0) else None,W=cam.writes())


def exit_menu(cam,kind):
    if kind=='ok':cam.press('OK')
    elif kind=='half':
        for address in (0x2029fdc4,0x202bd724):
            result=cam.m.fr.native(cam.h,address,(0x29,0),steps=30000000);assert result['ok'],result
    else:
        result=cam.m.fr.press(cam.h,0x29,steps=30000000);assert result['ok'],result
