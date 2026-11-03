"""Provenance and camera/source diagnostics that do not create spectral truth."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c
from common import np
from raw_io import RawDng
from extract_griv import GRIV,GRIV_SHA
import csv
import datetime
import json
import re


def main():
    s=c.arrays(c.LOCAL/'sensitivities.npz')
    with (c.LOCAL/'sensitivity_intervals.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['camera','channel','wavelength_nm','scenario_p05','scenario_p50','scenario_p95'])
        for camera in ('gxr','griv'):
            q=np.percentile(s[camera],[5,50,95],axis=0)
            for channel in range(3):
                for index,wavelength in enumerate(s['wave']):
                    w.writerow([camera,'RGB'[channel],int(wavelength),*q[:,channel,index]])
    source=c.read(c.LOCAL/'sensitivity_fit.json')
    contrast=[]
    for x in source['configurations']:
        contrast.append(dict(configuration=x['configuration'],
          griv_reference=x['target']['chart_reference'],gxr_cost=x['source']['cost'],griv_cost=x['target']['cost'],
          gxr_veiling=x['source']['neutral_veiling_reflectance'],griv_veiling=x['target']['neutral_veiling_reflectance']))
    c.dump('formulation_and_veil_diagnostic.json',dict(configurations=contrast,
         known_GXR_formulation='before November 2014, capture in 2010',
         known_GRIV_formulation=None,GRIV_label='colorchecker CLASSIC / X-Rite; chart production date not independently verified',
         default='post2014 DCamProf spectral model; explicit pre2014 Avg30 stress alternative',
         matching_average_does_not_establish_same_physical_chart=True,
         veiling_parameter_is_fitted_nuisance_not_measured_lens_property=True))
    # An independent pre-existing Python SOF3 decoder checks the new DNG pixel stream.
    # Cache is keyed by both implementations and the exact DNG, not by a success flag.
    decoder_path=c.inp('research/color_references/lossless_jpeg.py')
    cache=c.LOCAL/'independent_raw_decode.json'
    key=dict(input_sha256=GRIV_SHA,decoder_sha256=c.sha(decoder_path),
             adapter_sha256=c.sha(c.HERE/'raw_io.py'))
    previous=c.read(cache) if cache.exists() else None
    if previous and all(previous.get(k)==v for k,v in key.items()) and previous.get('mismatches')==0:
        print('independent GR IV decode verified previously against the exact same input and decoder')
    else:
        d=RawDng(GRIV);off,count=d._strips
        assert len(off)==1
        blob=d.data[off[0]:off[0]+count[0]]
        decoder=c.module('bridge_independent_sof3',decoder_path)
        raw,info=decoder.decode(blob)
        own=d.mosaic();assert raw.shape==own.shape
        mismatches=int(np.sum(raw!=own));assert mismatches==0
        c.dump(cache,dict(**key,shape=list(raw.shape),samples=int(raw.size),mismatches=mismatches,
                 decoder_1='installed imagecodecs.ljpeg_decode',decoder_2='frozen original Python SOF3 decoder',
                 decoded_u16_sha256=__import__('hashlib').sha256(raw.astype('<u2').tobytes()).hexdigest(),
                 predictor=info['predictor']))
        print('independent GR IV RAW decode: identical samples',int(raw.size),flush=True)
    # Old RAW packing has a second independent bit-unpacking check on widely spaced rows.
    old=RawDng('artifacts/downloads/dpreview-gxr-a12-studio/studio_iso200.DNG')
    offsets,counts=old._strips
    packed=b''.join(old.data[o:o+n] for o,n in zip(offsets,counts))
    row_bytes=(old.width*old.bps+7)//8
    checks=[]
    for row in (17,811,2617):
        b=np.frombuffer(packed,np.uint8,count=row_bytes,offset=row*row_bytes)
        bits=np.unpackbits(b)[:old.width*old.bps].reshape(old.width,old.bps)
        independent=(bits*(1<<np.arange(old.bps-1,-1,-1))).sum(axis=1)
        mismatches=int(np.sum(independent!=old.mosaic()[row]));assert mismatches==0
        checks.append(dict(row=row,mismatches=mismatches,samples=old.width))
    c.dump('gxr_packing_check.json',checks)
    # Existing protected source provenance is copied into this task's own registry.
    records=c.read(c.LOCAL/'sources.json')
    label='dpreview-gxr-existing-input'
    if not any(v['label']==label for v in records):
        p=c.inp('artifacts/downloads/dpreview-gxr-a12-studio/studio_iso200.DNG')
        records.append(dict(label=label,
            url='http://web.archive.org/web/20130105011012/http://movies.dpreview.com.s3.amazonaws.com/ricoh_gxr_a12/studio_iso200.zip',
            member='studio_iso200.DNG',file=str(p.relative_to(c.ROOT)),sha256=c.sha(p),
            archive_sha256='dcd768bb233dfdec99ef50239f2b8c6157717823fd31d5ce9797b791a99f2971',
            date_utc=datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat(),
            date_note='pre-existing local input file timestamp; original acquisition date is in its source receipt',
            method='GET',untrusted=True,status='pre-existing; not downloaded by this worker'))
        c.dump('sources.json',records)
    c.dump('sensor_identification.json',dict(
      gxr=dict(verified='Ricoh A12 50mm, 12.3 MP APS-C CMOS; dimensions and model read from own public DNG',
               likely='Sony 12 MP APS-C generation, IMX038-family hypothesis',confidence='low; no package marking or primary vendor cross-reference',
               exact_part_number=None,weak_siblings=['Nikon D90','Nikon D300s'],
               prior_weight='0 in default; 0.20 in one stress variant; CFA/lens/filter differences retained'),
      griv=dict(verified='Ricoh 25.74 MP APS-C BSI CMOS, revised UV/IR stack raises long-wavelength R throughput',
                likely='Sony IMX571 family / custom variant',confidence='low-to-moderate for family; exact part unverified',
                exact_part_number=None,same_chip_does_not_supply_camera_spectral_response=True,
                Sony_IMX571_effective_pixels='6252 x 4176; not identical to Ricoh saved crop 6192 x 4128'),
      source_urls=['https://www.ricoh-imaging.co.jp/english/products/gxr/specs.html',
        'https://www.ricoh-imaging.co.jp/english/products/gr-4/feature/',
        'https://www.sony-semicon.com/files/62/pdf/p-13_IMX571BQR_Flyer.pdf'],
      sensor_model_inference_is_not_a_confirmed_manufacturer_statement=True))
    print('diagnostics complete; frozen inputs',c.verify())


if __name__=='__main__':main()
