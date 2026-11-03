"""Host prediction using the frozen Engine colour chain and absolute T1.

The available Engine is ISO200 A12-50. Reuse on qlaunch/l08firm is explicitly
a transferred model, not an independent sensor/lens calibration.
"""
import sys
import support as s
s.dependencies()
import numpy as np
from PIL import Image
from collections import defaultdict
import knobs as k

OLD_TABLE=s.ROOT/'artifacts/stage2l-switch-packages/stage2l-switch-efe6587190e8/candidate/SD_ROOT/DEEPTBL0.DAT'
SCENES=(('desk','红印纸与桌面','2026-10-16/S1b-sd-import/DCIM/100RICOH/R8051130'),
        ('neutral','灰墙与笔','2026-10-16/S1b-sd-import/DCIM/100RICOH/R8051137'),
        ('apple','苹果与杂物','2026-10-19/stage2c-first-run/R8051144'),
        ('redblue','红蓝物体','2026-10-19/stage2c-first-run/R8051145'))


class Model:
    def __init__(self):
        sys.path.insert(0,str(s.ROOT/'research/closed_loop'))
        from model import Engine
        self.engine=Engine(OLD_TABLE,iso=200)
        self.mm,self.fs=self.engine.mm,self.engine.fs
        self.used={str(OLD_TABLE.relative_to(s.ROOT)):s.sha(OLD_TABLE)}

    def pre(self,b,x,channel_mode=None):
        xs=np.array([0,*__import__('struct').unpack_from('>31H',b,20),4095])
        active=bool(b[1]&4) if channel_mode is None else bool(channel_mode)
        curves=(b[379:412],b[82:115],b[412:445]) if active else (b[82:115],)*3
        return np.column_stack([np.interp(np.clip(x[:,j],0,4095),xs,list(curves[j])) for j in range(3)])

    def predict(self,b,x,channel_mode=None,quantize=False,half=0,bw_chroma='conditional'):
        pre=self.pre(b,x,channel_mode)
        row=self.mm.MatrixRow.from_bytes(b[216+half*28:244+half*28])
        # The B&W entry stores +0/+0/+0/+0. Negative zero is numerically zero;
        # fs.decode_word insists on a bitwise conjugate encoding and rejects it.
        coeff=np.array([[k.dec(z,128) for z in b[i:i+4]] for i in range(115,211,4)])
        if np.any(coeff[:,0]!=coeff[:,3]) or np.any(coeff[:,1]!=-coeff[:,2]):
            raise ValueError('frozen symmetric sector model cannot predict asymmetric rows')
        ab=coeff[:,:2]
        z=self.fs.Z_of_words(ab[:,0],ab[:,1],self.engine.ctx)
        y,ci=row.apply(pre)
        if b[0]==3:
            # Engine.predict('03') always discards chroma. For Tone only, this
            # explicit hypothesis lets matrix chroma reach BT.601 directly.
            # Its visibility is CONDITIONAL, never a camera or Engine proof.
            co=ci if bw_chroma=='conditional' else np.zeros_like(ci)
        else:co=self.engine.table.forward(ci,z)[0]
        rgb=np.clip(self.mm.rgb_from_ycc(y,co),0,255)
        return np.floor(rgb+.5).astype(np.uint8) if quantize else rgb

    def lab(self,rgb):return self.fs.lab_from_codes(rgb)
    def de(self,a,b):return self.fs.delta_e00(a,b)

    def provenance(self):
        e=self.engine.provenance.finish()
        for p,v in e.items():self.used[str(__import__('pathlib').Path(p).relative_to(s.ROOT))]=v['sha256']
        for p,h in self.used.items():
            if s.sha(s.ROOT/p)!=h:raise ValueError('model/capture input changed: '+p)
        return self.used

    def raw(self,scene,width=196):
        name,title,rel=scene
        stem=s.ROOT/'captures/a12-50'/rel
        dp,jp=stem.with_suffix('.DNG'),stem.with_suffix('.JPG')
        for p in (dp,jp):self.used[str(p.relative_to(s.ROOT))]=s.sha(p)
        d=self.fs.dsm().Dng(dp)
        if d.orientation!=1:raise ValueError('orientation needs explicit support')
        y0,x0,h,w=d.crop_window();oh=round(h*width/w);colours=defaultdict(list)
        for oy in range(2):
            for ox in range(2):
                yy=np.arange(y0+oy,y0+h-h%2,2)[:,None]
                xx=np.arange(x0+ox,x0+w-w%2,2)[None,:]
                val=d.normalised_at(yy,xx)
                small=Image.fromarray(val.astype(np.float32)).resize((width,oh),Image.Resampling.BOX)
                colours[int(d.cfa_at(y0+oy,x0+ox))].append(np.asarray(small,dtype=float))
        rgb=np.stack([np.mean(colours[c],axis=0) for c in range(3)],axis=-1)/d.as_shot_neutral
        x=rgb.reshape(-1,3)*4095
        info=dict(id=name,title=title,dng=str(dp.relative_to(s.ROOT)),jpeg=str(jp.relative_to(s.ROOT)),
                  iso=d.exif['iso'],size=[width,oh],input_above_4095_fraction=float(np.any(x>4095,axis=1).mean()),
                  raw_gain=1,calibration_iso=200,model_simulation_not_capture=True)
        return x,(width,oh),info


def synthetic():
    # Dense neutral ramp and a deterministic linear-light RGB cube, no photograph selection by result.
    neutral=np.repeat(np.geomspace(3,4095,257)[:,None],3,axis=1)
    grid=np.geomspace(12,3500,9)
    rgb=np.array(np.meshgrid(grid,grid,grid,indexing='ij')).reshape(3,-1).T
    return np.vstack((neutral,rgb))


def recipe_chart(model,base):
    # Equal areas per baseline output code avoid overweighting nearly black
    # patches merely because a logarithmic sensor grid contains many of them.
    raw=np.repeat(np.arange(4096)[:,None],3,axis=1)
    y=model.mm.ycbcr(model.predict(base,raw))[0]
    yy=np.maximum.accumulate(y);keep=np.r_[True,np.diff(yy)>1e-9]
    targets=np.linspace(max(1,float(yy[0])),min(254,float(yy[-1])),257)
    neutral=np.repeat(np.interp(targets,yy[keep],np.arange(4096)[keep])[:,None],3,axis=1)
    return np.vstack((neutral,synthetic()[257:]))


def masks(model,base,x,param,chart=False):
    rgb=model.predict(base,x,quantize=True);lab=model.lab(rgb)
    y=model.mm.ycbcr(rgb)[0];chroma=np.hypot(lab[:,1],lab[:,2])
    masks={'contrast':(y>=15)&(y<=240),'highlight':(y>=155)&(y<=245),
           'shadow':(y>=12)&(y<=110),'fade':(y>=5)&(y<=80),
           'saturation':(chroma>=15)&(y>=15)&(y<=235),
           'warmth':(chroma<=15)&(y>=35)&(y<=220),
           'tint':(chroma<=15)&(y>=35)&(y<=220),
           'filter':(chroma>=0)&(np.max(x,axis=1)-np.min(x,axis=1)>80)&(y>=15)&(y<=235),
           'tone':(y>=35)&(y<=220),'amount':(y>=15)&(y<=235)}
    neutral=np.max(x,axis=1)-np.min(x,axis=1)<1e-8
    if param=='split':
        result=[(y>=20)&(y<=90),(y>=160)&(y<=235)]
        return [m&neutral for m in result] if chart else result
    result=masks[param]
    if chart and param in ('contrast','highlight','shadow','fade'):result=result&neutral
    return [result]
