"""Add a fair structure-initialized shared-curve control without replacing old fits."""
from pathlib import Path
import argparse
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
from common import rt,LOCAL,UNITS,read,dump,sha
import library as L


def prepare(ordinal):
    film=L.CATALOG['films'][ordinal]
    for ui,unit in enumerate(UNITS):
        index=film['indices']['scene_shared_structure'];folder=LOCAL/'targets'/unit/f'{index:02d}'
        if (folder/'profile.json').exists():continue
        oldindex=film['indices']['scene_shared_matrix'];old=read(LOCAL/'targets'/unit/f'{oldindex:02d}/profile.json')
        root=LOCAL/'films'/f'{ordinal:02d}'/unit
        camera=rt.Camera(ui);seed=L.shared_structure(camera,read(root/'structure.json'))
        dump(root/'look-structure.json',seed)
        folder.mkdir(parents=True,exist_ok=True)
        source=Path(old['current_record']);entry=source.read_bytes()
        current=folder/'current.record552';current.write_bytes(entry)
        (folder/'photos.json').write_bytes((source.parent/'photos.json').read_bytes())
        packed=L.parameters_of(entry)
        packed.update(curve_y_u8=seed['shared_curve_y_u8'],matrix_q10=seed['shared_matrix_q10'])
        b=C.codec.encode(entry,packed,level=0,gray=film['family']=='bw',look_unit_mask=1<<ui)
        start=folder/'seed-structure.record552';start.write_bytes(b)
        doc=dict(old,index=index,route='scene_shared_structure',current_record=str(current),
            current_sha256=sha(current),seeds=[str(current),str(start)],structure_file=str(root/'look-structure.json'),
            fair_initialization_upgrade=True,prior_fits_preserved=True)
        dump(folder/'profile.json',doc)
    dump(LOCAL/'films'/f'{ordinal:02d}/look-structure-prepared.json',dict(ordinal=ordinal,ready=True))
    print('SHARED STRUCTURE PREPARED',film['name'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--film',type=int,required=True);a=p.parse_args();prepare(a.film)
