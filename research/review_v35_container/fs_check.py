from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import audit as a
flags=['/usr/bin/clang','-std=c11','-O1','-g','-DRV_HOST','-DENG_HOST','-DPN_CORE_HEADER="../core/eng_core.h"','-DPN_GXTS_SHARED_PARAMETER','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all']
a.run([*flags,a.HERE/'fs_probe.c','-o',a.HERE/'fs_probe'],'fs-probe-final-compile')
rows=[]
for case in ('normal','absent','short','long','readonly','partial','duplicate','transient','persistent','bounds','validated'):
 p=a.run([a.HERE/'fs_probe',case],'fs-'+case,check=False)
 rows.append(dict(case=case,returncode=p.returncode,stdout=p.stdout.decode(),stderr=p.stderr.decode()))
 print(p.stdout.decode().strip(),flush=True)
a.dump('fs-results.json',rows);assert all(x['returncode']==0 for x in rows)
alt=a.HERE/'minimal-fix/fs_probe_disabled'
a.run([*flags,'-Wno-unused-function','-DREVIEW_BLACKBOX_SOURCE="minimal-fix/blackbox.c"','-I',a.HERE/'isolated/candidate/containers/product',a.HERE/'fs_probe.c','-o',alt],'disabled-fs-probe-final-compile')
p=a.run([alt,'disabled'],'disabled-fs-final')
(a.HERE/'minimal-fix/no-media-writes.stdout').write_bytes(p.stdout)
(a.HERE/'minimal-fix/no-media-writes.stderr').write_bytes(p.stderr)
print('PASS 11 file boundary cases and no-media-write alternative')
