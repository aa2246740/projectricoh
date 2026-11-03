#!/usr/bin/python3 -I -B
"""Two changed fields, updated record identity, unchanged bottom-level sources."""
import copy
import hashlib
import itertools
import json
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from fixtures import gate,encode,load_module
from public_runner import warm,call
from run_mutations import rebound,assert_incomplete
SCRATCH=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v4-r5')

def variants(base):
    for left,right in itertools.combinations(range(11),2):
        doc=copy.deepcopy(base)
        doc['records'][left]['valid']+=1;doc['records'][right]['valid']+=1
        yield f'count_pair_{left}_{right}',doc
    for ri in (5,6):
        for ci in range(11):
            doc=copy.deepcopy(base);category=doc['records'][ri]['categories'][ci]
            count=category['count']
            if count<18:
                category['addresses'].append(category['base']+count*category['stride'])
                category['count']=count+1
            else:
                category['addresses'].pop();category['count']=count-1
            yield f'count_addresses_{ri}_{category["id"]}',doc

def main():
    assert os.getpriority(os.PRIO_PROCESS,0)>=10 and SCRATCH.is_dir()
    old_path=HERE/'before/r3/diag_gate.py'
    old=load_module('prior_gate_for_pairs',old_path)
    index=gate.read_json(HERE/'positive-index.json');rows=[];prior_accepted=0
    ppath=SCRATCH/'coupled-profile.json';cpath=SCRATCH/'coupled-capture.json'
    for item in index:
        stem=item['stem'];profile,capture=warm(item)
        base=gate.read_json(HERE/'positive'/(stem+'-record.json'))
        raw_profile=gate.read_json(HERE/'positive'/(stem+'-profile.json'))
        old_ref=old.load_profile(raw_profile,item['profile_sha256'])
        prior_base_complete=old.classify(base,old_ref)['records_complete']
        ppath.write_bytes(profile.serialized)
        for name,doc in variants(base):
            content=encode(doc);digest=hashlib.sha256(content).hexdigest()
            current=rebound(capture,digest)
            actual=gate.classify(doc,profile,current)
            try:
                assert_incomplete(actual)
                assert actual['reasons']['record'][0]['code']!='frozen_record_changed'
                cpath.write_bytes(current.serialized)
                gate.capture_text(current.serialized.decode(),current.digest)
                argv=['-','--profile',str(ppath),'--profile-sha256',profile.digest,
                      '--capture',str(cpath),'--capture-sha256',current.digest]
                code,out=call(argv,content.decode())
                assert code==2 and out['stderr']=='',(name,code,out)
                result=json.loads(out['stdout']);assert_incomplete(result)
                assert result['reasons']['record'][0]['code']!='frozen_record_changed'
            except BaseException:
                (HERE/'coupled-failure.json').write_text(json.dumps(dict(base=item,name=name,input=doc),ensure_ascii=False,indent=2)+'\n')
                raise
            previous=prior_base_complete and old.classify(doc,old_ref)['records_complete']
            prior_accepted+=previous
            rows.append(dict(base=stem,name=name,input_sha256=digest,capture_sha256=current.digest,
                             api_complete=False,cli_exit=code,issue=actual['reasons']['record'][0],
                             prior_base_complete=prior_base_complete,prior_accepted=previous))
            if len(rows)%500==0:print(json.dumps(dict(coupled_progress=len(rows))),flush=True)
    assert len(rows)==54*77==4158
    result=dict(classification='host_two_field_source_consistency_only',cases=rows,
                negative_cases=len(rows),positive_bases=54,updated_record_digest=True,
                original_source_observations_retained=True,all_rejected=True,
                prior_accepted_on_valid_prior_bases=prior_accepted,
                checker_sha256=hashlib.sha256((HERE.parent/'r3/diag_gate.py').read_bytes()).hexdigest(),
                contract_sha256=hashlib.sha256((HERE/'derived_contract.py').read_bytes()).hexdigest(),
                runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                prior_checker_sha256=hashlib.sha256(old_path.read_bytes()).hexdigest(),
                public_runner_sha256=hashlib.sha256((HERE/'public_runner.py').read_bytes()).hexdigest())
    (HERE/'coupled-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
