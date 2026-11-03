"""Retain unit calibration code windows with per-image address mapping."""
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import study
from facts import UnitImage

for name in ('jlaunch3','qlaunch3','l08firm3'):
    image=UnitImage(name)
    for label,start,end in (('start',0x2005b5b4,0x2005b648),
                            ('t-core',0x20065820,0x20065e48)):
        raw=image.raw(start,end-start)
        path=study.OUT/(name+'-'+label+'.bin')
        path.write_bytes(raw)
        result=subprocess.check_output([str(study.OBJDUMP),'-D','-b','binary',
            '-m','m32r','-EB','--adjust-vma='+hex(start),str(path)],text=True)
        path.with_suffix('.asm.txt').write_text(result)
        study.save(name+'-'+label+'.meta.json',dict(image_sha256=study.sha(image.path),
                   sha256=study.sha(path),start=hex(start),end=hex(end),
                   file=hex(image.offset(start,end-start)[0])))
print('Six unit code windows retained.')
