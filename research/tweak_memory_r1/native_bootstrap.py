"""Observe a fresh original-menu session before resuming the unit matrix stage."""
import json
from pathlib import Path
import sys
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from repro_flow import phase


def main():
    out=HERE/'evidence/r2-native-bootstrap.json';assert not out.exists();rows=[]
    result=dict(status='OPEN',phases=rows,native_state_presets=[],settings_source=None)
    try:
        phase('cold_run.py',['--name','r2-native-init','--unit','mount','--empty-card',
            '--budget',250000000,'--timeout',7200],'r2-native-init-run',rows)
        phase('native_menu_probe.py',['--source',HERE/'local/r2-native-init-session.pkl.z',
            '--name','r2-native-menu','--engine','native','--keys','MENU'],'r2-native-menu-run',rows)
        result['status']='OBSERVED'
    except BaseException as exc:
        result.update(error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc())
    finally:out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
