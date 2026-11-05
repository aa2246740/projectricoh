"""Join already scored brightness with read-only EXIF. No numerical imports or pixels."""
import hashlib
import importlib.util
import json
import math
import mmap
import os
from pathlib import Path
import sys

assert sys.flags.isolated
ROOT=Path(__file__).resolve().parents[2];LOCAL=Path(__file__).resolve().parent/'local'
UNITS=('a12-50','a12-28','mount-a12')
if os.getpriority(os.PRIO_PROCESS,0)<15:os.nice(15-os.getpriority(os.PRIO_PROCESS,0))
def read(p):return json.loads(Path(p).read_text())
source=ROOT/'research/recipe_redo_r1/local/source/studio_snapshot/src/gxr_studio/raw/tiff.py'
spec=importlib.util.spec_from_file_location('film_metadata_tiff',source)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
Tiff=module.Tiff


def exif(path):
    with Path(path).open('rb') as f:
        with mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as data:
            T=Tiff(data);root=T.ifd(T.root)
            out={}
            if 34665 in root:
                e=T.ifd(root[34665]['value'][0])
                for tag,name in ((37380,'bias_ev'),(33434,'exposure_seconds'),(33437,'f_number'),(34855,'ISO')):
                    if tag in e:
                        value=e[tag]['value'][0]
                        out[name]=None if isinstance(value,float) and not math.isfinite(value) else value
            return out


def main():
    result=[]
    for unit in UNITS:
        info=read(LOCAL/'inputs'/unit/'photos.json')
        score_path=LOCAL/'analysis/00'/unit/'screen.json'
        scored=read(score_path)['routes']['scene_rgb_matrix']['scores']
        rows=[]
        for group,data in scored.items():
            if not group.startswith('photo_'):continue
            for photo in data['photos']:
                pid=photo['photo_id']
                source=info[int(pid)];p=Path(source['path']);p=p if p.is_absolute() else ROOT/p
                r=dict(photo_id=int(pid),group=group,path=str(p),source_sha256=source['sha256'],
                    scene_group=source.get('scene_group'),samples=photo['de00']['n'],
                    bright_share=photo['highlight_share'],brightness_source=str(score_path),
                    clipped_share_from_frozen_sampler=source.get('clipped_share'),exif=exif(p))
                rows.append(r)
        bright=[r for r in rows if r['bright_share']>=.1]
        positive=[r for r in rows if (r['exif'].get('bias_ev') or 0)>0]
        result.append(dict(unit=unit,photos=len(rows),bright_photos=len(bright),
            positive_exposure_compensation_photos=len(positive),
            positive_compensation_and_bright=sum(r['bright_share']>=.1 for r in positive),
            highest_brightness=sorted(rows,key=lambda r:r['bright_share'],reverse=True)[:12],
            positive_compensation=positive,all_metadata=rows,
            no_new_photo_selection_for_fitting=True,
            clipped_RAW_samples_excluded_by_original_sampler=True,
            true_film_shouldering_beyond_sensor_clipping_is_not_observable=True))
        print('PHOTO AUDIT',unit,len(rows),'bright',len(bright),'positive EV',len(positive),flush=True)
    out=dict(units=result,selection='Fixed input-only Y>=.72, at least10% of samples',
        interpretation='Brightness and positive EXIF compensation are separate observations; neither alone proves an overexposed scene or a known unclipped light level.',
        read_only_mmap=True,no_new_pixel_computation=True,no_pixel_artifact_outside_local=True)
    (LOCAL/'photo_brightness_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
