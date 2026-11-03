#!/usr/bin/python3 -I -B
"""Generate all declared edits and check both public text and OS CLI behavior."""
import argparse
from dataclasses import replace
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from fixtures import gate,encode
from mutations import generate
from public_runner import arguments,warm,call


def rebound(capture,digest):
    raw=capture.serialized.replace(capture.record_sha256.encode(),digest.encode(),1)
    return gate.FrozenCapture(hashlib.sha256(raw).hexdigest(),digest,raw)


def semantic(text,profile,capture):
    try:doc=gate.parse_json(text)
    except (gate.InvalidRecord,json.JSONDecodeError) as error:
        return gate.incomplete(error.path,error.code) if isinstance(error,gate.InvalidRecord) else gate.incomplete('$','json_or_file_invalid')
    digest=hashlib.sha256(encode(doc)).hexdigest()
    return gate.classify(doc,profile,rebound(capture,digest))


def assert_incomplete(actual):
    assert actual['records_complete'] is False and actual['record_stage']=='undetermined',actual
    assert actual['verdict']=='不完整、不通过',actual
    assert [actual[k] for k in ('capacity','h43','time')]==['undetermined']*3,actual
    assert [actual[k] for k in ('read_interval','control_interval','crc_interval')]==[None]*3,actual
    assert actual['er_ownership']=='not_established_by_diag'
    assert actual['h42_time']=='requires_final_v4_measurement'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--limit',type=int)
    parser.add_argument('--write-evidence',action='store_true')
    args=parser.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)>=10
    indices=json.loads((HERE/'positive-index.json').read_text())
    total=0;semantic_count=0;positive_count=0;groups={};base_results=[]
    started=time.monotonic();trace_hash=hashlib.sha256()
    target=HERE/('mutation-pilot.jsonl.gz' if args.limit else 'mutation-results.jsonl.gz')
    with gzip.open(target,'wb',compresslevel=1) as trace:
        for index in indices:
            profile,capture=warm(index);argv=arguments(index)
            raw=(HERE/'positive'/(index['stem']+'-record.json')).read_bytes()
            doc=gate.parse_json(raw.decode())
            complete=gate.validate_text(raw.decode(),profile,capture)
            assert complete['records_complete'] is True,(index['name'],complete)
            code,out=call(argv,raw.decode())
            assert code==0 and out['stderr']=='' and json.loads(out['stdout'])==complete,(index['name'],code,out)
            positive_count+=1;chain=hashlib.sha256();local_semantic=0
            for mutation in generate(doc):
                if mutation.get('summary'):
                    base_results.append(dict(stem=index['stem'],name=index['name'],
                        input_sha256=index['record_sha256'],mutations=mutation['generated'],
                        counts=mutation['counts'],noops=mutation['noops'],semantic_checks=local_semantic,
                        checked_input_chain_sha256=chain.hexdigest()))
                    break
                text=mutation['data'].decode()
                try:
                    actual=gate.validate_text(text,profile,capture)
                    assert_incomplete(actual)
                    if mutation['semantic_reject']:
                        result=semantic(text,profile,capture);assert_incomplete(result)
                        assert result['reasons']['record'][0]['code']!='frozen_record_changed'
                        semantic_count+=1;local_semantic+=1
                    code,out=call(argv,text)
                    assert code==2 and out['stderr']=='' and json.loads(out['stdout'])==actual,(code,out)
                except BaseException:
                    (HERE/'mutation-failure.json').write_text(json.dumps(dict(index=index,
                        mutation={k:v for k,v in mutation.items() if k!='data'},input=text),ensure_ascii=False,indent=2)+'\n')
                    raise
                chain.update(bytes.fromhex(mutation['input_sha256']))
                row=dict(base=index['stem'],ordinal=mutation['ordinal'],operation=mutation['operation'],
                         path=mutation['path'],input_sha256=mutation['input_sha256'],
                         semantic_checked=mutation['semantic_reject'],api_complete=False,cli_exit=code)
                line=json.dumps(row,separators=(',',':')).encode()+b'\n'
                trace.write(line);trace_hash.update(line)
                total+=1;groups[mutation['operation']]=groups.get(mutation['operation'],0)+1
                if total%1000==0:
                    print(json.dumps(dict(progress=total,positive_bases=positive_count,semantic_checks=semantic_count,
                                          elapsed_seconds=round(time.monotonic()-started,2))),flush=True)
                if args.limit and total>=args.limit:break
            if args.limit and total>=args.limit:break
    summary=dict(classification='host_synthetic_frozen_record_contract_only',
        completed=not args.limit,mutants=total,positive_cases=positive_count,
        semantic_checks_with_updated_record_digest=semantic_count,
        operations=groups,bases=base_results,public_cli_children=total+positive_count,
        public_cli_incomplete_exit=2,public_cli_complete_exit=0,
        maximum_active_check_children=1,child_mode='fork; real public main(argv), stdin and OS exit code; parent waits',
        checker_sha256=hashlib.sha256((HERE.parent/'r3/diag_gate.py').read_bytes()).hexdigest(),
        derived_contract_sha256=hashlib.sha256((HERE/'derived_contract.py').read_bytes()).hexdigest(),
        generator_sha256=hashlib.sha256((HERE/'mutations.py').read_bytes()).hexdigest(),
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        public_runner_sha256=hashlib.sha256((HERE/'public_runner.py').read_bytes()).hexdigest(),
        decoded_trace_sha256=trace_hash.hexdigest(),trace=str(target.name),
        trace_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),er_ownership_passes=0,h42_time_passes=0)
    output=HERE/('mutation-pilot.json' if args.limit else 'mutation-summary.json')
    output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('bases',)},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
