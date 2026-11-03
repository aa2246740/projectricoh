"""Review complete RPC streams separately from failure-event summaries."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json

UNITS = ('50mm', '28mm', 'mount')
FIELDS = ('cmd', 'value', 'page', 'result', 't')

def sha(data):return hashlib.sha256(data).hexdigest()
def file_sha(path):return sha(Path(path).read_bytes())

def maps(raw, index):
    u16 = lambda b,o: int.from_bytes(b[o:o+2], 'big')
    u32 = lambda b,o: int.from_bytes(b[o:o+4], 'big')
    directory = u32(raw,156) + 64*index
    assert directory+64 <= len(raw), ('DAT directory',index)
    start=u32(raw,directory+12)
    assert start+152 <= len(raw), ('DAT mapping',index)
    data = raw[start:start+152]
    rows=[(u32(data,32+12*j),u16(data,36+12*j)) for j in range(9)]
    assert all(size>0 and address+size<=2**32 for address,size in rows), ('DAT row',index)
    return rows,(u16(data,28),u16(data,30))

def record_type(value, location):
    if not value or not isinstance(value,list):
        return None
    commands = all(isinstance(x,dict) and 'cmd' in x and 'value' in x for x in value)
    if not commands:
        assert not location.endswith('/rpc_log'), ('malformed rpc_log',location)
        return None
    if all(all(k in x for k in FIELDS) for x in value):
        return 'rpc_log'
    if all(all(k in x for k in ('page_before','page_after','address','result')) for x in value):
        return 'address_trace'
    assert not location.endswith('/rpc_log'), ('incomplete rpc_log',location)
    assert location.endswith('/events') and all('at' in x for x in value), ('unknown command record',location)
    return 'failure_events'

def check_log(log, mapping):
    rows,t = mapping
    pages = {a>>16 for a,s in rows} | {(a+s-1)>>16 for a,s in rows} | {t[0]}
    page,cursor,selected = None,None,None
    reads = {}
    counts = Counter(X=0,V=0,W=0,preserved_edges=0,prefix_writes=0,no_device_effect=0)
    for index,call in enumerate(log):
        assert all(k in call for k in FIELDS), ('full RPC fields',index)
        cmd,value = call['cmd'],call['value']
        assert cmd in (21,22,23) and isinstance(value,int) and 0 <= value <= 65535
        counts[{21:'V',22:'W',23:'X'}[cmd]] += 1
        result = call.get('device_result',call['result'])
        effect = isinstance(result,int) and 0 <= result <= 65535
        counts['no_device_effect'] += not effect
        actual_page = call['page']
        if cmd == 23:
            assert value in pages, ('page',index,call)
            selected = value
            if effect:
                assert actual_page == value, ('selected page',index,call)
            elif page is not None:
                assert actual_page == page, ('failed page change',index,call)
            page = actual_page
            continue
        if page is not None:
            assert actual_page == page, ('unrecorded page change',index,call)
        page = actual_page
        if page is None:
            assert not effect and selected in pages and cmd == 21, ('current page',index,call)
            continue
        assert page in pages, ('current page',index,call)
        if page == t[0]:
            if cmd == 21:
                assert value == t[1], ('T index',index,call)
                if effect:
                    assert result == call['t'], ('T read value',index,call)
                    cursor = None
            elif effect:
                assert call['t'] == value, ('T write value',index,call)
                cursor = None
            continue
        address = (page<<16)|(value&65534) if cmd == 21 else cursor
        assert address is not None, ('write without preceding read',index,call)
        matches = [(a,s) for a,s in rows if (a&~1) <= address and address+2 <= ((a+s+1)&~1)]
        assert matches, ('row range',hex(address),index,call)
        base,size = matches[0]
        if cmd == 21:
            if effect:
                reads[address] = result
                cursor = address
        else:
            high,low = address < base,address+2 > base+size
            if high or low:
                assert address in reads, ('neighbor evidence',hex(address),index)
                previous = reads[address]
                assert not high or value>>8 == previous>>8, ('leading neighbor',index,call)
                assert not low or value&255 == previous&255, ('trailing neighbor',index,call)
                counts['preserved_edges'] += 1
            if effect:
                reads[address] = value
                cursor = address+2
    return dict(counts)

def sentinel_logs(path,mapping,pin):
    path=Path(path)
    document = json.loads(path.read_text())
    unit=document['unit']
    assert document['dat_sha256'] == pin
    rows,t = mapping
    proofs = []
    for step in document['steps']:
        if step['operation'] not in ('reopen_recipe','reopen_same_recipe'):
            continue
        calls = step['rpc_log']
        assert len(calls)==step['RPC']==20 and step['W']==0
        contained = []; t_reads = 0
        for at in range(0,20,2):
            x,v = calls[at:at+2]
            assert x['cmd']==23 and v['cmd']==21
            assert x['page']==x['value']==v['page']
            assert 0 <= x['result'] <= 65535 and 0 <= v['result'] <= 65535
            if v['page']==t[0]:
                assert v['value']==t[1];t_reads += 1
            else:
                address=(v['page']<<16)|(v['value']&65534)
                found=[j for j,(base,size) in enumerate(rows) if base<=address and address+2<=base+size]
                assert len(found)==1, ('sentinel logical row',unit,hex(address))
                contained.append(dict(row=found[0],address=hex(address),bytes=2))
        assert t_reads==1 and sorted(r['row'] for r in contained)==list(range(9))
        proofs.append(dict(operation=step['operation'],T_reads=t_reads,contained_reads=contained))
    assert len(proofs)==2
    return dict(file=str(path),source_sha256=file_sha(path),steps=proofs)

def main(dat,records,output,sentinel_records=(),base=None):
    dat=Path(dat).resolve();output=Path(output).resolve()
    base=Path(base or Path.cwd()).resolve()
    def label(path):
        try:return str(path.relative_to(base))
        except ValueError:return str(path)
    raw = dat.read_bytes();pin = sha(raw)
    assert len(raw)>=256, 'DAT header'
    mappings = {u:maps(raw,i) for i,u in enumerate(UNITS)}
    paths=set()
    for source in records:
        source=Path(source).resolve()
        assert source.exists(), ('record path',str(source))
        paths.update(source.rglob('*.json') if source.is_dir() else [source])
    paths=sorted(paths)
    failures,records,summaries,excluded = [],[],[],[]
    totals = {u:Counter(source_files=0,logs=0,native_origin_records=0,file_counter_records=0,runtime_range_records=0) for u in UNITS}
    seen = set()
    def walk(value,unit,path,location):
        if isinstance(value,dict):
            if value.get('unit') in UNITS:unit=value['unit']
            counters=('create','write','rename','delete','write_open')
            if all(k in value for k in counters):
                assert all(value[k]==0 for k in counters), ('file counter',location)
                if unit in totals:totals[unit]['file_counter_records']+=1
            if 'host_writes' in value and 'getter_callback_present' in value:
                assert value['host_writes']==0 and not value['getter_callback_present'], ('native origin',location)
                if unit in totals:totals[unit]['native_origin_records']+=1
            if all(k in value for k in ('X','V','W','violations')):
                assert value['violations']==0, ('runtime range',location)
                if unit in totals:totals[unit]['runtime_range_records']+=1
            for key,child in value.items():walk(child,unit,path,location+'/'+key)
        elif isinstance(value,list):
            kind=record_type(value,location)
            if kind=='failure_events':
                summaries.append(dict(file=label(path),location=location,unit=unit,events=len(value)))
            elif kind in ('rpc_log','address_trace'):
                assert unit in UNITS, ('unit for log',location)
                digest=sha(json.dumps(value,sort_keys=True).encode());identity=unit+':'+digest
                if identity not in seen:
                    seen.add(identity)
                    stream=value
                    if kind=='address_trace':
                        stream=[]
                        for call in value:
                            result=call['result']
                            if call.get('simulated') and result<0:
                                assert call['cmd']==22, ('trace device result',location)
                                result=call['value']
                            stream.append(dict(cmd=call['cmd'],value=call['value'],page=call['page_after'],
                                result=result,t=result if call['cmd']==21 else call['value']))
                    counts=check_log(stream,mappings[unit]);totals[unit].update(counts);totals[unit]['logs']+=1
                    records.append(dict(file=label(path),source_sha256=file_sha(path),location=location,
                                        unit=unit,record_type=kind,log_sha256=digest,**counts))
            else:
                for i,child in enumerate(value):walk(child,unit,path,location+'/'+str(i))
    for path in paths:
        if not path.exists():continue
        document=json.loads(path.read_text())
        unit=document.get('unit') if isinstance(document,dict) else None
        unit=unit if unit in UNITS else next((u for u in UNITS if u in path.name),None)
        if isinstance(document,dict):
            old=document.get('dat_sha256',document.get('dat'))
            if isinstance(old,str) and len(old)==64 and old!=pin:
                excluded.append(dict(file=label(path),dat_sha256=old));continue
        if unit in totals:totals[unit]['source_files']+=1
        try:walk(document,unit,path,'')
        except (AssertionError,KeyError,ValueError,TypeError) as error:
            failures.append(dict(file=label(path),unit=unit,error=repr(error)))
    sentinels={}
    for path in sentinel_records:
        path=Path(path).resolve();unit=None
        try:
            unit=json.loads(path.read_text())['unit']
            assert unit in mappings, ('sentinel unit',unit)
            sentinels[unit]=sentinel_logs(path,mappings[unit],pin)
        except (AssertionError,KeyError,ValueError,TypeError) as error:
            failures.append(dict(file=label(path),unit=unit,error=repr(error)))
    states={u:('FAIL' if any(f['unit'] in (u,None) for f in failures) else 'PASS') for u in UNITS}
    for unit in UNITS:
        if not totals[unit]['source_files'] and not totals[unit]['logs']:states[unit]='INCOMPLETE'
    value=dict(status='PASS' if all(s=='PASS' for s in states.values()) else 'FAIL',dat_sha256=pin,dat_file=str(dat),
        generation=int.from_bytes(raw[28:32],'big'),auditor_sha256=file_sha(Path(__file__)),
        units=states,files=len(paths),unit_totals={u:dict(c) for u,c in totals.items()},failures=failures,
        failure_event_summaries=summaries,excluded_other_dat=excluded,communication_logs=records,
        sentinel_proofs=sentinels,
        unit_order=list(UNITS),format='GXRCE DAT with three 64-byte unit directories and nine GXMP rows per mapping.',
        coverage={u:dict(complete_streams=totals[u]['logs'],runtime_range_records=totals[u]['runtime_range_records'],
            raw_streams_present=bool(totals[u]['logs'])) for u in UNITS},
        count_scope='Identical complete streams counted once per unit; overlapping prefixes remain. Failure-event summaries are not communication streams.',
        aligned_words='Complete row access may include one adjacent byte at either halfword edge; every attempted edge W preserves the last read value. Sentinel halfwords are entirely within logical rows.')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(value['status'],'RPC review',states,'logs',len(records),'event summaries',len(summaries),'failures',failures[:4],flush=True)
    assert value['status']=='PASS',failures[:4]

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dat',required=True,type=Path)
    parser.add_argument('--records',required=True,nargs='+',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--sentinel-records',nargs='*',default=[],type=Path,
        help='Optional gen 122 twenty-call sentinel samples; omit for generations without that path.')
    parser.add_argument('--base-dir',type=Path,default=Path.cwd())
    args=parser.parse_args()
    main(args.dat,args.records,args.output,args.sentinel_records,args.base_dir)
