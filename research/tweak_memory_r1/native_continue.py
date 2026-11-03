"""Resume the observed original-menu request with its transport notice model."""
import json
from pathlib import Path
import sys
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from repro_flow import phase


def main():
    out=HERE/'evidence/r2-native-continue.json';assert not out.exists();rows=[]
    result=dict(status='OPEN',phases=rows,native_state_presets=[],camera_WB_parameters_supplied=0)
    try:
        phase('native_menu_probe.py',['--source',HERE/'local/r2-native-menu-stopped.pkl.z',
            '--name','r2-native-menu-r2','--engine','native','--keys','','--settle',12000000],
            'r2-native-menu-r2-run',rows)
        result['status']='OBSERVED'
    except BaseException as exc:result.update(error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc())
    finally:out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
