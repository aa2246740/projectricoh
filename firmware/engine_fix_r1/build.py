"""Build service archive and product containers without rebuilding resident."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
import service_build


def main():
    c.guard()
    service_build.main()
    sys.path.insert(0,str(c.PRODUCT))
    candidates=c.load(c.PRODUCT/'candidates.py','r2_candidates')
    candidates.main()
    import shutil
    pack=candidates.pack
    source=c.LOCAL/'product/candidates/full-r2'
    target=c.LOCAL/'product/candidates/full-r2-prev';target.mkdir(exist_ok=True)
    for name in ('layout.json','trust.bin','effective-rows.bin'):
        shutil.copyfile(source/name,target/name)
    data=bytearray((source/'GXRCE.DAT').read_bytes());pack.p32(data,28,103)
    pack.write_bytes(target/'GXRCE.DAT',pack.seal(data))
    c.save(target/'fixture.json',dict(purpose='Failure injection needs an older generation to reach commit',
                                    generation=103,production_container=False))


if __name__=='__main__':main()
