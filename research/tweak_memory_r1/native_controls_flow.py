"""Observe original WB presets, compensation, and the three Setting 1 sliders."""
import json
from pathlib import Path
import sys
import traceback

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from repro_flow import phase


def main():
    out=HERE/'evidence/r2-native-controls-flow.json';assert not out.exists();rows=[]
    result=dict(status='OPEN',phases=rows,native_state_presets=[],camera_setting_writes_by_runner=0,sliders=[])
    def run(name,source,keys='',extra=()):
        phase('native_menu_probe.py',['--source',source,'--engine','native','--name',name,'--keys',keys,*extra],name+'-run',rows)
        receipt=json.loads((HERE/'evidence'/(name+'.json')).read_text())
        assert receipt['status']=='OBSERVED' and receipt['camera_setting_writes_by_runner']==0
        return HERE/'local'/(name+'-final.pkl.z'),receipt
    def block(receipt):return (ROOT/receipt['settings']['path']).read_bytes()
    def delta(before,after):
        return [dict(offset=hex(i),before=x,after=y) for i,(x,y) in enumerate(zip(before,after)) if x!=y]
    try:
        source=HERE/'local/r2-native-wb-daylight-final.pkl.z'
        source,auto=run('r2-native-auto',source,extra=('--wb-preset','auto'))
        assert block(auto)[0x395]==0
        source,daylight=run('r2-native-auto-daylight',source,extra=('--wb-preset','daylight'))
        baseline=block(daylight);assert baseline[0x395]==1 and baseline[0x6dd:0x6df]==b'\x09\x09'
        result['auto_to_daylight']=dict(status='PASS',before=0,after=1,S_changes=delta(block(auto),baseline),
            gate_fields_unchanged=all(block(auto)[i]==baseline[i] for i in (8,0x36e,0x6dd,0x6de)))
        phase('native_wb_check.py',[],'r2-native-wb-setter-run',rows)
        neutral_source=source
        try:
            _,compensation=run('r2-native-wb-compensation',neutral_source,'RIGHT,UP,OK',('--shoot-row','wb-compensation'))
            final=block(compensation)
            assert final[0x395]==1 and final[0x36e]==baseline[0x36e]
            assert final[0x6dd:0x6df]!=baseline[0x6dd:0x6df]
            result['WB_compensation']=dict(status='PASS',S_changes=delta(baseline,final),
                    offsets_before=list(baseline[0x6dd:0x6df]),offsets_after=list(final[0x6dd:0x6df]),
                    WB_preset_unchanged=True,evidence='r2-native-wb-compensation.json')
        except Exception as exc:result['WB_compensation']=dict(status='OPEN',error=type(exc).__name__+': '+str(exc))
        try:
            opened,entry=run('r2-native-setting1-open',source,'ADJ,ADJ_RIGHT,ADJ_RIGHT,DOWN,DOWN,DOWN,DOWN,RIGHT')
            entry_block=block(entry)
            result['setting1_selection_changes']=delta(baseline,entry_block)
            changed_parameters=[]
            for label,keys in [('saturation','RIGHT,OK,OK'),('contrast','DOWN,RIGHT,OK,OK'),('sharpness','DOWN,DOWN,RIGHT,OK,OK')]:
                try:
                    _,receipt=run('r2-native-'+label,opened,keys)
                    final=block(receipt)
                    fields=[i for i in (0x36f,0x370,0x371) if final[i]!=entry_block[i]]
                    assert len(fields)==1,(label,fields)
                    assert receipt['final']['state']==5,'The original slider confirmation did not return to shooting.'
                    assert final[0x395]==1 and final[0x6dd:0x6df]==b'\x09\x09'
                    changed_parameters.extend(fields)
                    result['sliders'].append(dict(name=label,status='PASS',parameter_offset=hex(fields[0]),
                        S_changes=delta(entry_block,final),selector_before=entry_block[0x36e],selector_after=final[0x36e],
                        evidence='r2-native-'+label+'.json'))
                except Exception as exc:
                    result['sliders'].append(dict(name=label,status='OPEN',error=type(exc).__name__+': '+str(exc)))
            result['sliders_status']='PASS' if len(set(changed_parameters))==3 else 'OPEN'
        except Exception as exc:result['sliders_status']='OPEN';result['sliders_error']=type(exc).__name__+': '+str(exc)
        if result['sliders_status']==result['WB_compensation']['status']=='PASS':result['status']='PASS'
    except BaseException as exc:
        result.update(error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc())
        raise
    finally:out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
