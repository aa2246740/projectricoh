"""Rebuild only the isolated candidate; record exact sources and Python ABI."""
import json,os,platform,subprocess,sys,sysconfig
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from support import enable,emit,sha

def main():
    enable()
    print(subprocess.check_output(['/bin/df','-h','/Volumes/Workspace'],text=True),end='')
    folder=ROOT/'tools/speedlab/harness_release_r4'
    original=json.loads((ROOT/'tools/speedlab/harness_c_next/local/ccore/build.json').read_text())
    output=folder/'local/ccore';output.mkdir(parents=True,exist_ok=True)
    library=output/Path(original['library']).name
    command=[part.replace(str(ROOT/'tools/speedlab/harness_c_next'),str(folder)) for part in original['command']]
    result=subprocess.run(command,capture_output=True,text=True,timeout=3600)
    (output/'build.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError(result.stderr)
    sources={str(p):sha(p) for p in sorted(set(folder.glob('*.py'))|set((folder/'ccore').glob('*.py'))|set((folder/'ccore').glob('*.c'))|set((folder/'ccore').glob('*.h')))}
    p=ROOT/'research/emulator_feasibility_r1/prototype/boot_probe.py';sources[str(p)]=sha(p)
    original.update(library=str(library),sha256=sha(library),sources=sources,command=command,python=sys.version,machine=platform.machine())
    emit(output/'build.json',original)
    print(json.dumps({'sha256':original['sha256'],'api':6}),flush=True)
if __name__=='__main__':main()
