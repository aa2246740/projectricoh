"""Select daylight through the original menu, then run HC BW restart checks."""
import argparse
import json
from pathlib import Path
import sys
import traceback

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
from repro_flow import phase


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version',choices=('g154','g155c'),required=True)
    p.add_argument('--source',type=Path,required=True)
    a=p.parse_args();prefix='r2-daylight-'+a.version;rows=[]
    out=HERE/'evidence'/(prefix+'-round.json');assert not out.exists()
    result=dict(status='OPEN',version=a.version,phases=rows,native_state_presets=[])
    try:
        phase('native_menu_probe.py',['--source',a.source,'--name',prefix+'-wb','--engine',a.version,
            '--wb-preset','daylight','--keys',''],prefix+'-wb-run',rows)
        phase('wb_case_flow.py',['--version',a.version,'--source',HERE/'local'/(prefix+'-wb-final.pkl.z'),
            '--wb-evidence',HERE/'evidence'/(prefix+'-wb.json'),'--prefix',prefix],prefix+'-case-run',rows)
        result['status']='PASS'
    except BaseException as exc:
        result.update(error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc())
        raise
    finally:out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
