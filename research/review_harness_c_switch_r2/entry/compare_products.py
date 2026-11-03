"""Compare every saved artifact, with strict acceptance JSON and explicit runner metadata."""
import argparse,collections,copy,json,re,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from support import ROOT,enable,emit,sha
sys.path.insert(0,str(ROOT/'tools/speedlab'))
from compare import compare_values,read_json
REF=re.compile(r'(/r2-reference/)(reference|identity)-[0-9]+(\.dylib|\.json)')

def macho_sections(path):
    data=path.read_bytes()
    if len(data)<32 or struct.unpack_from('<I',data)[0]!=0xfeedfacf:raise ValueError('expected little-endian 64-bit Mach-O')
    count=struct.unpack_from('<I',data,16)[0];offset=32;sections={};identity=[]
    import hashlib
    for _ in range(count):
        command,size=struct.unpack_from('<II',data,offset)
        if size<8 or offset+size>len(data):raise ValueError('bad Mach-O command')
        if command==0x19:
            segment=struct.unpack_from('<II16sQQQQiiII',data,offset);n=segment[-2];at=offset+72
            for index in range(n):
                values=struct.unpack_from('<16s16sQQIIIIIIII',data,at+80*index)
                name=values[1].rstrip(b'\0').decode()+'/'+values[0].rstrip(b'\0').decode()
                length,fileoff,flags=values[3],values[4],values[8]
                blob=bytes(length) if flags&255 in (1,12,18) else data[fileoff:fileoff+length]
                if len(blob)!=length:raise ValueError('truncated section')
                sections[name]={'bytes':length,'sha256':hashlib.sha256(blob).hexdigest(),'address':values[2],'alignment':values[5],'flags':flags}
        if command==0xd:
            start=struct.unpack_from('<I',data,offset+8)[0]
            identity.append(data[offset+start:offset+size].split(b'\0',1)[0].decode())
        offset+=size
    return {'sections':sections,'install_names':identity,'whole_sha256':sha(path)}

def normalize_command(value):
    if isinstance(value,str):return REF.sub(r'\1\2-<process>\3',value)
    if isinstance(value,list):return [normalize_command(v) for v in value]
    if isinstance(value,dict):return {k:normalize_command(v) for k,v in value.items()}
    return value

def compare_group(name,candidate='c'):
    base=HERE/'local/measurements';folders={side:base/(candidate if side=='c' else side)/name for side in ('python','c')}
    metrics={side:json.loads((folder/'measurement.json').read_text()) for side,folder in folders.items()}
    products={side:folder/'products' for side,folder in folders.items()}
    inventory={side:{str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob('*')) if p.is_file()} for side,folder in products.items()}
    ordinary={side:{k:v for k,v in files.items() if '/r2-reference/' not in k} for side,files in inventory.items()}
    differences=[];json_proofs={};metadata={};raw_equal=0;values=0
    if ordinary['python'].keys()!=ordinary['c'].keys():differences.append({'reason':'artifact names','missing':sorted(ordinary['python'].keys()-ordinary['c'].keys()),'extra':sorted(ordinary['c'].keys()-ordinary['python'].keys())})
    for logical in sorted(ordinary['python'].keys()&ordinary['c'].keys()):
        left,right=(products[side]/logical for side in ('python','c'))
        same=inventory['python'][logical]==inventory['c'][logical]
        if same:raw_equal+=1
        if logical.endswith('.json'):
            a,b=read_json(left),read_json(right)
            if left.name.startswith('binding-'):
                da,db=a.pop('dependencies'),b.pop('dependencies')
                common=da.keys()&db.keys()
                extra_a=da.keys()-db.keys();extra_b=db.keys()-da.keys()
                allowed_a=all(k.startswith('tools/native_harness/') for k in extra_a)
                prefix='tools/speedlab/harness_release/' if candidate=='c-before' else 'tools/speedlab/harness_release_r4/'
                allowed_b=all(k.startswith(prefix) for k in extra_b)
                if candidate.startswith('c-strict'):
                    allowed_a=all(k.startswith('tools/native_harness/') or k=='tools/speedlab/host_regression_r4/run/backend_launch.py' for k in extra_a)
                    added={'tools/speedlab/host_regression_r4/run/input_trace_strict.py','tools/speedlab/host_regression_r4/run/backend_launch_strict.py'}
                    allowed_b=all(k.startswith(prefix) or k in added for k in extra_b)
                source_bytes=all((ROOT/k).is_file() and sha(ROOT/k)==v for deps in (da,db) for k,v in deps.items())
                identity_ok=all(da[k]==db[k] for k in common) and allowed_a and allowed_b and source_bytes
                metadata[logical]={'dependency_identity_checked':identity_ok,'python_only':{k:da[k] for k in sorted(extra_a)},'c_only':{k:db[k] for k in sorted(extra_b)}}
                if not identity_ok:differences.append({'file':logical,'reason':'dependency identity'})
            elif left.name.startswith('result-'):
                assert type(a['seconds']) in (int,float) and type(b['seconds']) in (int,float)
                metadata[logical]={'excluded_timing_fields':['/seconds'],'python_seconds':a.pop('seconds'),'c_seconds':b.pop('seconds')}
            proof=compare_values(a,b);values+=proof['compared_values'];json_proofs[logical]=proof
            if not proof['equal']:differences.append({'file':logical,'comparison':proof})
        elif logical.endswith('.jsonl'):
            a=[json.loads(x) for x in left.read_text().splitlines()];b=[json.loads(x) for x in right.read_text().splitlines()]
            proof=compare_values(normalize_command(a),normalize_command(b));metadata[logical]={'command_process_names_normalized':True,'comparison':proof}
            if not proof['equal']:differences.append({'file':logical,'comparison':proof})
        elif not same:differences.append({'file':logical,'reason':'raw bytes differ'})
    reference={}
    for side in ('python','c'):
        libraries=[];sources=[];other=[]
        for logical in sorted(inventory[side]):
            if '/r2-reference/' not in logical:continue
            file=products[side]/logical
            if re.search(r'/reference-[0-9]+\.dylib$',logical):
                libraries.append({'file':logical,**macho_sections(file)})
            elif re.search(r'/identity-[0-9]+\.json$',logical):sources.append({'file':logical,'sha256':sha(file),'value':read_json(file)})
            else:other.append(logical)
        reference[side]={'libraries':libraries,'sources':sources,'other':other}
    def section_counts(side):return collections.Counter(json.dumps(v['sections'],sort_keys=True) for v in reference[side]['libraries'])
    def source_counts(side):return collections.Counter(v['sha256'] for v in reference[side]['sources'])
    reference_sections_equal=section_counts('python')==section_counts('c')
    reference_whole_equal=collections.Counter(v['whole_sha256'] for v in reference['python']['libraries'])==collections.Counter(v['whole_sha256'] for v in reference['c']['libraries'])
    reference_ok=not reference['python']['other'] and not reference['c']['other'] and len(reference['python']['libraries'])==len(reference['c']['libraries']) and source_counts('python')==source_counts('c')
    if not reference_ok:differences.append({'reason':'reference source identity or multiplicity differs'})
    expected_api=5 if candidate=='c-before' else 6
    for process in metrics['c']['processes']:
        if process.get('native_api')!=expected_api:differences.append({'reason':'native API identity differs','actual':process.get('native_api'),'expected':expected_api})
    actual_work=metrics['python']['packets']==metrics['c']['packets'] and (metrics['python']['packets']>0 or name=='user-tool')
    if name!='user-tool' and metrics['c']['native_stats'].get('instructions',0)<=0:actual_work=False
    if not actual_work:differences.append({'reason':'executed packet count differs or empty'})
    for side in ('python','c'):
        if metrics[side]['result']['returncode'] or metrics[side]['result']['execution']!='FINISHED':differences.append({'reason':'failed execution','side':side})
    return {'job':name,'equal':not differences,'differences':differences,'json_files':len(json_proofs),'compared_values':values,'json_proofs':json_proofs,
            'raw_equal_ordinary_files':raw_equal,'ordinary_files':len(ordinary['python']),'all_artifacts':inventory,'runner_metadata':metadata,
            'reference_builds':reference,'reference_sources_equal':reference_ok,'reference_sections_equal':reference_sections_equal,'reference_whole_sha256_equal':reference_whole_equal,'raw_hashes_equal':inventory['python']==inventory['c'],'comparison_scope':'strict acceptance JSON, wrapper timing only excluded, binary products exact; per-process reference build hashes are reported individually without a byte-equality claim','packets':metrics['python']['packets'],
            'wall_seconds':{s:metrics[s]['wall_seconds'] for s in metrics},'cpu_seconds':{s:metrics[s]['cpu_seconds'] for s in metrics},
            'speedup_wall':metrics['python']['wall_seconds']/metrics['c']['wall_seconds'],'speedup_cpu':metrics['python']['cpu_seconds']/metrics['c']['cpu_seconds']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--job');args=p.parse_args();enable()
    jobs=[args.job] if args.job else [j['name'] for j in json.loads((HERE/'queue.json').read_text())['jobs']]
    results=[]
    for name in jobs:
        result=compare_group(name);emit(HERE/'local/comparisons'/(name+'.json'),result);results.append(result)
        print(json.dumps({k:result[k] for k in ('job','equal','json_files','compared_values','speedup_wall','speedup_cpu','differences')}),flush=True)
    summary={'passed':all(r['equal'] for r in results),'jobs':len(results),'compared_values':sum(r['compared_values'] for r in results),'json_files':sum(r['json_files'] for r in results),'raw_artifacts_all_hashed':True,'reference_binary_sha256_equality_claimed':False,'results':[ {k:r[k] for k in ('job','equal','packets','wall_seconds','cpu_seconds','speedup_wall','speedup_cpu')} for r in results]}
    emit(HERE/'local/comparisons/summary.json',summary)
    before=[]
    for name in jobs:
        if not (HERE/'local/measurements/c-before'/name/'measurement.json').is_file():continue
        result=compare_group(name,'c-before');emit(HERE/'local/comparisons-before'/(name+'.json'),result);before.append(result)
    if before:
        emit(HERE/'local/comparisons-before/summary.json',{'passed':all(r['equal'] for r in before),'jobs':len(before),'results':[{k:r[k] for k in ('job','equal','packets','wall_seconds','cpu_seconds','speedup_wall','speedup_cpu','differences')} for r in before]})
        summary['passed']=summary['passed'] and all(r['equal'] for r in before)
    return 0 if summary['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
