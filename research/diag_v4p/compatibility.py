"""Preserve the reviewed version 4 contract independently of version 6."""
from pathlib import Path
import copy
import gzip
import hashlib
import io
import json
import os
import sys
from contextlib import redirect_stdout
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s
import gate as v
import gate_cases as f
old=v.g


def call(text,profile,capture,expected,label,stream,missing=False):
    folder=s.TMP/'compatibility';folder.mkdir(exist_ok=True)
    (folder/'profile.json').write_bytes(v.canonical(profile));(folder/'capture.json').write_bytes(v.canonical(capture))
    argv=['-','--profile',str(folder/'profile.json'),'--profile-sha256','0'*64 if missing else v.digest(profile),
       '--capture',str(folder/'capture.json'),'--capture-sha256',v.digest(capture)]
    sys.stdout.flush();sys.stderr.flush();readfd,writefd=os.pipe();pid=os.fork()
    if pid==0:
        try:
            os.close(readfd);sys.stdin=io.StringIO(text);out=io.StringIO()
            with redirect_stdout(out):code=old.main(argv)
            result=json.loads(out.getvalue())
            if (code==0)!=result['records_complete']:os._exit(91)
            if code and (result['verdict']!='不完整、不通过' or any(result[k]!='undetermined' for k in ('capacity','h43','time'))):os._exit(92)
            os.write(writefd,json.dumps(dict(code=code,complete=result['records_complete'],reasons=result.get('reasons'))).encode());os._exit(code)
        except BaseException:os._exit(93)
    os.close(writefd);parts=[]
    while True:
        chunk=os.read(readfd,65536)
        if not chunk:break
        parts.append(chunk)
    os.close(readfd);_,status=os.waitpid(pid,0);code=os.waitstatus_to_exitcode(status)
    row=dict(name=label,exit_code=code,expected=expected,input_sha256=hashlib.sha256(text.encode()).hexdigest(),result=json.loads(b''.join(parts)) if parts else {})
    stream.write(json.dumps(row,ensure_ascii=False)+'\n');assert code==expected,row


def main():
    s.enable();cases=f.F.complete_cases();profiles={v.digest(c['profile']):c['profile'] for c in cases}
    counts=dict(positive=0,historical_positive=0,historical_negative=0,new_fields_rejected=0)
    basecap=f.F.make_capture(cases[0]['doc'])
    with gzip.open(s.HERE/'evidence/legacy-cli.jsonl.gz','wt') as stream:
        for case in cases:
            doc=case['doc'];profile=case['profile'];cap=f.F.make_capture(doc)
            call(v.canonical(doc).decode(),profile,cap,0,case['name'],stream);counts['positive']+=1
        trace=s.ROOT/'research/body_v4_design/r5/history-inputs.jsonl.gz'
        with gzip.open(trace,'rt') as source:
            for i,line in enumerate(source):
                item=json.loads(line);doc=item['input'];expected=0 if item['row']['complete'] else 2
                profile=profiles.get(doc.get('profile_sha256'),cases[0]['profile']) if expected==0 and type(doc) is dict else cases[0]['profile']
                cap=f.F.make_capture(doc) if expected==0 else copy.deepcopy(basecap)
                cap['record_sha256']=v.digest(doc)
                issue=item['row'].get('issue') or {}
                call(v.canonical(doc).decode(),profile,cap,expected,'history/'+str(i),stream,missing=issue.get('code')=='independent_profile_required')
                counts['historical_positive' if expected==0 else 'historical_negative']+=1
                if i and i%1000==0:print('legacy',i,flush=True)
        doc=copy.deepcopy(cases[0]['doc']);doc['BOOT_CURRENT']={};cap=copy.deepcopy(basecap);cap['record_sha256']=v.digest(doc)
        call(v.canonical(doc).decode(),cases[0]['profile'],cap,2,'version4_rejects_boot_fields',stream);counts['new_fields_rejected']+=1
    s.save(s.HERE/'evidence/legacy-summary.json',dict(**counts,old_gate_sha256=s.sha(s.ROOT/'research/body_v4_design/r3/diag_gate.py'),
       derived_contract_sha256=s.sha(s.ROOT/'research/body_v4_design/r5/derived_contract.py'),
       trace_sha256=s.sha(s.ROOT/'research/body_v4_design/r5/history-inputs.jsonl.gz'),actual_public_cli_os_exit=True))
    print(json.dumps(counts))

if __name__=='__main__':main()
