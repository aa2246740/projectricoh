"""Independent static reconstruction of Ricoh GR III/IV GammaTuning.

All Python entry points are intended for python3 -I. No camera I/O and no firmware
writes. The small A32 checker interprets only the isolated numeric routine; it
rejects writes outside synthetic stack/output memory and all unexpected calls.
"""
from pathlib import Path
import struct, importlib.util
from functools import lru_cache
_here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('arm_gamma_inspect',_here/'arm_gamma_inspect.py')
inspect=importlib.util.module_from_spec(spec);spec.loader.exec_module(inspect)
MODELS={
 'gr3':{'entry':0x536e7b64,'end':0x536e82c8,'families':0x550204d4,'key':0x538f34e0,'smoothing':0x53ddd594,'unit':0x53ddd658,'divide_unsigned':0x5313d850,'divide_signed':0x5313d884},
 'gr4':{'entry':0x5391dad4,'end':0x5391e238,'families':0x55032890,'key':0x53b4d644,'smoothing':0x5407b1f4,'unit':0x5407e710,'divide_unsigned':0x53153830,'divide_signed':0x53153864},
}
@lru_cache(maxsize=2)
def tables(model):
 c=MODELS[model];d=inspect.image(model)
 read=lambda a,n:inspect.read(model,a,n,d)
 word=lambda a:struct.unpack('<I',read(a,4))[0]
 ptrs=[[word(word(c['families']+4*f)+4*b) for b in range(5)] for f in range(3)]
 return {'pointers':ptrs,'curves':[[list(struct.unpack('<256H',read(a,512))) for a in fam] for fam in ptrs],
         'keys':list(struct.unpack('<9i',read(c['key'],36))),
         'smoothing':list(struct.unpack('<97H',read(c['smoothing'],194))),
         'unit':struct.unpack('<H',read(c['unit'],2))[0]}
def _blend(a,b,w):return (a*w+b*(512-w)+256)>>9

def effective_curve(model='gr3',key=0,contrast=0,highlight=0,shadow=0,gain=8192,flag=0,details=False):
 """Return 256 integer u14-ish gamma nodes; gain and flag are explicit runtime inputs.

 Sliders are signed -4..4. Default arguments mean an explicit hypothetical neutral
 state, not proof of factory settings or a reference photograph's runtime gain.
 """
 if any(not -4<=v<=4 for v in [key,contrast,highlight,shadow]):raise ValueError('slider outside -4..4')
 if flag not in [0,1]:raise ValueError('flag must be explicit 0 or 1')
 if not 0<=gain<=65535:raise ValueError('gain outside producer UXTH range 0..65535')
 t=tables(model)
 knee=max(128,min(2048,((t['keys'][key+4]*(256 if flag else 512)//256)*gain & 0xffffffff)>>13))
 low=0 if knee<=255 else 1 if knee<512 else 2 if knee<1024 else 3
 high=low+1;index=knee>>4
 target=(t['unit']*118)&65535
 regions=[]
 for adjustment in [highlight,0,-shadow]:
  k=max(-12,min(12,2*contrast+adjustment))
  if k>0: a,b,w=0,1,(k*512)//12
  else:a,b,w=1,2,((k+12)*512)//12
  ylow=_blend(t['curves'][a][low][index],t['curves'][b][low][index],w)
  yhigh=_blend(t['curves'][a][high][index],t['curves'][b][high][index],w)
  bandw=512 if ylow<=yhigh else 0 if yhigh>=target else ((target-yhigh)<<9)//(ylow-yhigh)
  regions.append({'adjustment':adjustment,'contrast_sum':k,'families':[a,b],'family_weights':[w,512-w],'bands':[low,high],'band_weights':[bandw,512-bandw],'anchor_values':[ylow,yhigh]})
 def region_y(region,i):
  a,b=region['families'];w=region['family_weights'][0];bw=region['band_weights'][0]
  return _blend(_blend(t['curves'][a][low][i],t['curves'][b][low][i],w),_blend(t['curves'][a][high][i],t['curves'][b][high][i],w),bw)
 out=[]
 for i in range(256):
  x=i*16;ri=2 if x<=knee else 0
  mid=region_y(regions[1],i);selected=region_y(regions[ri],i);y=mid
  if x>knee and highlight:
   if x>=4*knee:y=selected
   else:
    s=t['smoothing'][max(0,min(96,(i*512)//knee-32))]
    y=(selected*s+mid*(2048-s)+1024)>>11
  if x<knee and shadow:
   if x<=knee//4:y=selected
   else:
    s=t['smoothing'][max(0,min(96,(knee*32)//x-32))]
    y=(selected*s+mid*(2048-s)+1024)>>11
  out.append(min(16384,(y<<14)//(0x3f02*(t['unit']>>6))))
 info={'knee_u12':knee,'knee_sample_index':index,'target_before_final_scale':target,'regions_high_mid_shadow':regions,'gain':gain,'flag':flag}
 return (out,info) if details else out

def evaluate_gamma(sliders, gain, model='gr3', flag=0):
 return effective_curve(model=model,gain=int(gain),flag=flag,**sliders)

MASK=0xffffffff
def s32(x):return x-2**32 if x&0x80000000 else x
def ror(x,n):
 n%=32
 return ((x>>n)|(x<<(32-n)))&MASK if n else x

class StaticA32:
 """Restricted A32 integer interpreter used to check the independent formula.

 It is not a camera simulator. Firmware data is immutable; only an isolated
 64 KiB stack and 4 KiB scratch region can receive writes. Calls other than the
 two observed integer-division helpers are rejected.
 """
 def __init__(self,model,params):
  self.model=model;self.c=MODELS[model];self.d=inspect.image(model);self.reg=[0]*16;self.flags=[0,0,0,0];self.steps=0;self.calls={};self.trace=[]
  self.reg[0]=self.reg[1]=0x61000000;self.reg[2]=0x61000800;self.reg[13]=0x6000ff00;self.reg[14]=0x62000000;self.reg[15]=self.c['entry']
  self.blocks=[(0x60000000,bytearray(65536)),(0x61000000,bytearray(4096))]
  values=[0,params['key'],params['contrast'],-params['shadow'],params['highlight'],params['flag'],params['gain']]
  for i,x in enumerate(values):self.write(0x61000800+4*i,4,x)
 def read(self,a,n):
  for base,b in self.blocks:
   if base<=a and a+n<=base+len(b):return int.from_bytes(b[a-base:a-base+n],'little')
  if not 0x53000000<=a<0x55100000:raise ValueError(f'unmapped read {a:#x}')
  return int.from_bytes(inspect.read(self.model,a,n,self.d),'little')
 def write(self,a,n,v):
  for base,b in self.blocks:
   if base<=a and a+n<=base+len(b):b[a-base:a-base+n]=(v&((1<<(n*8))-1)).to_bytes(n,'little');return
  raise ValueError(f'rejected firmware/unmapped write {a:#x}')
 def cond(self,c):
  n,z,cflag,v=self.flags
  return [z,not z,cflag,not cflag,n,not n,v,not v,cflag and not z,not cflag or z,n==v,n!=v,not z and n==v,z or n!=v,True,False][c]
 def shift(self,v,kind,n,imm=True):
  oldc=self.flags[2]
  if not n and (not imm or kind==0):return v,oldc
  if imm and not n:n=32
  if kind==0:return (v<<n)&MASK,((v>>(32-n))&1 if n<=32 else 0)
  if kind==1:return (v>>n if n<32 else 0),(v>>(n-1)&1 if n<=32 else 0)
  if kind==2:return (s32(v)>>min(n,32))&MASK,(v>>(min(n,32)-1))&1
  if kind==3:
   if imm and n==32:return ((oldc<<31)|(v>>1)),v&1
   return ror(v,n),((v>>(n%32-1))&1 if n%32 else v>>31)
 def operand(self,w):
  if w&(1<<25):
   rot=((w>>8)&15)*2;v=ror(w&255,rot);return v, v>>31 if rot else self.flags[2]
  rm=self.get(w&15);kind=(w>>5)&3
  n=(self.get((w>>8)&15)&255) if w&16 else (w>>7)&31
  return self.shift(rm,kind,n,not bool(w&16))
 def add(self,a,b,carry=0):
  total=a+b+carry;u=total&MASK
  self.flags=[u>>31,int(u==0),int(total>MASK),int(((~(a^b)&(a^u))>>31)&1)]
  return u
 def step(self):
  pc=self.reg[15];w=self.read(pc,4);self.reg[15]=pc+4;self.steps+=1
  # get(PC) must observe architectural current PC+8, not next instruction+8.
  self._pc=pc
  if not self.cond(w>>28):return
  rn=(w>>16)&15;rd=(w>>12)&15
  if w&0x0ff00000 in (0x03000000,0x03400000):
   v=(w&4095)|((w>>4)&0xf000)
   self.reg[rd]=v if w&0x0ff00000==0x03000000 else (self.reg[rd]&65535)|(v<<16);return
  if w&0x0ffffff0==0x012fff10:self.reg[15]=self.get(w&15)&~1;return
  if w&0x0fff0ff0==0x06ff0070:self.reg[rd]=self.get(w&15)&65535;return
  if w&0x0f8000f0==0x00800090:
   signed=bool(w&(1<<22));a=self.get(w&15);b=self.get((w>>8)&15)
   if signed:a=s32(a);b=s32(b)
   p=a*b;lo=(w>>12)&15;hi=(w>>16)&15
   if w&(1<<21):p+=self.reg[lo]+(self.reg[hi]<<32)
   self.reg[lo]=p&MASK;self.reg[hi]=(p>>32)&MASK;return
  if w&0x0fc000f0==0x00000090:
   dest=(w>>16)&15;p=self.get(w&15)*self.get((w>>8)&15)
   if w&(1<<21):p+=self.get((w>>12)&15)
   self.reg[dest]=p&MASK;return
  if w&0x0e000000==0x0a000000:
   off=w&0xffffff
   if off&0x800000:off-=0x1000000
   target=pc+8+off*4
   if w&(1<<24):
    self.reg[14]=pc+4;self.calls[target]=self.calls.get(target,0)+1
    if target in [self.c['divide_unsigned'],self.c['divide_signed']]:
     a,b=self.reg[:2]
     if target==self.c['divide_signed']:a=s32(a);b=s32(b)
     if b==0:raise ValueError('division by zero')
     q=abs(a)//abs(b);self.reg[0]=(q if (a<0)==(b<0) else -q)&MASK;return
    raise ValueError(f'unexpected call {target:#x}')
   self.reg[15]=target;return
  if w&0x0e000000==0x08000000:
   regs=[i for i in range(16) if w&(1<<i)];base=self.get(rn);up=bool(w&(1<<23));pre=bool(w&(1<<24));load=bool(w&(1<<20));n=len(regs)
   start=base+(4 if pre else 0) if up else base-4*n+(0 if pre else 4)
   new={}
   for i,reg in enumerate(regs):
    a=start+4*i
    if load:new[reg]=self.read(a,4)
    else:self.write(a,4,self.get(reg))
   if w&(1<<21):self.reg[rn]=(base+(4*n if up else -4*n))&MASK
   for reg,v in new.items():self.reg[reg]=v
   return
  if w&0x0c000000==0x04000000:
   off=w&4095
   if w&(1<<25):off=self.shift(self.get(w&15),(w>>5)&3,(w>>7)&31)[0]
   base=self.get(rn);adj=(base+(off if w&(1<<23) else -off))&MASK;a=adj if w&(1<<24) else base;n=1 if w&(1<<22) else 4
   if w&(1<<20):self.reg[rd]=self.read(a,n)
   else:self.write(a,n,self.get(rd))
   if not w&(1<<24) or w&(1<<21):self.reg[rn]=adj
   return
  if w&0x0e000090==0x00000090:
   off=(((w>>8)&15)<<4)|(w&15) if w&(1<<22) else self.get(w&15)
   base=self.get(rn);adj=(base+(off if w&(1<<23) else -off))&MASK;a=adj if w&(1<<24) else base
   kind=(w>>5)&3
   if w&(1<<20):
    n=1 if kind==2 else 2;v=self.read(a,n)
    if kind>=2 and v&(1<<(n*8-1)):v-=1<<(n*8)
    self.reg[rd]=v&MASK
   elif kind==1:self.write(a,2,self.get(rd))
   else:raise ValueError(f'unsupported halfword store {pc:#x} {w:#x}')
   if not w&(1<<24) or w&(1<<21):self.reg[rn]=adj
   return
  if w&0x0c000000==0:
   op=(w>>21)&15;a=self.get(rn);b,c=self.operand(w);setflags=bool(w&(1<<20)) or op in [8,9,10,11];old=self.flags[:]
   if op in [2,10]:v=self.add(a,(~b)&MASK,1)
   elif op==3:v=self.add(b,(~a)&MASK,1)
   elif op in [4,11]:v=self.add(a,b)
   elif op==5:v=self.add(a,b,self.flags[2])
   elif op==6:v=self.add(a,(~b)&MASK,self.flags[2])
   elif op in [0,8]:v=a&b
   elif op in [1,9]:v=a^b
   elif op==12:v=a|b
   elif op==13:v=b
   elif op==14:v=a&~b
   elif op==15:v=~b&MASK
   else:raise ValueError(f'unsupported opcode {pc:#x} {w:#x}')
   if op in [0,1,8,9,12,13,14,15]:self.flags=[v>>31,int(v==0),c,old[3]]
   if not setflags:self.flags=old
   if op not in [8,9,10,11]:self.reg[rd]=v&MASK
   return
  raise ValueError(f'unsupported instruction {pc:#x} {w:#x}')
 def get(self,n):return self._pc+8 if n==15 else self.reg[n]
 def run(self):
  while self.reg[15]!=0x62000000:
   if not self.c['entry']<=self.reg[15]<self.c['end']:raise ValueError(f'control escaped function {self.reg[15]:#x}')
   if self.steps>100000:raise ValueError('step cap')
   self.step()
  return [self.read(0x61000000+i*2,2) for i in range(256)]

def interpreted_curve(model='gr3',key=0,contrast=0,highlight=0,shadow=0,gain=8192,flag=0):
 c=StaticA32(model,locals());out=c.run();return out,{'steps':c.steps,'calls':{hex(a):v for a,v in c.calls.items()}}

if __name__=='__main__':
 for model in ['gr3','gr4']:
  p={'key':-1,'contrast':3,'highlight':-1,'shadow':-2,'gain':8192,'flag':0}
  a,details=effective_curve(model,**p,details=True);b,trace=interpreted_curve(model,**p)
  print(model,'matches',a==b,'first_difference',next(((i,x,y) for i,(x,y) in enumerate(zip(a,b)) if x!=y),None),'first16',a[:16],details,trace)
