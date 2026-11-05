"""Only replace the test's browser launcher. Preserve its page, inputs and pixel assertions."""
from pathlib import Path
import json
import os
import subprocess
import sys

HERE = Path(__file__).resolve().parent
STUDIO = Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/g156-codec')


def pytest_configure(config):
    sys.path.insert(0,str(STUDIO/'tests'))
    import gpu_support as gpu

    def run_engine(tmp_path, files, cases, timeout=180.0):
        files = {**files, '/cases.json':json.dumps(cases).encode()}
        # Node resolves the globally pinned runtime from the account home, while
        # product code continues to see the test's isolated HOME unchanged.
        env = {k:v for k,v in os.environ.items() if k != 'HOME'}
        with gpu._Server(files) as server:
            result = subprocess.run(['node',str(HERE/'pinned_gpu.mjs'),server.url,str(int(timeout*1000))],
                                    capture_output=True,text=True,env=env,timeout=timeout+30,cwd=HERE)
            (tmp_path/'pinned-browser.log').write_text(result.stdout+result.stderr)
            assert result.returncode == 0, result.stdout+result.stderr
            assert server.done.is_set(), 'Pinned browser exited before /done'
            assert 'error' not in server.summary, server.summary
            output = {key:gpu.np.frombuffer(data,gpu.np.uint8).reshape(height,width,4)[...,:3].copy()
                      for key,(width,height,data) in server.results.items()}
            return output,server.summary

    gpu.run_engine = run_engine
