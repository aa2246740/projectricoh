"""Construct and mutate independently frozen BOOT_CURRENT records."""
from pathlib import Path
import copy
import gzip
import io
import json
import os
import struct
import sys
import time
import zlib
from contextlib import redirect_stdout
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s
import gate as v
F=s.load(s.ROOT/'research/body_v4_design/r5/fixtures.py','diag160_r5_fixtures')


def raw_current(unit,ready,context):
    native=bytearray(128);struct.pack_into('>HHI3I',native,0,1,128,0,0x2004a000,4096,56)
    native[22]=1;struct.pack_into('>II',native,24,0xffffffff,55)
    native[32:44]=v.UNITS[unit]+b'\x01\x51\x00\x00'
    native[44:69]=bytes((0,13,36,1,9,9))+bytes([5])*19
    struct.pack_into('>II',native,112,0x2004a000,4096)
    rows=b''.join(bytes((i*31+j)%256 for j in range(size)) for i,size in enumerate(v.SIZES))
    raw=bytearray(768);raw[128:633]=rows;raw[640:]=native
    meta=[0]*32;meta[0]=10;meta[1]=1023;meta[2]=3;meta[3]=(ready+1)&0xffffffff;meta[4]=(ready+51)&0xffffffff
    for i in range(10):meta[8+i]=(ready+2+4*i)&0xffffffff;meta[18+i]=(ready+5+4*i)&0xffffffff
    for index,key in ((6,'boot'),(7,'unit_epoch'),(29,'link_epoch'),(30,'s_epoch')):meta[index]=context[key]
    meta[28]=sum(1<<(3*i) for i in range(10));meta[31]=zlib.crc32(raw[128:])&0xffffffff
    struct.pack_into('>32I',raw,0,*meta)
    return raw.hex()


def make(case):
    legacy=copy.deepcopy(case['doc']);profile=copy.deepcopy(case['profile'])
    def shift(obj):
        if type(obj) is dict:
            for key,item in obj.items():
                if key in ('tick','start_tick','end_tick','h09','h40','h41') and type(item) is int:obj[key]=(item+200)&0xffffffff
                else:shift(item)
        elif type(obj) is list:
            for item in obj:shift(item)
    shift(legacy)
    identity=legacy['identity'];unit=identity['unit']
    ctx=dict(boot=identity['boot'],unit=unit,unit_epoch=identity['unit_epoch'],link_epoch=2,s_epoch=3,set=1,phase='P04_CURRENT')
    raw=raw_current(unit,next(x for x in legacy['records'] if x['scene']=='KEY')['ready_tick'],ctx)
    doc=dict(schema_version=6,capability='BOOT_CURRENT',legacy=legacy,current=v.expand_current(raw,ctx))
    p=dict(version=6,capability='BOOT_CURRENT',kind='synthetic_fixture',legacy=profile)
    cap=dict(version=6,kind='synthetic_fixture',record_sha256=v.digest(doc),current_source=raw,current_context=ctx,
             legacy=F.make_capture(legacy))
    return doc,p,cap


def classify(doc,p,cap):return v.classify_text(v.canonical(doc).decode(),p,v.digest(p),cap,v.digest(cap))


def frozen(doc,cap,semantic=True):
    out=copy.deepcopy(cap)
    if semantic:out['record_sha256']=v.digest(doc)
    return out


def cli(text,p,cap,expect,label,log):
    directory=s.TMP/'gate';directory.mkdir(exist_ok=True)
    for name,obj in (('profile',p),('capture',cap)):(directory/(name+'.json')).write_bytes(v.canonical(obj))
    argv=['-','--profile',str(directory/'profile.json'),'--profile-sha256',v.digest(p),
          '--capture',str(directory/'capture.json'),'--capture-sha256',v.digest(cap)]
    sys.stdout.flush();sys.stderr.flush()
    readfd,writefd=os.pipe();pid=os.fork()
    if pid==0:
        try:
            os.close(readfd);sys.stdin=io.StringIO(text);buf=io.StringIO()
            with redirect_stdout(buf):code=v.main(argv)
            out=json.loads(buf.getvalue())
            if (code==0)!=bool(out['records_complete']):os._exit(91)
            if not out['records_complete']:
                if out['verdict']!='不完整、不通过' or any(out[k]!='undetermined' for k in ('capacity','h43','time')):os._exit(92)
            os.write(writefd,json.dumps(dict(code=code,complete=out['records_complete'],reason=out.get('issue',out.get('reasons',{})))).encode())
            os.close(writefd);os._exit(code)
        except BaseException:os._exit(93)
    os.close(writefd);parts=[]
    while True:
        chunk=os.read(readfd,65536)
        if not chunk:break
        parts.append(chunk)
    os.close(readfd);_,status=os.waitpid(pid,0);code=os.waitstatus_to_exitcode(status)
    check=code==expect
    row=dict(name=label,exit_code=code,expected=expect,input_sha256=__import__('hashlib').sha256(text.encode()).hexdigest(),
       result=json.loads(b''.join(parts)) if parts else {})
    log.write(json.dumps(row,ensure_ascii=False)+'\n')
    assert check,row
    return code


def paths(value,prefix=()):
    if type(value) is dict:
        for key,item in value.items():
            yield prefix+(key,),item
            yield from paths(item,prefix+(key,))
    elif type(value) is list:
        for index,item in enumerate(value):
            yield prefix+(index,),item
            yield from paths(item,prefix+(index,))


def assign(doc,path,value,delete=False):
    obj=doc
    for key in path[:-1]:obj=obj[key]
    if delete:del obj[path[-1]]
    else:obj[path[-1]]=value


def run(mode):
    cases=F.complete_cases();out=s.HERE/'evidence';counts={};start=time.monotonic()
    directory=out/'gate-positive';directory.mkdir(exist_ok=True)
    for i,case in enumerate(cases):
        doc,p,cap=make(case);result=classify(doc,p,cap)
        assert result['records_complete'],(case['name'],result)
        for kind,data in (('record',doc),('profile',p),('capture',cap)):
            (directory/(f'{i:02d}-'+kind+'.json')).write_bytes(v.canonical(data))
    if mode=='positives':
        s.save(out/'schema-inventory.json',v.SCHEMA_INVENTORY)
        with gzip.open(out/'gate-cli-positives.jsonl.gz','wt') as log:
            for i,case in enumerate(cases):
                doc,p,cap=make(case);cli(v.canonical(doc).decode(),p,cap,0,case['name'],log)
        s.save(out/'gate-positive-summary.json',dict(accepted=len(cases),boot_early='undetermined',unique_id='undetermined'))
        print('PASS new positives',len(cases));return
    with gzip.open(out/'gate-mutations.jsonl.gz','wt') as log:
        total=0
        for ci in (0,47,48):
            base,p,cap=make(cases[ci]);items=list(paths(base['current'],('current',)))
            def test(doc,name,text=None,semantic=True):
                nonlocal total
                c=frozen(doc,cap,semantic);source=v.canonical(doc).decode() if text is None else text
                if text is not None and semantic:c['record_sha256']=__import__('hashlib').sha256(source.encode()).hexdigest()
                code=cli(source,p,c,2,str(ci)+'/'+name,log);total+=1
            for path,value in items:
                label='.'.join(map(str,path))
                if isinstance(path[-1],str):
                    doc=copy.deepcopy(base);assign(doc,path,None,True);test(doc,'delete/'+label)
                doc=copy.deepcopy(base);assign(doc,path,None);test(doc,'type/'+label)
                if type(value) is int:
                    for delta in (-1,1):
                        doc=copy.deepcopy(base);assign(doc,path,value+delta);test(doc,'integer'+str(delta)+'/'+label)
                if type(value) is str and value:
                    doc=copy.deepcopy(base);assign(doc,path,value[:-1]);test(doc,'truncate/'+label)
                if type(value) is list and value:
                    for which in ('truncate','duplicate','swap'):
                        doc=copy.deepcopy(base);change=copy.deepcopy(value)
                        if which=='truncate':change=change[:-1]
                        elif which=='duplicate':change.append(copy.deepcopy(change[0]))
                        elif len(change)>1:change[0],change[1]=change[1],change[0]
                        else:continue
                        assign(doc,path,change);test(doc,which+'/'+label)
                if type(value) is dict:
                    doc=copy.deepcopy(base);assign(doc,path,dict(value,unknown=1));test(doc,'unknown/'+label)
            for key in ('schema_version','capability'):
                doc=copy.deepcopy(base);del doc[key];test(doc,'top-delete/'+key)
            doc=copy.deepcopy(base);doc['unknown']=0;test(doc,'top-unknown')
            doc=copy.deepcopy(base);doc['capability']='BOOT_EARLY';test(doc,'early-unavailable')
            for selected in ('synthetic_fixture','sealed_native'):
                if selected==p['kind']:continue
                changed_profile=copy.deepcopy(p);changed_profile['kind']=selected
                c=frozen(base,cap);c['kind']=selected
                issue=classify(base,changed_profile,c).get('reasons',{}).get('record',[None])[0]
                assert issue and issue['code']=='wrapper_kind_mismatch',issue
                cli(v.canonical(base).decode(),changed_profile,c,2,str(ci)+'/wrapper-kind',log);total+=1
            for i in range(10):
                doc=copy.deepcopy(base);doc['current']['rows'][i]['length']+=1;doc['current']['row_bytes']+=1
                test(doc,'two-counts/'+str(i))
            text=v.canonical(base).decode();text=text.replace('"schema_version":6','"schema_version":6,"schema_version":6',1)
            test(base,'duplicate-json',text=text)
            raw=bytearray.fromhex(base['current']['raw_source'])
            for off in range(128):
                changed=bytearray(raw);changed[off]^=1
                doc=copy.deepcopy(base);doc['current']['raw_source']=changed.hex();test(doc,'source-byte/'+str(off))
            # Renew both source bindings so these cases must fail on their own semantics.
            changes=[(0,9),(4,511),(8,7),(20,1),(24,0),(28,0),(116,0),(120,0),
                (112,0x40000000|int.from_bytes(raw[112:116],'big')),
                (112,(int.from_bytes(raw[112:116],'big')&~7)|2),
                (12,int.from_bytes(raw[16:20],'big')),(32,int.from_bytes(raw[72:76],'big')),
                (648,0x2004a001),(652,4092),(752,0x2004b000),(756,4092)]
            for off,new in changes:
                changed=bytearray(raw);struct.pack_into('>I',changed,off,new)
                struct.pack_into('>I',changed,124,zlib.crc32(changed[128:])&0xffffffff)
                doc=copy.deepcopy(base);doc['current']=v.expand_current(changed.hex(),cap['current_context'])
                c=frozen(doc,cap);c['current_source']=changed.hex()
                cli(v.canonical(doc).decode(),p,c,2,str(ci)+'/raw-semantic/'+str(off)+'/'+str(new),log);total+=1
            for off in (662,672,685,686,709,760):
                changed=bytearray(raw);changed[off]^=1
                struct.pack_into('>I',changed,124,zlib.crc32(changed[128:])&0xffffffff)
                doc=copy.deepcopy(base);doc['current']=v.expand_current(changed.hex(),cap['current_context'])
                c=frozen(doc,cap);c['current_source']=changed.hex()
                cli(v.canonical(doc).decode(),p,c,2,str(ci)+'/raw-byte-semantic/'+str(off),log);total+=1
            counts[cases[ci]['name']]=total-sum(counts.values())
        # R5 mutations are tested through both the preserved version 4 and the version 6 public command.
        base,p,cap=make(cases[0]);legacy_paths=list(paths(base['legacy'],('legacy',)))
        derived_names=sys.modules['derived_contract'].DERIVED_NAMES
        legacy_derived=0
        for path,value in legacy_paths:
            field=next(part for part in reversed(path) if type(part) is str)
            derived=field in derived_names or 'categories' in path and field in ('base','addresses','stride_raw')
            if type(value) not in (int,bool,str) or not derived:continue
            doc=copy.deepcopy(base)
            changed=value+1 if type(value) is int else not value if type(value) is bool else value[:-1]
            assign(doc,path,changed);c=frozen(doc,cap)
            # Renew only the record binding; the independent raw observations remain fixed.
            c['legacy']['record_sha256']=v.digest(doc['legacy'])
            cli(v.canonical(doc).decode(),p,c,2,'r5/'+'.'.join(map(str,path)),log);total+=1;legacy_derived+=1
        doc=copy.deepcopy(base);doc['legacy']['records'][0]['end_tick']+=1
        c=frozen(doc,cap);c['legacy']['record_sha256']=v.digest(doc['legacy'])
        cli(v.canonical(doc).decode(),p,c,0,'r5/resealed-valid-observed-time',log)
    s.save(out/'gate-mutation-summary.json',dict(rejected=total,current_by_base=counts,seconds=round(time.monotonic()-start,2),
          legacy_derived=legacy_derived,valid_observed_variations_accepted=1,
          actual_public_cli_os_exit=True,max_test_processes=2,semantic_resealed=True))
    print('PASS mutations',total)

if __name__=='__main__':
    s.enable();run(sys.argv[1])
