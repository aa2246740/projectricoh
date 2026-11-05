"""Conditional sector-response calibration. No camera or file writes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
from analyze import np


class Correction:
    def __init__(self,document=None):
        self.doc=document or a.read(a.LOCAL/'model.json')
        self.kind=self.doc['kind'];self.p=np.array(self.doc['parameters'])
    def hue(self,ci):
        h=np.angle(ci,deg=True)%360;p=self.p
        if self.kind=='nodes':
            step=360/len(p)
            return h+np.interp(h,np.arange(-1,len(p)+2)*step,np.r_[p[-1],p,p[0],p[1]])
        if self.kind=='ellipse':
            return np.angle(np.exp(1j*np.deg2rad(p[0]))*(ci+(p[1]+1j*p[2])*ci.conjugate()),deg=True)%360
        return h
    def parts(self,table,ci):
        h=np.angle(ci,deg=True)%360;W0=table.kernel_weights(h,abs(ci))
        if self.kind in ('nodes','ellipse'):
            W=table.kernel_weights(self.hue(ci),abs(ci))
            scale=(W0@table.S)/(W@table.S)
            G=W*table.gain*scale[:,None]
        else:G=W0*table.gain
        return W0@table.S,G
    def sector(self,table,ci,z):
        base,G=self.parts(table,ci)
        change=ci*(G@(table.S*(z-1)))
        if self.kind=='delta_linear':
            p=self.p;change=(p[0]+1j*p[1])*change+(p[2]+1j*p[3])*change.conjugate()
        return ci*base+change,G
    def predict(self,model,entry,x,*,round_output=False,half=0,bw_discard=None,unclipped=False):
        pre=model.pre(entry,np.asarray(x))
        y,ci=model.mm.MatrixRow.from_bytes(entry[216+half*28:244+half*28]).apply(pre)
        if bw_discard is None:bw_discard=entry[0]==3
        if bw_discard:co=np.zeros_like(ci)
        else:
            ab=np.array([model.fs.decode_word(entry[o:o+4]) for o in range(115,211,4)])
            z=model.fs.Z_of_words(ab[:,0],ab[:,1],model.engine.ctx)
            z=abs(z)*np.exp(1j*model.engine.table.k*np.angle(z))
            co,_=self.sector(model.engine.table,ci,z)
        rgb=model.mm.rgb_from_ycc(y,co)
        if unclipped:return rgb
        rgb=np.clip(rgb,0,255)
        return np.rint(rgb) if round_output else rgb
