from pathlib import Path
import json
import subprocess
import sys
# g139 copy of research/emptystack_v38/list_check.py (via research/g138_persist/es): same C check, current
# sources and package; helper C files are read from emptystack_v38 unchanged.
import hashlib, os
ROOT = Path(__file__).resolve().parents[3]
HELPERS = ROOT / 'research/emptystack_v38'
WORK = Path(__file__).resolve().parent
LOCAL = WORK / 'local'
def setup():
    LOCAL.mkdir(parents=True, exist_ok=True)
    os.environ['TMPDIR'] = '/Volumes/Workspace/Scratch/tmp/projectricoh/g139'
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p, v):
    Path(p).write_text(json.dumps(v, indent=2) + '\n')
neutral = lambda text: text

def main():
    setup()
    product = ROOT / 'firmware/engine_v56_g139/candidate/containers/product'
    output = LOCAL / 'list-check'
    source = (product / 'adapter.c').read_text()
    start = source.index('static EngStatus uv_move(')
    end = source.index('static int32_t uv_disp(', start)
    extracted = LOCAL / 'adapter-check.c'
    extracted.write_text((WORK / 'adapter_check.h').read_text() + source[start:end] + (HELPERS / 'adapter_check.inc.c').read_text())
    command = ['/usr/bin/cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
               '-ffunction-sections', '-fdata-sections', '-Wl,-dead_strip',
               '-I', str(product), '-I', str(product / 'kv2'), str(WORK / 'list_check.c'), str(extracted),
               str(product / 'kv2/kv_ui.c'), str(product / 'kv2/kv_data.c'),
               str(product / 'ui_v2_data.c'), str(product / 'src/firmware/card_container_v2/common.c'),
               str(product.parents[1] / 'engine_services/crc.c'),
               '-o', str(output)]
    built = subprocess.run(command, text=True, capture_output=True)
    (LOCAL / 'list-build.log').write_text(neutral(built.stdout+built.stderr))
    assert built.returncode == 0, neutral(built.stderr)
    dat = ROOT / 'firmware/package_v38_g139/SD_ROOT/GXRCE.DAT'
    result = subprocess.run([str(output), str(dat)], text=True, capture_output=True)
    (LOCAL / 'list-run.log').write_text(neutral(result.stdout+result.stderr))
    assert result.returncode == 0, neutral(result.stdout+result.stderr)
    evidence = json.loads(result.stdout)
    evidence.update(dat_sha256=sha(dat), executable_sha256=sha(output), adapter_sha256=sha(product / 'adapter.c'), extracted_sha256=sha(extracted))
    save(WORK / 'list-results.json', evidence)
    print(json.dumps(evidence))

if __name__ == '__main__':
    main()
