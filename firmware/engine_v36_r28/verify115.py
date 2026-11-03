"""Rerunnable host acceptance; preserve raw subprocess logs under this task only."""
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE/'candidate'))
import common as c
import verify_v34c as v

PHASES = ('basic','first','ctl','iso','rpc-faults','t','quarantine','irom','blackbox',
          'legacy','store-fault','neighbour','service-quarantine','log-fault',
          'publish-failure','conflict','accepted-f02','daily','rejected','r33','same-conflict')


def main():
    assert len(sys.argv)==2 and sys.argv[1] in ('compile','seed','suites','history','decode')
    phase=sys.argv[1]
    if phase=='compile':
        v.compile_all()
    elif phase=='seed':
        v.OLD[114]=HERE/'local/reproduced114'
        for unit in range(3):
            v.run('seed115',unit,str(HERE/f'local/seed-{unit}.BIN'))
            v.run('fallback115',unit)
            v.run('update115',unit,generation=114)
            v.run('update115',unit,'1',generation=114)
            v.run('bindings115',unit,generation=114)
            v.run('sticky115',unit,str(HERE/f'local/sticky-{unit}'))
            v.run('adjacency115',unit)
        print('PASS three-unit native seed/fallback, exact 114->115 update with old OK conflict, GXTS/GXLS bindings, sticky seed, adjacency',flush=True)
    elif phase=='suites':
        for name in PHASES:
            c.run(['/usr/bin/python3','-I','-B',c.HERE/'verify_v34c.py',name],
                  'suite-'+name,timeout=1800)
            print('PASS '+name,flush=True)
    elif phase=='history':
        c.run(['/usr/bin/python3','-I','-B',c.HERE/'verify_history34c.py'],'suite-history',timeout=1800)
        print('PASS history',flush=True)
    else:
        spec=importlib.util.spec_from_file_location('decoder114',HERE/'decode_blackbox.py')
        decoder=importlib.util.module_from_spec(spec);spec.loader.exec_module(decoder)
        for unit in range(3):
            for source in (HERE/f'local/seed-{unit}.BIN',v.OUT/f'GXRBX-{unit}.BIN'):
                value=decoder.read_log(source.read_bytes())
                assert value['header']['engine_generation']==115
                seed=value['seed_inputs'];assert seed and seed['ui_state_capacity']==256
                assert seed['table_word']=='0x2022F56C' and seed['view_array']=='0x205A279C'
                (source.with_suffix('.decoded.json')).write_text(json.dumps(value,indent=2)+'\n')
            for boot,kind in ((0,0),(1,4)):
                source=HERE/f'local/sticky-{unit}-boot{boot}.BIN'
                value=decoder.read_log(source.read_bytes())
                assert value['header']['engine_generation']==115
                assert value['first_seed_inputs']['type_byte']==kind
                assert value['seed_inputs']['type_byte']==5
                assert value['first_seed_inputs']['event_sequence']<value['seed_inputs']['event_sequence']
                source.with_suffix('.decoded.json').write_text(json.dumps(value,indent=2)+'\n')
        for unit in (0,2):
            source=ROOT/f'firmware/engine_v35_publish/local/seed-{unit}.BIN'
            value=decoder.read_log(source.read_bytes())
            assert value['header']['engine_generation']==114 and value['first_seed_inputs'] is None
        card=ROOT/'artifacts/card-b-mount/card-b-after-v34c-first-run-20261026T032356Z'
        assert (card/'root/GXRCE.OK').read_bytes()==(c.UPSTREAM/'acceptance/local/full-r11/GXRCE.DAT').read_bytes()
        result=[]
        for name in ('GXRBX0','GXRBX1'):
            data=decoder.read_log((card/'root'/f'{name}.BIN').read_bytes())
            assert data['seed_inputs'] is None and data['header']['engine_generation']==113
            events=data['events'];assert not any(e['event']==3 and e['phase']==16 for e in events)
            assert data['publish']['stage']==15 and data['publish']['rows']==0
            assert data['publish']['top_state']==0x2022f71c
            assert any(e['event']==5 and e['a']==4 and e['native_result']==-1 for e in events)
            result.append(dict(name=name,publish=data['publish'],events=events))
        (HERE/'local/field-evidence.json').write_text(json.dumps(result,indent=2)+'\n')
        print('PASS decoder: six gen115 host logs, six first/latest two-boot logs, two gen114 host logs, two gen113 field logs',flush=True)


if __name__=='__main__':
    main()
