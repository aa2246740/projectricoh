"""Record the actual host numerical environment, without running a benchmark."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import os
import platform
import runtime as rt
import scipy
import PIL

def main():
    rt.dump('environment.json',dict(python=sys.version,python_executable=sys.executable,
        numpy=rt.np.__version__,scipy=scipy.__version__,pillow=PIL.__version__,
        OS=platform.system(),OS_release=platform.release(),architecture=platform.machine(),
        byte_order=sys.byteorder,nice=os.getpriority(os.PRIO_PROCESS,0),
        thread_environment={k:os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS')},
        benchmark=False,camera_CPU_rate_measured=False))
    rt.finish('environment')

if __name__=='__main__':main()
