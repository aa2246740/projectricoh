"""Bind the local user-row calculation library to unchanged C source inputs."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyze as a
import json


def main(stage):
    if stage=='before':
        product=a.ROOT/'firmware/engine_v58_g150/candidate/containers/product'
        files=sorted(p for p in product.rglob('*') if p.is_file() and p.suffix in ('.c','.h','.inc'))
        files += [a.ROOT/'research/emptystack_v38/host_engine.c',
                  a.ROOT/'firmware/engine_v58_g150/candidate/engine_services/crc.c', a.HERE/'build_users.sh']
        a.dump('build_inputs.json',{str(p.relative_to(a.ROOT)):a.sha(p) for p in files})
    else:
        before=json.loads((a.HERE/'build_inputs.json').read_text())
        assert all(a.sha(a.ROOT/p)==h for p,h in before.items())
        a.dump('build_receipt.json',dict(inputs=before,all_inputs_unchanged=True,
            library_sha256=a.sha(a.TMP/'g150-host.dylib'),sdk='/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk',
            clang='/Library/Developer/CommandLineTools/usr/bin/clang',command='build_users.sh'))
        print('C source hashes unchanged:',len(before),flush=True)


if __name__=='__main__': main(sys.argv[1])
