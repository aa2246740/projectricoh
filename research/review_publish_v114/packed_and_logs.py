"""Rerun packed-instruction cases and decode frozen field/independent host logs."""
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TASK=ROOT/'firmware/engine_v35_publish'

def load(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def main():
    machine=load(TASK/'machine114.py','review_packed_cases')
    machine.OUT=HERE/'packed_machine'
    machine.main()
    decoder=load(TASK/'decode_blackbox.py','review_decoder')
    data=[]
    paths=[(ROOT/'artifacts/card-b-mount/card-b-after-v34c-first-run-20261026T032356Z/root')/(n+'.BIN')
        for n in ('GXRBX0','GXRBX1')]
    paths += [HERE/'host'/f'{case}-{unit}.BIN' for case in ('seed114','blackbox') for unit in (0,2)]
    for source in paths:
        result=decoder.read_log(source.read_bytes());data.append(dict(source=str(source.relative_to(ROOT)),decoded=result))
        assert result['header']['engine_generation'] in (113,114)
        if result['header']['engine_generation']==113:
            assert result['seed_inputs'] is None and result['publish']['stage']==15 and result['publish']['rows']==0
            assert not any(e['event']==3 and e['phase']==16 for e in result['events'])
        else:
            assert result['seed_inputs']['ui_state_capacity']==256
            assert result['seed_inputs']['table_word']=='0x2022F56C'
    (HERE/'logs_decoded.json').write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')
    print('PASS two field and four independent host black boxes',flush=True)

if __name__=='__main__':main()
