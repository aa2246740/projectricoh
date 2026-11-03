"""Re-extract official native windows from the pinned genuine ZIP."""
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from common import ROOT, OUT, load, save, sha
m=load(ROOT/'research/ux_preview_dot_r1/collect_native.py','g118_official_windows')
m.HERE=OUT
m.main()
# Also inspect the native setting accessors that choose shutter exit arms.
image=m.Image(OUT/'local/native/ilaunch3','da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7')
start,end=0x20260000,0x20280000;blob=image.bytes_at(start,end-start)
p=OUT/'local/native/settings-accessors.bin';p.write_bytes(blob)
cmd=[str(ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'),'-D','-z','-b','binary','-m','m32r','-EB','--adjust-vma='+hex(start),str(p)]
r=subprocess.run(cmd,text=True,capture_output=True,check=True)
p.with_suffix('.txt').write_text(r.stdout)
save('official-accessors.json',dict(vma=hex(start),end=hex(end),file_offset=image.offset(start,len(blob)),sha256=sha(blob),command=cmd))
