"""Relink only the task copy; no make, downloads, or original-tree writes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
sys.path.insert(0, str(Path(__file__).resolve().parent))
from safety import FAST, HERE, enable
enable()

b = FAST/'build'
s = FAST/'third_party/gdb-16.3'
inc = [b,b/'sim',b/'sim/m32r',s,s/'sim/m32r',s/'sim/common',b/'bfd',
       s/'bfd',s/'include',b/'opcodes',s/'opcodes',b/'gnulib/import',
       s/'gnulib/import',s/'sim']
cmd = ['clang','-dynamiclib','-O3','-g','-fPIC','-DHAVE_CONFIG_H','-DSIM_TOPDIR_BUILD']
cmd += ['-I'+str(p) for p in inc]
cmd += [str(FAST/'bridge.c'), str(FAST/'value.c'), str(b/'sim/m32r/libsim.a'),
        str(b/'opcodes/.libs/libopcodes.a'), str(b/'bfd/.libs/libbfd.a'),
        str(b/'libiberty/libiberty.a'), str(b/'gnulib/import/libgnu.a'),
        '-lz','-liconv','-lc++','-o',str(b/'libgxr_m32r.dylib')]
result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
(HERE/'runs/build.log').write_text(result.stdout+result.stderr)
(HERE/'runs/build-command.json').write_text(json.dumps(cmd,indent=2)+'\n')
if result.returncode:
    print(result.stderr)
    raise SystemExit(result.returncode)
print('built', b/'libgxr_m32r.dylib')
headers=Path(sysconfig.get_path('include'))
if not (headers/'Python.h').is_file():
    headers=Path('/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/Headers')
assert (headers/'Python.h').is_file(),headers
target=b/('_gxr_wire'+sysconfig.get_config_var('EXT_SUFFIX'))
cmd=['clang','-bundle','-O3','-g','-fPIC','-undefined','dynamic_lookup','-I'+str(headers),str(FAST/'wire_python.c'),'-o',str(target)]
result=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
(HERE/'runs/build-wire.log').write_text(result.stdout+result.stderr)
if result.returncode:print(result.stderr);raise SystemExit(result.returncode)
print('built',target)
