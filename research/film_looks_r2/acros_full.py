"""Independent-curve control for the delivered official Acros, without changing it."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
from common import rt,LOCAL,UNITS,read,dump,sha
import library as L

INDEX=4053


def prepare():
    rows=[]
    for ui,unit in enumerate(UNITS):
        meta=read(LOCAL/'targets'/unit/'14/profile.json')
        source=LOCAL/'acros_official'/unit/'Acros.record552'
        entry=source.read_bytes();b=bytearray(entry);b[0]=6
        entry=C.codec.encode(bytes(b),L.parameters_of(entry),level=1,gray=True)
        folder=LOCAL/'targets'/unit/str(INDEX);folder.mkdir(parents=True,exist_ok=True)
        p=folder/'current.record552';p.write_bytes(entry)
        (folder/'photos.json').write_bytes((LOCAL/'inputs'/unit/'photos.json').read_bytes())
        doc=dict(meta,index=INDEX,kind='builtin',level=1,name='Acros official full control',
            current_record=str(p),current_sha256=sha(p),seeds=[str(p),str(source)],
            base_slot=6,expected_slot05_flags=None,required_base_flags=None,
            requires_companion_builtin=None,delivered_shared_record_unchanged=True)
        dump(folder/'profile.json',doc);rows.append(doc)
    dump('acros_full_profiles.json',rows)
    print('PREPARED 3 Acros full controls',flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('prepare','iterate','exact'))
    p.add_argument('--unit',choices=UNITS);p.add_argument('--nfev',type=int,default=400)
    a=p.parse_args()
    if a.stage=='prepare':return prepare()
    C.load_fit().run(a.unit,INDEX,a.stage,a.nfev)


if __name__=='__main__':main()
