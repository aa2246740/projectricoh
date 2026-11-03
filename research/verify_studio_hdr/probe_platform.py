"""Check the HDR test's host condition with separate process imports."""
import json
import os
import subprocess
import sys
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
rows=[]
code='''import importlib,json,os,shutil,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
sys.path.insert(0,sys.argv[2])
kernel,platform,compiler=sys.argv[3:]
import hdr_support as h
from gxr_studio import privacy
os.uname=lambda: os.uname_result((kernel,"review","6.8","review","x86_64"))
sys.platform=platform
real_which=shutil.which
shutil.which=lambda name: ("/local/swiftc" if compiler=="yes" else None) if name=="swiftc" else real_which(name)
importlib.reload(h)
importlib.reload(privacy)
print(json.dumps({"kernel":kernel,"sys_platform":platform,"compiler":compiler,"has_imageio":h.HAS_IMAGEIO,"skip_imageio":bool(h.needs_imageio.mark.args[0]),"privacy_darwin":privacy._HOST_IS_DARWIN}))
'''
for kernel,platform,compiler in [('Linux','linux','no'),('Linux','darwin','yes'),('Darwin','linux','yes'),('Darwin','darwin','no')]:
    p=subprocess.run([sys.executable,'-I','-B','-c',code,str(ROOT/'studio/tests'),str(ROOT/'studio/src'),kernel,platform,compiler],check=True,capture_output=True,text=True,timeout=900)
    row=json.loads(p.stdout)
    assert row['has_imageio']==(kernel=='Darwin' and compiler=='yes')
    assert row['skip_imageio'] != row['has_imageio']
    assert row['privacy_darwin']==(kernel=='Darwin')
    rows.append(row)
(OUT/'platform_cases.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows))
