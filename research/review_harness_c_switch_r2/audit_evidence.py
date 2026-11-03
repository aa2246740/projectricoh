"""Read complete products independently and compare typed acceptance values."""
from pathlib import Path
import argparse,collections,hashlib,json,re,struct,time

ROOT=Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh')
OUT=Path(__file__).resolve().parent
SOURCE=ROOT/'tools/speedlab/host_regression_r4'
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-cswitch-r2')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def pairs(items):
    result={}
    for key,value in items:
        if key in result:raise ValueError('duplicate JSON key '+key)
        result[key]=value
    return result
def read(path):
    def invalid(value):raise ValueError('nonfinite JSON value '+value)
    return json.loads(path.read_text(),object_pairs_hook=pairs,parse_constant=invalid)
def compare(a,b,path=''):
    if type(a) is not type(b):return 0,[{'path':path,'reason':'type'}]
    if isinstance(a,dict):
        count=0;diff=[]
        if a.keys()!=b.keys():diff.append({'path':path,'reason':'keys','left_only':sorted(a.keys()-b.keys()),'right_only':sorted(b.keys()-a.keys())})
        for key in sorted(a.keys()&b.keys()):
            n,d=compare(a[key],b[key],path+'/'+str(key));count+=n;diff.extend(d)
        return count,diff
    if isinstance(a,list):
        count=0;diff=[]
        if len(a)!=len(b):diff.append({'path':path,'reason':'length'})
        for index,(x,y) in enumerate(zip(a,b)):
            n,d=compare(x,y,path+'/'+str(index));count+=n;diff.extend(d)
        return count,diff
    return 1,([] if a==b else [{'path':path,'reason':'value','left':a,'right':b}])

def metadata_normalize(value,paths=()):
    if isinstance(value,str):
        for name,replacement in sorted(paths,key=lambda v:len(v[0]),reverse=True):value=value.replace(name,replacement)
        return re.sub(r'(/r2-reference/)(reference|identity)-[0-9]+(\.(?:dylib|json))',r'\1\2-<process>\3',value)
    if isinstance(value,list):return [metadata_normalize(v,paths) for v in value]
    if isinstance(value,dict):return {k:metadata_normalize(v,paths) for k,v in value.items()}
    return value

def sections(path):
    data=path.read_bytes()
    if len(data)<32 or struct.unpack_from('<I',data)[0]!=0xfeedfacf:raise ValueError('expected Mach-O 64')
    at=32;count=struct.unpack_from('<I',data,16)[0];result={}
    for _ in range(count):
        command,size=struct.unpack_from('<II',data,at)
        if size<8 or at+size>len(data):raise ValueError('bad Mach-O command')
        if command==0x19:
            n=struct.unpack_from('<I',data,at+64)[0]
            for i in range(n):
                x=struct.unpack_from('<16s16sQQIIIIIIII',data,at+72+80*i)
                name=x[1].rstrip(b'\0').decode()+'/'+x[0].rstrip(b'\0').decode()
                blob=bytes(x[3]) if x[8]&255 in (1,12,18) else data[x[4]:x[4]+x[3]]
                if len(blob)!=x[3]:raise ValueError('truncated section')
                result[name]={'size':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'address':x[2],'alignment':x[5],'flags':x[8]}
        at+=size
    return result

def compare_trees(left,right,mode,run_paths=None):
    folders={'python':left,'c':right}
    files={s:{str(p.relative_to(f)):sha(p) for p in sorted(f.rglob('*')) if p.is_file()} for s,f in folders.items()}
    ordinary={s:{k:v for k,v in rows.items() if '/r2-reference/' not in k} for s,rows in files.items()}
    diff=[];metadata=[];count=0;njson=0
    if ordinary['python'].keys()!=ordinary['c'].keys():diff.append({'reason':'file names','python_only':sorted(ordinary['python'].keys()-ordinary['c'].keys()),'c_only':sorted(ordinary['c'].keys()-ordinary['python'].keys())})
    replacements={s:[] for s in folders}
    if run_paths:
        for s in folders:
            run=run_paths[s]
            replacements[s]=[(str(run),'<run>'),(str(run.relative_to(ROOT)),'<run>'),(str(TMP/('real-'+s)),'<temporary>'),(str(TMP/('labels-'+('py-ref' if s=='python' else 'cc-ref'))),'<temporary>')]
    for name in sorted(ordinary['python'].keys()&ordinary['c'].keys()):
        paths={s:folders[s]/name for s in folders}
        if name.endswith('.json'):
            values={s:read(p) for s,p in paths.items()}
            if paths['python'].name.startswith('binding-'):
                deps={s:v.pop('dependencies') for s,v in values.items()}
                shared=deps['python'].keys()&deps['c'].keys()
                valid=all(deps['python'][k]==deps['c'][k] for k in shared)
                valid=valid and all((ROOT/k).is_file() and sha(ROOT/k)==v for d in deps.values() for k,v in d.items())
                adapters={}
                for s in folders:
                    other='c' if s=='python' else 'python'
                    for key in sorted(deps[s].keys()-shared):
                        p=ROOT/key
                        backend_prefix='tools/native_harness/' if s=='python' else 'tools/speedlab/harness_release/' if mode=='before' else 'tools/speedlab/harness_release_r4/'
                        if run_paths and p.is_relative_to(run_paths[s]/'run'):
                            q=run_paths[other]/p.relative_to(run_paths[s])
                            a=metadata_normalize(p.read_text(),replacements[s]);b=metadata_normalize(q.read_text(),replacements[other]) if q.is_file() else None
                            adapters[str(p.relative_to(run_paths[s]))]=a==b;valid=valid and a==b
                        elif key.startswith(backend_prefix):
                            pass
                        elif mode in ('stored','before') and key in (
                            'tools/speedlab/host_regression_r4/run/backend_launch.py',
                            'tools/speedlab/host_regression_r4/run/backend_launch_strict.py',
                            'tools/speedlab/host_regression_r4/run/input_trace_strict.py'):
                            pass
                        else:valid=False
                metadata.append({'file':name,'dependency_identity_checked':valid,'adapters_equal_after_directory_relocation':adapters,'dependencies':deps})
                if not valid:diff.append({'file':name,'reason':'dependency identity'})
            if paths['python'].name.startswith('result-'):
                excluded={s:v.pop('seconds') for s,v in values.items()}
                metadata.append({'file':name,'excluded_wrapper_root_seconds':excluded})
            n,d=compare(values['python'],values['c']);count+=n;njson+=1
            if d:diff.append({'file':name,'differences':d})
        elif name.endswith('.jsonl'):
            values={s:metadata_normalize([json.loads(line,object_pairs_hook=pairs) for line in p.read_text().splitlines()],replacements[s]) for s,p in paths.items()}
            _,d=compare(values['python'],values['c'])
            metadata.append({'file':name,'command_paths_and_process_filenames_normalized':True})
            if d:diff.append({'file':name,'differences':d})
        elif ordinary['python'][name]!=ordinary['c'][name]:
            if '/decode/' in name and name.endswith('.txt') and run_paths:
                equal=metadata_normalize(paths['python'].read_text(),replacements['python'])==metadata_normalize(paths['c'].read_text(),replacements['c'])
                metadata.append({'file':name,'listing_filename_normalized':True,'equal':equal})
                if not equal:diff.append({'file':name,'reason':'decode listing'})
            else:diff.append({'file':name,'reason':'bytes'})
    references={};section_counters={}
    for s in folders:
        refs=[];identities=[];unknown=[]
        for name in files[s]:
            if '/r2-reference/' not in name:continue
            p=folders[s]/name
            if re.search(r'/reference-[0-9]+\.dylib$',name):refs.append({'file':name,'sha256':files[s][name],'sections':sections(p)})
            elif re.search(r'/identity-[0-9]+\.json$',name):identities.append(files[s][name])
            else:unknown.append(name)
        references[s]={'libraries':refs,'identity_sha256':sorted(identities),'unknown':unknown}
        # Keep unwind tables and addresses in evidence; compare executable code and constant bytes separately.
        relevant=[]
        for ref in refs:
            data={k:{x:y for x,y in v.items() if x!='address'} for k,v in ref['sections'].items() if k.startswith('__TEXT/') and k not in ('__TEXT/__eh_frame','__TEXT/__unwind_info')}
            relevant.append(json.dumps(data,sort_keys=True))
        section_counters[s]=collections.Counter(relevant)
    if references['python']['identity_sha256']!=references['c']['identity_sha256'] or len(references['python']['libraries'])!=len(references['c']['libraries']) or any(v['unknown'] for v in references.values()):diff.append({'reason':'reference inputs or quantity'})
    section_equal=section_counters['python']==section_counters['c']
    if not section_equal:diff.append({'reason':'reference executable or constant sections'})
    return {'equal':not diff,'differences':diff,'json_files':njson,'compared_values':count,'all_file_sha256':files,'metadata':metadata,'references':references,'reference_code_and_constants_equal':section_equal}

def observations():
    rows=[]
    for label,relative in [('busy','tests/local/busy-settings-exit/checks/50mm-busy-settings-exit.json'),('observation','tests/local/unverified-late-mount/checks/mount-unverified-late.json')]:
        folder=OUT/label;values={};timings={};metrics={};raw={}
        for s in ('python','c'):
            p=folder/s/relative;raw[s]=sha(p);value=read(p)
            timings[s]={k:value.pop(k) for k in ('seconds','started_ns','ended_ns')}
            values[s]=value
            metrics[s]=[read(p) for p in sorted((folder/s/'metrics').glob('process-*.json'))]
        n,d=compare(values['python'],values['c'])
        row={'case':label,'equal':not d,'differences':d,'compared_values':n,'statuses':{s:v['status'] for s,v in values.items()},'timing_exclusions':timings,'raw_sha256':raw,
             'packets':{s:sum(p['packets'] for p in records) for s,records in metrics.items()},'processes':metrics}
        (folder/'comparison.json').write_text(json.dumps(row,indent=2)+'\n');rows.append(row)
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('kind',choices=('observations','stored','real','labels','before'));args=p.parse_args()
    target=OUT/'comparisons'/args.kind;target.mkdir(parents=True,exist_ok=True)
    if args.kind=='observations':
        rows=observations()
        summary={'passed':all(r['equal'] and set(r['statuses'].values())=={'OBSERVED_P1'} and len(set(r['packets'].values()))==1 for r in rows),'rows':rows}
    else:
        rows=[]
        records=read(OUT/'real/complete.json') if args.kind=='real' else read(OUT/'real-labels-equal/complete.json') if args.kind=='labels' else None
        jobs=[j['name'] for j in read(SOURCE/'queue.json')['jobs']] if records is None else list(dict.fromkeys(r['job'] for r in records))
        if args.kind=='before':jobs=['group124+126-50mm-safety','group126-50mm-view-reentry','group126-28mm-exits','group126-28mm-users','group126-mount-cutpoints']
        for job in jobs:
            if records is None:
                folders={'python':SOURCE/'local/measurements/python'/job,'c':SOURCE/'local/measurements'/('c-before' if args.kind=='before' else 'c-strict-release')/job}
                metric={s:read(f/'measurement.json') for s,f in folders.items()}
                row=compare_trees(folders['python']/'products',folders['c']/'products','before' if args.kind=='before' else 'stored')
            else:
                metric={s:next(r for r in records if r['job']==job and r['side']==s) for s in ('python','c')}
                runs={s:Path(r['run']) for s,r in metric.items()}
                row=compare_trees(runs['python']/'run/local/jobs'/job,runs['c']/'run/local/jobs'/job,'real',runs)
            row['job']=job;row['timing']={s:{k:v[k] for k in ('wall_seconds','cpu_seconds')} for s,v in metric.items()}
            row['packets']={s:sum(p['packets'] for p in v['processes']) for s,v in metric.items()}
            row['native_stats']={k:sum(p['native_stats'].get(k,0) for p in metric['c']['processes']) for k in ('instructions','fallback_calls','fallback_steps','fast_writes')}
            work_ok=len(set(row['packets'].values()))==1 and (job=='user-tool' or row['packets']['python']>0 and row['native_stats']['instructions']>0)
            if not work_ok:row['differences'].append({'reason':'execution counts'})
            for s,v in metric.items():
                receipt=v.get('result',v.get('receipt'))
                if receipt['returncode']!=0 or receipt['execution']!='FINISHED':row['differences'].append({'reason':'execution status','side':s})
                if any(p.get('nice',0)<15 for p in v['processes']):row['differences'].append({'reason':'worker priority','side':s})
            row['equal']=not row['differences'];rows.append(row)
            (target/(job+'.json')).write_text(json.dumps(row,indent=2)+'\n')
            print(json.dumps({k:row[k] for k in ('job','equal','json_files','compared_values','packets','differences')}),flush=True)
        measured=[r for r in rows if r['job']!='user-tool']
        totals={key:{s:sum(r['timing'][s][key] for r in measured) for s in ('python','c')} for key in ('wall_seconds','cpu_seconds')}
        summary={'passed':all(r['equal'] for r in rows),'groups':len(measured),'including_prerequisite_groups':len(rows),'json_files':sum(r['json_files'] for r in rows),'compared_values':sum(r['compared_values'] for r in rows),'packets_each_side':sum(r['packets']['python'] for r in measured),'timing':totals,'ratios':{k:v['python']/v['c'] for k,v in totals.items()},'results':[{k:r[k] for k in ('job','equal','json_files','compared_values','packets','timing','native_stats')} for r in rows]}
    (target/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('rows','results')}),flush=True)
    return 0 if summary['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
