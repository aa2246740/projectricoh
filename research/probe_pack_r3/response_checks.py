"""Exercise seven response classes on prior real measurements, including stale labels."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *
from response_identity import identify,attach_label,KEYS
import numpy as np


def main():
    guard();f=load(ROOT/'research/probe_pack_r1/field_20261103.py','probe3_field_model')
    f.OUT=ROOT/'research/probe_pack_r2/local/field_probe2_20261103'
    os.environ.update(TMPDIR=str(TMP),MPLCONFIGDIR=str(TMP/'mpl'))
    model=f.FieldModel();expected=json.loads((HERE/'local/expected.json').read_text())['M']
    for key in KEYS:
        entry=bytes.fromhex(expected[key]['entry_hex'])
        model.curves[key]=np.asarray([list(entry[379:412]),list(entry[82:115]),list(entry[412:445])],float)
    inputs={};samples=[]
    def read(relative):
        path=ROOT/relative;inputs[relative]=sha(path.read_bytes());return json.loads(path.read_text())
    old=read('research/probe_pack_r1/local/ramp_field_20261103/measure-0.5.json')
    negative=read('research/probe_pack_r2/local/field_probe2_20261103/measure-0.5.json')
    for data,frames,key_of in [(old,range(1927,1933),lambda row:row['channel']+'P'),
                               (negative,range(1935,1938),lambda row:row['label'])]:
        for number in frames:
            frame='R805'+str(number)
            rows=[r for r in data['points'] if r['frame']==frame and r['gray'] and not r['excluded']]
            assert rows
            samples.append((frame,key_of(rows[0]),np.asarray([r['x_B'] for r in rows]),
                np.asarray([r['observed_rgb'] for r in rows])))
    drift=old['drift']
    x=np.asarray(drift['first_conditioned_input'])*np.asarray(drift['last_raw_wb'])/np.asarray(drift['first_raw_wb'])
    samples.append(('R8051933-A-drift','A',x[:49],np.asarray(drift['corrected_rgb'])[:49]))
    results=[]
    for frame,wanted,x,observed in samples:
        baseline=model.predict(x)
        templates={key:model.predict(x,key)-baseline for key in KEYS}
        response=identify(observed,x,templates)
        no_label=attach_label(response)
        stale=attach_label(response,dict(shot=1,entry='A'))
        wrong=attach_label(response,dict(shot=8,entry='BN' if wanted=='A' else 'A'))
        for result in (no_label,stale,wrong):
            assert result['response_identity']==response['response_identity'] and result['fits']==response['fits']
        assert wrong['label_response_conflict']==(response['response_identity']!='unknown')
        results.append(dict(frame=frame,expected_from_prior_response_analysis=wanted,
            measured=stale,no_label=no_label['response_identity'],deliberate_wrong_label=wrong['label_response_conflict']))
        print(json.dumps(dict(frame=frame,wanted=wanted,got=response['response_identity'],
            amplitude=response['fits'][response['best_template']]['amplitude'],margin=response['margin'])),flush=True)
    save(HERE/'local/response-checks-detail.json',dict(frames=results,source_files=inputs,
        model_sources=model.inputs,templates_use_final_DAT=True,label_not_used=True))
    assert all(r['expected_from_prior_response_analysis']==r['measured']['response_identity'] for r in results)
    assert {r['measured']['response_identity'] for r in results}=={'A',*KEYS}
    save(HERE/'evidence/response.json',dict(status='PASS',dat_sha256=sha((PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes()),
        real_frames=len(results),candidate_classes=7,missing_and_stale_labels_do_not_change_response=True,
        deliberate_conflicts_retained=True,detail_sha256=sha((HERE/'local/response-checks-detail.json').read_bytes()),
        future_capture_success_not_claimed=True,order_or_count_prior=False))


if __name__=='__main__':main()
