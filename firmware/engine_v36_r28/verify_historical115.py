"""Keep 113/114 qlaunch native-only assertions tied to their historical artifacts."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'candidate'))
import common as c


def main():
    binary=HERE/'local/historical114/host';out=binary.parent;results=[]
    for generation,folder in ((113,c.UPSTREAM/'acceptance/local/full-r11'),(114,HERE/'local/reproduced114')):
        for case in ('basic','first'):
            label=f'historical-native{generation}-{case}-qlaunch'
            result=c.run([binary,case,1,folder/'GXRCE.DAT',folder/'trust.bin',folder/'effective-rows.bin',
                c.ROOT/'firmware/resident_v33/acceptance/local/full-r9/GXRCE.DAT','0'],label)
            assert result.stdout.splitlines()[-1].startswith('OK ')
            (out/(label+'.stdout')).write_text(result.stdout)
            (out/(label+'.stderr')).write_text(result.stderr)
            results.append(dict(generation=generation,case=case,unit=1,native_only=True,
                dat_sha256=c.sha(folder/'GXRCE.DAT'),host_sha256=c.sha(binary)))
    (out/'results.json').write_text(json.dumps(dict(status='PASS',runs=results),indent=2)+'\n')
    print('PASS historical qlaunch native-only assertions: four runs on real gen113/gen114 artifacts')


if __name__=='__main__':main()
