"""Freeze the film selection, attribution, default print steps and scoring rules."""
import datetime
import hashlib
import json
from pathlib import Path
import sys

assert sys.flags.isolated
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
LOCAL=HERE/'local'
FILMS=(
    ('fujifilm_pro_400h','Pro 400H','negative'),
    ('fujifilm_provia_100f','Provia 100F','reversal'),
    ('fujifilm_velvia_100','Velvia 100','reversal'),
    ('fujifilm_xtra_400','Superia X-TRA 400','negative'),
    ('kodak_ektachrome_100','Ektachrome 100','reversal'),
    ('kodak_ektar_100','Ektar 100','negative'),
    ('kodak_gold_200','Gold 200','negative'),
    ('kodak_kodachrome_64','Kodachrome 64','reversal'),
    ('kodak_portra_160','Portra 160','negative'),
    ('kodak_portra_400','Portra 400','negative'),
    ('kodak_portra_800','Portra 800','negative'),
    ('kodak_portra_800_push2','Portra 800 +2','negative_push'),
    ('kodak_verita_200d','Verita 200D','cinema'),
    ('kodak_vision3_250d','Vision3 250D','cinema'),
    ('kodak_vision3_500t','Vision3 500T','cinema'),
)
EXTRAS=(('trix400','Tri-X 400','bw'),('velvia50','Velvia 50','reversal'),
        ('kodachrome25','Kodachrome25','reversal'),('instaxmini','instax mini','instant'),
        ('lomochromemetropolis','Metropolis','negative_special'))
ROUTES=('jpeg_control','scene_shared','scene_rgb','scene_shared_matrix',
        'scene_rgb_matrix','scene_structure','scene_weighted')


def main():
    assert not (LOCAL/'catalog.json').exists(),'Preserve the preregistered selection'
    frozen=[]
    def copy(p):
        p=Path(p);raw=p.read_bytes();dest=LOCAL/'film_sources'/p.name
        dest.parent.mkdir(exist_ok=True)
        if dest.exists():assert dest.read_bytes()==raw
        else:dest.write_bytes(raw)
        row=dict(source=str(p.relative_to(ROOT)),file=str(dest),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        frozen.append(row);return row
    info=json.loads((ROOT/'research/spektrafilm_bake/local/info.json').read_text())
    stocks={r['film']:r for r in info['films']}
    rows=[]
    for sid,name,kind in FILMS:
        base=ROOT/'research/spektrafilm_bake/local'
        bundle=json.loads((base/'bundles'/(sid+'_vlog65.json')).read_text())
        assert abs(bundle['input_exposure']['gain']-1)<1e-12
        row=dict(id=sid,name=name,family=kind,provider='spektrafilm',
            scene=copy(base/'cubes'/('spektrafilm_'+sid+'_vlog65.cube')),
            jpeg=copy(base/'cubes'/('spektrafilm_'+sid+'_srgbmid.cube')),
            jpeg_default=copy(base/'cubes'/('spektrafilm_'+sid+'_srgb.cube')),
            scene_space='vlog',output_space='srgb',profile=stocks[sid],bundle=copy(base/'bundles'/(sid+'_vlog65.json')),
            density_intermediates_available=any(v is not None for v in bundle['wires'].values()),
            intermediate_wires=bundle['wires'],
            print_step='direct film scan, matching the exporter correction to the GUI' if stocks[sid]['positive'] else stocks[sid]['target_print'],
            exposure_gain=1.,license='CC BY-SA 4.0',author='Andrea Volpato',
            version='spektrafilm 0.3.3 / commit 500bc429b7e93450ef228305c319dc03d8e185d1',
            source_url='https://github.com/andreavolpato/spektrafilm')
        rows.append(row)
    for sid,name,kind in EXTRAS:
        base=ROOT/'research/fotufilm_bake/local/cubes'
        lut=copy(base/('fotufilm_'+sid+'_srgb.cube'))
        rows.append(dict(id=sid,name=name,family=kind,provider='fotufilm',scene=lut,jpeg=lut,
            scene_space='srgb',output_space='srgb',density_intermediates_available=False,
            print_step='fotufilm stock default medium and fixed timing; no Auto Levels',
            exposure_gain=1.,license='CC BY-SA 4.0',author='Fotufilm / MUAStudio Inc. 2026',
            version='fotufilm-engine 1.14.1 / commit 96623ba0831a52dbddcda35727a206d4123a8b5f',
            source_url='https://fotufilm.com'))
    for folder in ('spektrafilm_bake','fotufilm_bake'):
        for p in (ROOT/'research'/folder/'local/cubes').glob('*.txt'):copy(p)
    for ordinal,row in enumerate(rows):
        row['ordinal']=ordinal
        row['indices']={route:1000+10*ordinal+j for j,route in enumerate(ROUTES)}
        row['existing_g157_film']=row['name'] in ('Tri-X 400','Portra 400','Velvia 50','Kodachrome25','Vision3 500T','instax mini','Metropolis')
    rules=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        purpose='Reproduce scene light -> film simulation -> print/scan -> output. JPEG-after04 is a control only.',
        scene_exposure='One fixed gain=1. D65 neutral XYZ Y=.18 at EV0; inherited GXR RAW meter anchor, no per-photo exposure/WB fitting.',
        look_safe_gap_pp=2.,look_safe_gap_reason='Operational budget, not a JND. Require <=2 pp on each unit plus <=0.25 median-DE00 penalty and stable quantization classification.',
        minimum_similarity_denominator=.25,
        perceptual_weights=dict(base=1.,skin=2.5,sky=2.5,foliage=2.5),
        color_region_masks=dict(skin=dict(L=[25,90],C=[8,55],h=[20,80]),
            sky=dict(L=[30,95],C=[8,75],h=[220,290]),foliage=dict(L=[15,85],C=[8,85],h=[95,175])),
        weighted_overall_allowance=dict(max_similarity_loss_pp=1.,max_p95_de00_rise=.25),
        highlights=dict(scene_Y_at_least=.72,EV_above_middle_gray=2.,bright_photo_minimum_share=.10),
        real_photos_are_frozen_whole_scene_holdouts=True,
        physical_layer_density_claim=False,
        structural_surrogate='Neutral-axis total response initializes separate RGB curves; local color Jacobian initializes matrix. Default print is folded into curves, because no stage density/print arrays survive in available 1lut bundles.',
        no_look_L1_engine_estimate=True,full_record_library_is_not_a_camera_release=True)
    doc=dict(films=rows,routes=list(ROUTES),rules=rules,frozen=frozen)
    (LOCAL/'catalog.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
    print('CATALOG',len(rows),'films,',sum(r['existing_g157_film'] for r in rows),'existing film Looks,',
          sum(r['density_intermediates_available'] for r in rows),'with intermediate wires')


if __name__=='__main__':main()
