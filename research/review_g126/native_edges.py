"""Extract actual native wrap and DAT clamp observations from the value suite."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    units={}
    for unit in ('50mm','28mm','mount'):
        path=OUT/'local/ui-cases'/(unit+'-L1-virtual-scroll.json')
        value=json.loads(path.read_text())
        assert value['status']=='PASS' and value['dat_sha256']==sha(DAT.read_bytes())
        events=value['events']
        up=next(e for e in events if e['key']=='UP' and e['before']['cur']==0)
        down=next(e for e in events if e['key']=='DOWN' and e['before']['cur']==9)
        assert up['before']['physical']==0 and down['before']['physical']==7
        assert up['draws'][0]['cursor']==8 and down['draws'][0]['cursor']==1
        assert up['draws'][-1]['cursor']==1 and down['draws'][-1]['cursor']==8
        assert up['after']['cur']==0 and down['after']['cur']==9
        assert all(row['rows']==8 for event in (up,down) for row in event['draws'])
        units[unit]=dict(record=str(path.relative_to(ROOT)),up=up,down=down)
    save('evidence/native-edges.json',dict(status='PASS',dat_sha256=sha(DAT.read_bytes()),units=units,
         scope='Observed native cursor wrap before H08 and the subsequent compiled DAT redraw, extracted from official-key acceptance records. No synthetic UI seeding.'))
    print('PASS three units: native 1->8 / 8->1, DAT clamps logical endpoints; physical rows remain eight')

if __name__=='__main__':main()
