"""Extract bounded official or flashed M32R ranges into this task only."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import artifacts as a
import boundary as b
import json
import subprocess

def main():
    objdump=b.add(b.ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump')
    out=b.LOCAL/'disasm'
    image_path=b.ROOT/('firmware/image_v34c/local/package/SD_ROOT/ilaunch3' if sys.argv[1]=='flashed' else 'artifacts/firmware/gxr-1.51/ilaunch3')
    image=a.read(image_path);locations=[]
    for item in sys.argv[2:]:
        name,lo,hi=item.split(':');start,end=int(lo,0),int(hi,0)
        data,off,section=a.native_span(image,start,end-start)
        inp=out/(name+'.bin');inp.write_bytes(data)
        cmd=[str(objdump),'-D','-EB','-b','binary','-m','m32r','--adjust-vma='+hex(start),str(inp)]
        result=subprocess.run(cmd,text=True,capture_output=True,check=True)
        (out/(name+'.txt')).write_text(result.stdout)
        locations.append(dict(name=name,image=str(image_path.relative_to(b.ROOT)),start=hex(start),end=hex(end),file_offset=hex(off),section=section,command=cmd))
    b.dump('ranges-'+sys.argv[2].split(':')[0]+'.json',locations)
    print('extracted',len(locations),'bounded ranges')

if __name__=='__main__':main()
