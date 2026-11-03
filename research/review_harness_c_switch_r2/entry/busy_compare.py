"""Compare the complete retained g139 reporter result, including its verdict."""
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from support import enable,emit,sha
from compare_products import compare_values

def main():
    enable();base=HERE/'local/busy';values={};files={};metrics={}
    excluded=('seconds','started_ns','ended_ns');timing={}
    for side in ('python','c'):
        path=base/side/'tests/local/busy-settings-exit/checks/50mm-busy-settings-exit.json'
        value=json.loads(path.read_text());assert value['status']=='OBSERVED_P1'
        timing[side]={key:value.pop(key) for key in excluded};values[side]=value;files[side]=sha(path)
        metrics[side]=[json.loads(p.read_text()) for p in sorted((base/side/'metrics').glob('process-*.json'))]
        assert sum(row['packets'] for row in metrics[side])==20932506
        assert json.loads((base/side/'metadata.json').read_text())['class_module']=='python_backend'
    proof=compare_values(values['python'],values['c'])
    emit(base/'comparison.json',{'passed':proof['equal'],'statuses':{s:v['status'] for s,v in values.items()},'comparison':proof,'excluded_timing_fields':['/'+k for k in excluded],'timings':timing,'raw_sha256':files,'metrics':metrics})
    print(json.dumps({'passed':proof['equal'],'statuses':{s:v['status'] for s,v in values.items()},'compared_values':proof['compared_values']}),flush=True)
    return 0 if proof['equal'] else 1
if __name__=='__main__':raise SystemExit(main())
