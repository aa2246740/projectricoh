#!/usr/bin/python3
"""Check physical shutter requests observed during a real BOOT colour transaction."""
import argparse
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--name',required=True);a=p.parse_args()
    E=HERE/'evidence';record=json.loads((E/(a.name+'-record.json')).read_text())
    colour=json.loads((E/(a.name+'-acceptance.json')).read_text())
    assert colour['status']=='PASS' and colour['target_bytes']==552
    shutter=record['shutter_during_real_DIRTY'];assert shutter['native_state_presets']==[]
    assert shutter['requested'] and shutter['released']
    keys=shutter['keys']
    cancelled=[raw for raw in (13,14) if any(x['raw']==raw and x['pressed']==1 and x['word']&4 and x.get('path')=='cancel' for x in keys)]
    after=shutter['after_complete'];assert after and after[0]['pressed']
    phase_start=after[0]['step']-after[0]['stop']['steps']
    restored=any(x['step']>=phase_start and x['raw']==13 and x['pressed']==1 and x['word']==2 and x.get('path')=='continue' for x in keys)
    result=dict(status='PASS' if cancelled==[13,14] and restored else 'FAIL',basis='real BOOT DIRTY writes, physical GPIO keys and actual H52 branches',
        dat_sha256=colour['dat_sha256'],native_state_presets=[],
        dirty_press_cancelled=cancelled,missing_cancelled=[x for x in (13,14) if x not in cancelled],
        clear_press_continued=restored,after_complete_phase_start=phase_start,
        after_complete_inputs=after,keys=keys,physical_inputs=shutter['inputs'],
        finding='Presses supplied during DIRTY were handled after the word cleared and continued',
        colour_target_equal=True,photo_completion='OPEN; branch continuation does not prove a complete photo')
    (E/(a.name+'-h52-acceptance.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    if result['status']!='PASS':raise SystemExit(1)


if __name__=='__main__':main()
