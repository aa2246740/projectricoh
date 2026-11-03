"""Finish the review correction in audit, report and seal order."""
from pathlib import Path
import argparse,ast,hashlib,importlib.util,json,os,subprocess,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g152')
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(name,*args):
    r=subprocess.run(['/usr/bin/python3','-I','-B',str(HERE/name),*args],cwd=ROOT,capture_output=True,text=True)
    print(name,r.stdout[-1700:],r.stderr[-1700:],flush=True);r.check_returncode()
def scope():
    package=read(HERE/'package.json');test=package['test']['dat_sha256'];archive=HERE/'local/review-fix-prior'
    old_jobs=read(archive/'research/looks_g152/queue-required.json');new_jobs=read(HERE/'queue-fix-required.json')
    lines=['# 本轮复审修复的复跑范围','','本表逐项对照上一候选 58 个作业。只有新 DAT 的回执算本轮执行；原回执和旧 DAT 均已封存。','','| 上轮作业 | 本轮处理与理由 |','|---|---|']
    for old in old_jobs:
        matches=[j['name'] for j in new_jobs if j['script']==old['script'] and j.get('args',[])==old.get('args',[])]
        if matches:reason='以最终 DAT 重新执行：'+', '.join(matches)+'。'
        elif old['script']=='regressions.py':reason='本轮选择受影响的启动、首次应用、锁忙和双包记录组；逐用例和单元列在 REGRESSION_SCOPE.md，未选部分留给发布复审。'
        elif old['script']=='lock_checks.py':reason='以新 DAT 的 fix-matrix 两单元 48 项替代；原独立 sample 是同一 late/OK 路径的重复子集，没有另计通过。'
        elif old['script']=='ui_checks.py':reason='未重跑该组。两套文本数组、窗口、标签和滚动源码未改；本轮重跑错误/失归属，以及三单元十效果的原生 8 行和实际长名。完整列表组合仍留给发布复审。'
        elif old['script']=='knob_checks.py':reason='未重跑正常微调组。数学和已提交配方的控制值组合未改；本轮重新执行完整整数合同、30 次效果应用、W 前拒绝及 48 项已提交切换。完整微调回归留给发布复审。'
        elif old['script']=='identity_checks.py':reason='独立身份组未重跑。引用构造和内容 CRC 未改；本轮 48 项切换核对 56 B 引用不变，30 次应用核对最终完整条目。原复审已独立通过该组。'
        elif old['script']=='emu_boot.py':reason='未重跑。官方 MAIN 和全部机身文件逐字节相同；两次原模拟器冷启动不执行 DAT，保留原机身身份与零介质写回执。'
        else:raise AssertionError(old)
        lines.append('| '+old['name']+' | '+reason+' |')
    lines+=['','新增原复审 04/08 两次事务、效果/拍摄恢复/四次拒绝后成功、单元行与 T 不稳定组。原生相机路径全部使用 Python 指令后端；主机 C 仅用于算法与格式比较。','','完整 144 项锁忙、其余 99 条旧用例与 81 个全量组、实机 LCD/RPC/RTOS/ISO100/ready=0 和独立画质标定留给发布复审。']
    (HERE/'REVIEW_FIX_SCOPE.md').write_text('\n'.join(lines)+'\n')
    original=(archive/'research/looks_g152/CORE_REGRESSION_SCOPE.md').read_text()
    original=original.replace('另选19次旧用例','另选10次旧用例执行（含 service-six-matrix）')
    original=original.replace('四种切换×六时序×三退出及五种锁 count/ID','四种切换×三时序×两退出，完整 144 项仍留给发布复审')
    original=original.replace('新矩阵覆盖 OK/半按/MENU 与重开','缩减矩阵覆盖 OK/半按与重开；未建基线的专项另含 MENU 退出')
    original=original.replace('本轮另跑四种切换','本轮在 50mm/MOUNT 另跑四种切换')
    original=original.replace('缩减矩阵覆盖 OK/半按','50mm/MOUNT 缩减矩阵覆盖 OK/半按')
    (HERE/'CORE_REGRESSION_SCOPE.md').write_text(original)
    runs=['# 本轮最终 DAT 的执行记录','','旧 DAT 反例是独立的观察作业，不计入下表最终候选通过数。每行日志及 JSON 保存完整命令、DAT、脚本摘要和产物时间。','','| 作业 | 状态 | 秒 | 回执 |','|---|---|---:|---|']
    for job in new_jobs:
        p=HERE/'evidence/jobs'/(job['name']+'.json');r=read(p) if p.is_file() else {}
        runs.append('| '+job['name']+' | '+r.get('status','PENDING')+' | '+str(round(r.get('seconds',0),3))+' | [JSON](../evidence/jobs/'+job['name']+'.json) |')
    (HERE/'review_fix/RUNS.md').write_text('\n'.join(runs)+'\n')
def file_list():
    archive=HERE/'local/review-fix-prior';rows=[]
    for base in (HERE,ROOT/'firmware/engine_v60_g152',ROOT/'firmware/package_v38_g152',ROOT/'firmware/package_v38_g152_test'):
        for directory,dirs,names in os.walk(base,followlinks=False):
            dirs[:]=[d for d in dirs if d not in ('local','SD_ROOT','__pycache__','evidence','legacy')]
            for name in names:
                p=Path(directory)/name
                if p.is_symlink() or name in ('SHA256SUMS','REVIEW_FIX_FILES.md'):continue
                old=archive/p.relative_to(ROOT)
                if old.is_file() and sha(old)==sha(p):continue
                rows.append((str(p.relative_to(ROOT)),'新增' if not old.is_file() else '修改',sha(p)))
    text=['# 精确改动文件清单','','引擎移植仅涉及以下唯一文件，完整差异见 review_fix/engine-change.diff：','','`firmware/engine_v60_g152/candidate/containers/product/src/firmware/engine/core/eng_core.c`','','以下包含测试、构建、队列、报告和包清单。运行回执、日志及最终 DAT/ELF 由 SHA256SUMS 逐项列出，本表不展开这些生成物。','','| 路径 | 类型 | SHA256 |','|---|---|---|']
    text.extend('| `'+p+'` | '+kind+' | `'+value+'` |' for p,kind,value in sorted(rows))
    (HERE/'REVIEW_FIX_FILES.md').write_text('\n'.join(text)+'\n')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');args=parser.parse_args()
    assert os.environ['TMPDIR']==str(TMP)
    run('final_scope.py');scope()
    run('final_audit.py',*(['--partial'] if args.partial else []))
    run('report.py')
    acceptance=read(HERE/'acceptance.json');verdict=acceptance['verdict']
    state=read(HERE/'review_fix/start.json');state.update(status='COMPLETE' if verdict=='可以交复审' else 'PARTIAL',completed_ns=time.time_ns(),release_sha256=acceptance['dat_sha256'],test_sha256=acceptance['test_dat_sha256'])
    (HERE/'review_fix/start.json').write_text(json.dumps(state,indent=2)+'\n')
    (HERE/'PROGRESS.md').write_text(verdict+'\n\n复审修复只改一个引擎文件 eng_core.c；区 CRC 正式夹具已隔离。最终 DAT 完成 '+str(acceptance['passing_jobs'])+'/'+str(acceptance['required_jobs'])+' 作业和 '+str(acceptance['lock_cases'])+'/48 缩减锁忙项。\n\n发布 DAT：'+acceptance['dat_sha256']+'\n\n测试 DAT：'+acceptance['test_dat_sha256']+'\n\n本轮最大并发 '+str(acceptance['maximum_concurrent_tests'])+'，测试进程全部退出、Scratch 已清理。旧失败与前轮调度事件保留；完整 144 项留给发布复审。\n')
    file_list()
    spec=importlib.util.spec_from_file_location('g152_final_text',HERE/'final_audit.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    tree=ast.parse((HERE/'final_audit.py').read_text())
    assignment=next(n for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='words' for t in n.targets))
    pattern='|'.join(bytes.fromhex(x).decode() for x in ast.literal_eval(assignment.value));files=module.text_files()
    scan=subprocess.run(['/usr/bin/grep','-lEi',pattern,*map(str,files)],capture_output=True,text=True)
    assert scan.returncode==1,scan.stdout
    (HERE/'evidence/final_text_scan.json').write_text(json.dumps(dict(status='PASS',files=len(files),matches=0,dat_sha256=acceptance['dat_sha256'],recorded_ns=time.time_ns()),indent=2)+'\n')
    sys.path.insert(0,str(HERE));from controller_guard import workers
    active=workers({j['script'] for j in read(HERE/'queue-fix-required.json')}|{'run_jobs.py'});assert not active and not TMP.exists()
    (HERE/'evidence/process_census.json').write_text(json.dumps(dict(status='PASS',remaining=[],TMP_absent=True,recorded_ns=time.time_ns()),indent=2)+'\n')
    run('seal.py')
    for path,base in ((HERE/'SHA256SUMS',ROOT),(HERE/'local/review-fix-prior/SHA256SUMS',HERE/'local/review-fix-prior'),(HERE/'local/earlier-candidate-159d/SHA256SUMS',HERE/'local/earlier-candidate-159d')):
        p=subprocess.run(['/usr/bin/shasum','-a','256','-c',str(path)],cwd=base,capture_output=True,text=True);p.check_returncode();print('Verified SHA256 files',len(p.stdout.splitlines()),str(path),flush=True)
    print(json.dumps(acceptance,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
