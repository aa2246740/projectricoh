"""Literal field-analysis examples and rejected incomplete receipts."""
from pathlib import Path
import copy
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
from analyze import analyze

def main():
    C.setup(); C.gate('check-field-analysis')
    manifest=json.loads((C.PACKAGE/'local/MANIFEST.json').read_text())
    doc=dict(dat_sha256=manifest['dat_sha256'],status='OK',full_pairs=6106112,
        references=[dict(ticks=30000,phone_seconds=30),dict(ticks=30000,phone_seconds=30)],
        pairs=[dict(kernel_ticks=k,increment_ticks=d,checksum=checksum,off_encoder_status=4,encoder_status=20,saved_ok=True,full=True,pairs=6106112)
            for k,d,checksum in ((2000,2100,'00000001'),(3000,3100,'00000002'),(4000,4100,'00000003'))])
    result=analyze(doc,manifest)
    assert result['kernel_seconds']['all']==[2.0,3.0,4.0]
    assert result['H40_H41_increment_seconds']['median']==3.1
    wrap=copy.deepcopy(doc)
    for ref in wrap['references']:
        ref.update(start=0xffffc000,end=(0xffffc000+30000)&0xffffffff)
    assert analyze(wrap,manifest)==result
    rejected=[]
    mutations=[('DAT',lambda d:d.update(dat_sha256='bad')),
        ('lower-bound',lambda d:d.update(status='LOWER BOUND')),
        ('missing-reference',lambda d:d['references'].pop()),
        ('clock-rate',lambda d:d['references'][0].update(phone_seconds=3)),
        ('clock-disagree',lambda d:d['references'][1].update(phone_seconds=33)),
        ('missing-pair',lambda d:d['pairs'].pop()),
        ('partial',lambda d:d['pairs'][1].update(full=False)),
        ('wrong-count',lambda d:d['pairs'][1].update(pairs=6106111)),
        ('encoder-word-range',lambda d:d['pairs'][1].update(encoder_status=65536)),
        ('off-encoder-word-range',lambda d:d['pairs'][1].update(off_encoder_status=65536)),
        ('save-unconfirmed',lambda d:d['pairs'][1].update(saved_ok=False)),
        ('missing-checksum',lambda d:d['pairs'][1].update(checksum=''))]
    for name,mutate in mutations:
        broken=copy.deepcopy(doc); mutate(broken)
        try: analyze(broken,manifest)
        except ValueError as error: rejected.append(dict(case=name,reason=str(error)))
        else: raise AssertionError(name)
    negative=copy.deepcopy(doc); negative['pairs'][0]['increment_ticks']=-10
    assert analyze(negative,manifest)['H40_H41_increment_seconds']['all'][0]==-0.01
    C.save(C.LOCAL/'analysis-check.json',dict(status='PASS',dat_sha256=manifest['dat_sha256'],
        literal_seconds=result,wrap_equal=True,negative_preserved=True,rejected=rejected,
        boundary='Synthetic arithmetic examples, not camera timing.'))
    print(json.dumps(dict(status='PASS',rejected=len(rejected))))

if __name__=='__main__': main()
