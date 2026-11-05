"""Final independent replays after the sole fitting scheduler has settled."""
import argparse
import concurrent.futures
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

assert sys.flags.isolated
HERE = Path(__file__).resolve().parent
LOCAL = HERE/'local'
UNITS = ('a12-50', 'a12-28', 'mount-a12')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    parser.add_argument('--max-workers', type=int, default=6)
    args = parser.parse_args()
    assert 1 <= args.max_workers <= 6
    assert (LOCAL/'master_complete.json').exists(), 'Finish the single master queue first'
    if os.getpriority(os.PRIO_PROCESS, 0) < 15:
        os.nice(15-os.getpriority(os.PRIO_PROCESS, 0))
    assert os.getpriority(os.PRIO_PROCESS, 0) == 15
    root = LOCAL/'batches'/args.tag
    root.mkdir(exist_ok=False)
    # The sole fit scheduler has finished. Compile the already frozen pure-C
    # application routine once before dispatching any numerical replay worker.
    while True:
        line=subprocess.check_output(['/usr/bin/uptime'],text=True).strip()
        match=re.search(r'load averages?:\s*([\d.]+)',line);assert match,line
        if float(match[1])<=10:break
        print('WAIT host compile',line,flush=True);time.sleep(5)
    while True:
        with (root/'host-compile.log').open('a') as output:
            result=subprocess.run([sys.executable,'-I','-B',str(HERE/'host_build.py')],stdout=output,stderr=subprocess.STDOUT)
        if result.returncode==75:time.sleep(5);continue
        assert result.returncode==0,'Inspect host-compile.log'
        break
    waiting = [(film, unit) for film in range(20) for unit in UNITS]
    running, rows, failures = {}, [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        while waiting or running:
            for key, future in list(running.items()):
                if not future.done():
                    continue
                row = future.result()
                rows.append(row)
                del running[key]
                print('VERIFY FINISH', key, row['exit_code'], flush=True)
                if row['exit_code'] == 75:
                    waiting.append(key)
                elif row['exit_code']:
                    failures.append(key)
                (root/'receipt.json').write_text(json.dumps(dict(rows=rows, failures=failures), indent=2)+'\n')
            if failures:
                waiting.clear()
                if not running:
                    break
                time.sleep(2)
                continue
            line = subprocess.check_output(['/usr/bin/uptime'], text=True).strip()
            match = re.search(r'load averages?:\s*([\d.]+)', line)
            assert match, line
            load = float(match[1])
            limit = 0 if load > 10 else min(args.max_workers, 6 if load < 5 else 2)
            for unused in range(max(0, limit-len(running))):
                if not waiting:
                    break
                key = waiting.pop(0)
                film, unit = key
                result_path = LOCAL/'final_verification'/f'{film:02d}'/(unit+'.json')
                source_path = LOCAL/'analysis'/f'{film:02d}'/unit/'final.json'
                if result_path.exists():
                    import hashlib
                    result = json.loads(result_path.read_text())
                    same_binary=result.get('records',[{}])[0].get('runtime_C_flags',{}).get('dylib_sha256')==hashlib.sha256((LOCAL/'flags_host.dylib').read_bytes()).hexdigest()
                    if same_binary and result.get('runtime_C_flags_checked') and result['analysis_sha256'] == hashlib.sha256(source_path.read_bytes()).hexdigest():
                        continue
                log = root/(f'{film:02d}-{unit}-'+datetime.datetime.now().strftime('%H%M%S')+'.log')

                def one(key=key, log=log, line=line):
                    film, unit = key
                    command = [sys.executable, '-I', '-B', str(HERE/'verify_final.py'),
                               '--film', str(film), '--unit', unit]
                    started = time.monotonic()
                    with log.open('w') as output:
                        result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT)
                    return dict(film=film, unit=unit, command=command, log=str(log), uptime=line,
                                exit_code=result.returncode, seconds=time.monotonic()-started)

                running[key] = pool.submit(one)
            time.sleep(2)
    if failures:
        raise SystemExit('Independent verification failed: '+repr(failures))
    assert all((LOCAL/'final_verification'/f'{film:02d}'/(unit+'.json')).exists()
               for film in range(20) for unit in UNITS)
    subprocess.run([sys.executable,'-I','-B',str(HERE/'summarize.py'),'--require-complete'],check=True)
    while True:
        with (root/'locked-promotion.log').open('a') as output:
            result=subprocess.run([sys.executable,'-I','-B',str(HERE/'verify_locked.py')],stdout=output,stderr=subprocess.STDOUT)
        if result.returncode==75:
            time.sleep(5);continue
        assert result.returncode==0,'Inspect locked-promotion.log'
        break
    print('FINAL VERIFICATION COMPLETE: 60 profiles', flush=True)


if __name__ == '__main__':
    main()
