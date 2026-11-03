"""Check color matrix math and MA register packing with a bounded A32 checker.

The checker runs only isolated original numeric/register packing routines in
synthetic RAM. It cannot write firmware files or access real camera hardware.
Run python3 -I. It reuses the independently developed gamma A32 decoder.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

ROOT=Path('/Users/wu/.t3/projects/projectricoh/research/gr_complete_pipeline')
spec=importlib.util.spec_from_file_location('arm_gamma_model',ROOT/'arm_gamma_model.py')
gamma=importlib.util.module_from_spec(spec);spec.loader.exec_module(gamma)

def signed16(x):return (x&65535)-65536 if x&32768 else x&65535
def trunc0(n,d):return n//d if n>=0 else -((-n)//d)
def mmul16(a,b):
 return [[signed16((sum(a[i][k]*b[k][j] for k in range(3))+4096)>>13) for j in range(3)] for i in range(3)]
def mmul32(a,b):
 return [[trunc0(sum(a[i][k]*b[k][j] for k in range(3))+4096,8192) for j in range(3)] for i in range(3)]
def front_registers(a,gain_scalar=128,mono=False):
 m=[[trunc0(v*gain_scalar,4096) for v in row] for row in a]
 if not mono:
  for i in range(3):m[i][i]=2*gain_scalar-sum(m[i][j] for j in range(3) if i!=j)
 return [[min(2047,max(-2048,v)) for v in row] for row in m]

C={
 'gr3':{'entry':0x536deecc,'lo':0x536deddc,'hi':0x536df13c,'memcpy':0x5313fd80,'ma_writer':0x536df55c,'ma_end':0x536e4470},
 'gr4':{'entry':0x53914e20,'lo':0x53914d30,'hi':0x5391506c,'memcpy':0x53156140,'ma_writer':0x5391548c,'ma_end':0x5391a3a0},
}
class ColorA32(gamma.StaticA32):
 def __init__(self,model):
  super().__init__(model,dict(key=0,contrast=0,shadow=0,highlight=0,flag=0,gain=8192))
  self.blocks=[(0x60000000,bytearray(65536)),(0x61000000,bytearray(65536))]
  self.allowed=[]
 def step(self):
  pc=self.reg[15];w=self.read(pc,4)
  if not self.cond(w>>28):return super().step()
  self._pc=pc
  if w&0x0fe00070==0x07c00010:
   rd=(w>>12)&15;lsb=(w>>7)&31;msb=(w>>16)&31;rn=w&15
   mask=((1<<(msb-lsb+1))-1)<<lsb
   self.reg[rd]=(self.reg[rd]&~mask)|((self.get(rn)<<lsb)&mask)
  elif w&0x0fff0ff0 in [0x06ef0070,0x06bf0070]:
   rd=(w>>12)&15;v=self.get(w&15)
   self.reg[rd]=(v&255) if w&0x0fff0ff0==0x06ef0070 else signed16(v)&gamma.MASK
  elif w&0x0ff00090==0x01000080:
   rd=(w>>16)&15;rn=(w>>12)&15;rs=(w>>8)&15;rm=w&15
   a=self.get(rm)>>(16 if w&(1<<5) else 0)
   b=self.get(rs)>>(16 if w&(1<<6) else 0)
   self.reg[rd]=(signed16(a)*signed16(b)+self.get(rn))&gamma.MASK
  elif w&0x0f000000==0x0b000000:
   off=w&0xffffff
   if off&0x800000:off-=0x1000000
   target=pc+8+4*off
   self.reg[14]=pc+4;self.calls[target]=self.calls.get(target,0)+1
   if target==C[self.model]['memcpy']:
    dest,source,count=self.reg[:3]
    if count>4096:raise ValueError('oversize copy')
    raw=[self.read(source+i,1) for i in range(count)]
    for i,v in enumerate(raw):self.write(dest+i,1,v)
   elif any(lo<=target<hi for lo,hi in self.allowed):self.reg[15]=target;self.steps+=1;return
   else:raise ValueError(f'unexpected color helper {target:#x}')
  else:return super().step()
  self.reg[15]=pc+4;self.steps+=1
 def run(self):
  while self.reg[15]!=0x62000000:
   if not any(lo<=self.reg[15]<hi for lo,hi in self.allowed):raise ValueError(f'color control escaped {self.reg[15]:#x}')
   if self.steps>200000:raise ValueError('step cap')
   self.step()

def interpreted_matrix(model,record,saturation=0,mono=False):
 m=ColorA32(model);c=C[model];out=0x61000000;settings=0x61009000
 m.reg[0]=out;m.reg[1]=settings;m.reg[15]=c['entry'];m.allowed=[(c['lo'],c['hi'])]
 m.write(settings+8,4,record)
 m.write(settings+0x57,1,saturation+4)
 m.write(settings+0x58,1,8)
 m.write(settings+0x5a,2,256)
 m.write(settings+0x79,1,int(mono))
 for off in [0x7c,0x7e,0x80]:m.write(settings+off,2,0xaaa)
 m.run()
 front=[[signed16(m.read(out+4+(i*3+j)*4,4)) for j in range(3)] for i in range(3)]
 second=[[signed16(m.read(out+0x32+(i*3+j)*2,2)) for j in range(3)] for i in range(3)]
 return {'front':front,'second':second,'steps':m.steps,'calls':{hex(k):v for k,v in m.calls.items()}}

def ma_register_image(model,record):
 m=ColorA32(model);c=C[model];obj=0x61008000;regs=0x61002000
 w=record['values']
 ptrs=[w[0],w[1],m.read(w[2]+16,4),m.read(w[3]+16,4),w[4],w[5]]
 for i,v in enumerate(ptrs):m.write(obj+4*i,4,v)
 m.reg[0]=obj;m.reg[1]=regs;m.reg[15]=c['ma_writer'];m.allowed=[(c['ma_writer'],c['ma_end'])]
 m.run()
 raw=bytes(m.read(regs+i,1) for i in range(0xb00))
 matrices=[m.read(ptrs[2]+4*i,4) for i in range(540)]
 matrix_mismatches=[i for i,v in enumerate(matrices) if int.from_bytes(raw[0x100+(i//45)*128+(i%45//9)*20+(i%9)*2:0x102+(i//45)*128+(i%45//9)*20+(i%9)*2],'little') != v&4095]
 bound_mismatches=[i for i in range(16) if int.from_bytes(raw[0xa0+2*i:0xa2+2*i],'little')!=m.read(ptrs[0]+2*i,2)&4095]
 bank_mismatches=[i for i in range(20) if (raw[0xc0+(i//5)*4+(i%5)//2]>>((i%5)%2*4))&15 != m.read(ptrs[1]+i,1)&15]
 assert not matrix_mismatches and not bound_mismatches and not bank_mismatches
 return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'hex':raw.hex(),'steps':m.steps,'calc_normal_path_pointers':list(map(hex,ptrs)), 'independent_layout_checks':{'matrix_values_checked':540,'matrix_mismatches':matrix_mismatches,'bound_values_checked':16,'bound_mismatches':bound_mismatches,'bank_values_checked':20,'bank_mismatches':bank_mismatches,'matrix_destination_formula':'0x100 + bank*0x80 + row*0x14 + element*2; i32 source, low12 bits','bounds_destination_formula':'0xA0 + bound_index*2; low12 bits','bank_destination_formula':'0xC0 + quadrant*4 + floor(segment/2); low4 bits shifted by 4*(segment%2)'},'unresolved':'Packing is exact. ISP pixel algorithm, row selection and interpretation of control bit5 are not established by this check.'}

def main():
 extracted=json.loads((ROOT/'arm_color_analysis.json').read_text())
 result={'kind':'bounded isolated A32 numeric/register packing interpretation, not camera execution or ISP pixel emulation','models':{}}
 for model,mi in extracted['models'].items():
  modes={}
  for mode,item in mi['modes'].items():
   mono=mode=='Hi-Contrast B&W'
   first=[[2730]*3]*3 if mono else item['saturation_matrices'][4]['Q13']
   expected=front_registers(mmul32(mmul16(first,item['look_matrix']['Q13']) if model=='gr3' else item['look_matrix']['Q13'],item['sensor_ccm']['Q13']),mono=mono)
   actual=interpreted_matrix(model,int(item['record']['vma'],16),mono=mono)
   actual['high_level_front']=expected
   actual['high_level_matches_A32']=expected==actual['front']
   assert actual['high_level_matches_A32']
   saturation_checks=[]
   for sat in ([0] if mono else range(-4,5)):
    test=interpreted_matrix(model,int(item['record']['vma'],16),saturation=sat,mono=mono)
    saturation_matrix=[[2730]*3]*3 if mono else item['saturation_matrices'][sat+4]['Q13']
    expected_front=front_registers(mmul32(mmul16(saturation_matrix,item['look_matrix']['Q13']) if model=='gr3' else item['look_matrix']['Q13'],item['sensor_ccm']['Q13']),mono=mono)
    expected_second=mmul16([[512,0,0],[0,512,0],[0,0,512]],saturation_matrix) if model=='gr4' else [[0]*3]*3
    ok=test['front']==expected_front and test['second']==expected_second
    saturation_checks.append({'saturation':sat,'front_match':test['front']==expected_front,'second_match':test['second']==expected_second})
    assert ok
   actual['saturation_checks']=saturation_checks
   ma=ma_register_image(model,item['MultiAxial'])
   filename=mode.lower().replace(' ','_').replace('&','and')
   (ROOT/f'arm_color_{model}_{filename}_registers.json').write_text(json.dumps(ma,indent=2)+'\n')
   actual['MultiAxial_register_image_sha256']=ma['sha256']
   modes[mode]=actual
   print(model,mode,actual)
  result['models'][model]=modes
 (ROOT/'arm_color_math_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
