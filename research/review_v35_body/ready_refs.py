"""Find literal address constructions in genuine body code, keep disassembly."""
import json
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,ROOT,save
from image_loader import Image
im=Image(ROOT/"artifacts/firmware/gxr-1.51/ilaunch3","da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7")
objdump=ROOT/"research/tooling_m32r/prefix/bin/m32r-elf-objdump"
dest=HERE/"ready_refs";dest.mkdir(exist_ok=True)
refs=[]
for s in im.sections:
 data=im.raw[s.source+512:s.source+512+s.size]
 for pos in range(0,len(data)-4,2):
  word=data[pos:pos+4]
  if word[0] not in range(0xd0,0xe0) or word[1]!=0xc0:continue
  reg=word[0]&15;high=int.from_bytes(word[2:],"big")<<16
  if high not in (0x20400000,0x20410000,0x200d0000,0x20090000):continue
  for rel in range(4,33,2):
   w=data[pos+rel:pos+rel+4]
   if len(w)!=4 or w[0] != 0x80+reg or (w[1]&15)!=reg:continue
   low=int.from_bytes(w[2:],"big")
   if w[1]>>4==0xe:value=high|low
   elif w[1]>>4==0xa:value=high+(low-65536 if low&32768 else low)
   else:continue
   if value not in (0x200d7fd8,0x2040f800,0x2040f804,0x2040f818,0x200935b4):continue
   va=s.base+pos;start=max(s.base,va-40);end=min(s.base+s.size,va+100)
   label=f'{value:08x}-{va:08x}'
   raw=dest/(label+".bin");raw.write_bytes(im.bytes_at(start,end-start))
   p=subprocess.run([str(objdump),"-D","-b","binary","-m","m32r","-EB","--adjust-vma="+hex(start),str(raw)],capture_output=True,text=True,check=True)
   (dest/(label+".asm")).write_text(p.stdout)
   refs.append(dict(target=hex(value),vma=hex(va),low_vma=hex(va+rel),reg=reg,listing=raw.with_suffix(".asm").relative_to(HERE).as_posix()))
save("ready-refs.json",refs)
print(json.dumps(refs,indent=2))
