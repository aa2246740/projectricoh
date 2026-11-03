"""Finish the time-limited offline record, cleanup and SHA256 manifests."""
from pathlib import Path
import argparse,ast,hashlib,importlib.util,json,os,subprocess,time
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g152')
def run(name,*args):
    r=subprocess.run(['/usr/bin/python3','-I','-B',str(HERE/name),*args],cwd=ROOT,capture_output=True,text=True,check=True)
    print(name,r.stdout[-1400:],flush=True)
def main():
    if (HERE/'review_fix/start.json').is_file():
        import sys
        sys.path.insert(0,str(HERE))
        from review_fix_finish import main as review_main
        return review_main()
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');args=parser.parse_args()
    assert os.environ['TMPDIR']==str(TMP)
    run('final_scope.py')
    # Process census is a local read. It runs here because ps is unavailable
    # in the test sandbox; this script performs no network or device action.
    run('final_audit.py',*(['--partial'] if args.partial else []))
    run('report.py')
    summary=json.loads((HERE/'acceptance.json').read_text())
    package=json.loads((HERE/'package.json').read_text())
    resume=json.loads((HERE/'resume.json').read_text())
    resume.update(status='COMPLETE' if summary['verdict']=='可以交复审' else 'PARTIAL',completed_ns=time.time_ns())
    (HERE/'resume.json').write_text(json.dumps(resume,indent=2)+'\n')
    (HERE/'PROGRESS.md').write_text(summary['verdict']+'\n\n最终源码和两个候选包保留 10 个效果，DAT 没有再改。19 个快组与 48 项缩减锁忙矩阵的实际结果见 REPORT.md；完整 144 项按用户要求留给发布复审。\n\n发布 DAT：'+summary['dat_sha256']+'\n\n测试 DAT：'+summary['test_dat_sha256']+'\n\n已通过 '+str(summary['passing_jobs'])+'/'+str(summary['required_jobs'])+' 个计划作业。续轮最大并发 '+str(summary['resume_maximum_concurrent_tests'])+'；前轮 25.194 秒四进程事件仍保留。\n\nScratch 已清理，测试进程已结束。全部工作离线，g150 输入未改，未访问存储卡或刷机。\n')
    p=HERE/'final_audit.py';spec=importlib.util.spec_from_file_location('final_text',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    assignment=next(n for n in ast.walk(ast.parse(p.read_text())) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='words' for t in n.targets))
    pattern='|'.join(bytes.fromhex(x).decode() for x in ast.literal_eval(assignment.value));files=m.text_files()
    check=subprocess.run(['/usr/bin/grep','-lEi',pattern,*map(str,files)],capture_output=True,text=True)
    assert check.returncode==1,check.stdout
    (HERE/'evidence/final_text_scan.json').write_text(json.dumps(dict(status='PASS',files=len(files),matches=0,dat_sha256=summary['dat_sha256'],recorded_ns=time.time_ns()),indent=2)+'\n')
    planned={j['name']:j for j in json.loads((HERE/'queue-required.json').read_text())}
    names={j['script'][:-3] for j in planned.values()}|{'run_jobs'}
    census=subprocess.run(['/usr/bin/pgrep','-fl','Python.*research/looks_g152/('+'|'.join(sorted(names))+')\\.py'],capture_output=True,text=True)
    assert census.returncode==1,census.stdout
    assert not TMP.exists()
    (HERE/'evidence/process_census.json').write_text(json.dumps(dict(status='PASS',remaining=[],pgrep_returncode=1,TMP_absent=True,recorded_ns=time.time_ns()),indent=2)+'\n')
    run('seal.py')
    for cwd,manifest in ((ROOT,HERE/'SHA256SUMS'),(HERE/'local/earlier-candidate-159d',HERE/'local/earlier-candidate-159d/SHA256SUMS')):
        verified=subprocess.run(['/usr/bin/shasum','-a','256','-c',str(manifest)],cwd=cwd,capture_output=True,text=True,check=True)
        print('SHA256 verified',len(verified.stdout.splitlines()),str(manifest),flush=True)
    print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
