"""g152 bindings for the Python instruction model and native menu constructors."""
from pathlib import Path
import importlib.util
import json
import os
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g152')
os.environ['TMPDIR']=str(TMP)
os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ.setdefault('REVIEW_JOB',Path(sys.argv[0]).stem+'-'+str(os.getpid()))
spec=importlib.util.spec_from_file_location('g152_host_base',ROOT/'research/g150/tests/g139_host.py')
H=importlib.util.module_from_spec(spec);sys.modules[spec.name]=H;spec.loader.exec_module(H)
H.WORK=HERE;H.LOCAL=HERE/'local/native';H.TMP=TMP/'native'/os.environ['REVIEW_JOB']
H.PACKAGE=ROOT/'firmware/package_v38_g152_test/local/SD_ROOT'
H.DAT=H.PACKAGE/'GXRCE.DAT';H.BODY=H.PACKAGE/'ilaunch3'
H.ENGINE=ROOT/'firmware/engine_v60_g152/candidate/local/full-r13/engine.elf'
H.LAYOUT=json.loads((HERE/'layout.json').read_text());H.UI=H.LAYOUT['ui']
H.setup()

class Camera(H.Camera):
    def symbol(self,name):
        if name not in self.p.elf.symbols:
            matches=[s for s in self.p.elf.symbols if s.startswith(name+'.')]
            assert len(matches)==1,(name,matches)
            name=matches[0]
        return self.p.symbol_pc(name)

    def labels(self):
        base=self.adapter+H.UI+H.LAYOUT['ui.text']
        return [bytes(self.h.b.read(base+14*i,14)).split(b'\0')[0].decode('ascii') for i in range(8)]

    def state(self):
        result=super().state();result['effect']=self.ui('effect');return result

    def effect_rows(self):
        from dat_format import expand_effect,CRC_FIELDS
        e=expand_effect(H.DAT_BYTES[self.dat_path],self.ui('effect')-1)
        return [e[a:a+n] for a,n,_ in CRC_FIELDS],int.from_bytes(e[445:447],'big')

    def engine_ref(self,which='current'):
        return self.engine_bytes(H.LAYOUT['g.'+which],56)

    def open_looks(self):
        self.goto(8);self.press('DISP');frame=self.check_frame()
        assert frame['screen']==7 and frame['count']==11,frame
        return frame

    def select_effect(self,number):
        if self.ui('screen')!=7:
            if self.ui('screen')==1:self.goto(0);self.press('DISP')
            if self.ui('screen')!=7:self.open_looks()
        self.goto(number);return self.check_frame()

def exit_menu(cam,kind):
    if kind=='ok':cam.press('OK')
    elif kind=='half':
        for address in (0x2029fdc4,0x202bd724):
            result=cam.m.fr.native(cam.h,address,(0x29,0),steps=30000000);assert result['ok'],result
    else:
        result=cam.m.fr.press(cam.h,0x29,steps=30000000);assert result['ok'],result

def snapshot(cam):
    rows,t=cam.unit_rows()
    return dict(rows=rows,T=t,S=cam.s_bytes(0,4096),ref=cam.engine_ref() if getattr(cam.p,'image_base',0) else None,W=cam.writes())

def expected(cam,entry):
    from dat_format import CRC_FIELDS
    return [entry[a:a+n] for a,n,_ in CRC_FIELDS],int.from_bytes(entry[445:447],'big')
