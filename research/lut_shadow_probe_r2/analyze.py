"""Analyze transcribed eight-line L3 results with measured phone-video intervals."""
from pathlib import Path
import argparse
import json
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C

def analyze(doc,manifest):
    if doc['dat_sha256']!=manifest['dat_sha256']: raise ValueError('DAT identity differs')
    if doc.get('status')!='OK' or doc.get('full_pairs')!=6106112: raise ValueError('partial/failed samples are lower bounds only')
    refs=doc['references']
    if len(refs)!=2: raise ValueError('two phone references required')
    tau=[]
    for ref in refs:
        ticks=ref.get('ticks')
        if 'start' in ref and 'end' in ref:
            raw=(ref['end']-ref['start'])&0xffffffff
            if ticks is not None and raw!=ticks: raise ValueError('reference delta differs')
            ticks=raw
        seconds=ref['phone_seconds']
        if not 20000<=ticks<=45000 or not 20<=seconds<=45: raise ValueError('reference range')
        tau.append(seconds/ticks)
    if max(tau)/min(tau)>1.05: raise ValueError('external references disagree by more than 5 percent')
    if any(abs(value-0.001)>0.00005 for value in tau): raise ValueError('nominal millisecond tick not confirmed')
    samples=doc['pairs']
    if len(samples)!=3: raise ValueError('three OFF/ON pairs required')
    for sample in samples:
        if not sample.get('full') or sample.get('pairs')!=6106112:
            raise ValueError('failed/incomplete full-frame result')
        if sample.get('saved_ok') is not True: raise ValueError('owner confirmation of both saved photos required')
        for key in ('off_encoder_status','encoder_status'):
            word=sample.get(key)
            if not isinstance(word,int) or not 0<=word<=65535: raise ValueError('native encoder word outside observed u16 contract')
        if not 0<=sample['kernel_ticks']<0x80000000: raise ValueError('kernel tick range')
        if not -0x7fffffff<=sample['increment_ticks']<=0x7fffffff: raise ValueError('increment tick range')
        if len(sample['checksum'])!=8 or any(c not in '0123456789abcdefABCDEF' for c in sample['checksum']):
            raise ValueError('checksum missing')
    scale=statistics.median(tau)
    def stats(values): return dict(min=min(values),median=statistics.median(values),max=max(values),all=values)
    return dict(status='VALID_FULL_FRAME_FIELD_TIMING',dat_sha256=manifest['dat_sha256'],
        seconds_per_tick=stats(tau),kernel_seconds=stats([s['kernel_ticks']*scale for s in samples]),
        H40_H41_increment_seconds=stats([s['increment_ticks']*scale for s in samples]),
        kernel_definition='Whole shadow window including checksum and budget polling; excludes card/DAT first load.',
        boundary='H41 is encoder-wrapper return, not completed card save; shadow output does not include CPU-to-JPEG DMA handoff cost.')

def main():
    p=argparse.ArgumentParser(); p.add_argument('input',type=Path); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    C.setup(); C.gate('field-analysis')
    result=analyze(json.loads(a.input.read_text()),json.loads((C.PACKAGE/'local/MANIFEST.json').read_text()))
    C.save(a.output,result); print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__': main()
