"""Sample the native core separately from the alternating speed measurements."""
import json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from safety import enable,HERE
enable();import bootstrap


def main():
    ctx=bootstrap.construct('fast','main','profile-whole-native-final9')
    c=ctx.machine.cpu;assert c.run(1000000).reason=='max_steps'
    output=HERE/'runs/profile-whole-native-final9.txt'
    child=subprocess.Popen(['/usr/bin/sample',str(os.getpid()),'2','1','-file',str(output)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    try:
        before=time.perf_counter();stop=c.run(200000000);seconds=time.perf_counter()-before
        log,_=child.communicate(timeout=15)
        (HERE/'runs/profile-whole-native-final9.log').write_text(log)
        record=dict(status='sampled' if child.returncode==0 else 'sample-failed',sample_exit_code=child.returncode,
            profiled=True,benchmark=False,seconds=seconds,stop=stop.to_dict(),load=os.getloadavg(),native=c._native_driver.stats())
        (HERE/'runs/profile-whole-native-final9.json').write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps(dict(status=record['status'],steps=c.steps,seconds=seconds)))
    finally:
        if child.poll() is None:child.kill();child.communicate(timeout=10)
        ctx.machine.close()


if __name__=='__main__':main()
