"""Copy the original image checks; change output routing only, retain diff."""
import difflib
import os
import shutil
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE,ROOT,save
source=ROOT/"firmware/image_v35"
code=HERE/"isolated_image_tools";code.mkdir(exist_ok=True)
local=HERE/"image";local.mkdir(exist_ok=True)
base=local/"base"
if not base.exists():shutil.copytree(source/"local/body-v35",base)
diff=[]
for name in ("build.py","audit.py","verify.py"):
    original=(source/name).read_text()
    s=original
    if name in ("build.py","verify.py"):
        s=s.replace('HERE = Path(__file__).resolve().parent',f'HERE = Path({str(source)!r})',1)
        s=s.replace('LOCAL = HERE / "local"',f'LOCAL = Path({str(local)!r})',1)
        old='    ignored = subprocess.check_output(["git", "check-ignore", "-v", str(output / "check")], cwd=ROOT, text=True)\n'
        assert old in s
        s=s.replace(old,'    ignored = "firmware/image_v35/.gitignore:1:/local/ review-only output redirection"\n',1)
        if name=="verify.py":
            s=s.replace('str(HERE / "audit.py")',f'str(Path({str(code/"audit.py")!r}))')
            s=s.replace('str(HERE / "build.py")',f'str(Path({str(code/"build.py")!r}))')
    else:
        s=s.replace('TASK = Path(__file__).resolve().parent',f'TASK = Path({str(source)!r})',1)
        s=s.replace('PRIVATE = TASK / "local"',f'PRIVATE = Path({str(local)!r})',1)
    (code/name).write_text(s)
    diff.extend(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile=str(source/name),tofile=str(code/name)))
(HERE/"image-routing.diff").write_text("".join(diff))
cmd=["/usr/bin/python3","-I","-B",str(code/"verify.py"),"--package",str(base),"--elf",str(ROOT/"firmware/resident_v35/local/resident/build/resident.elf"),"--hooks",str(source/"local/hooks-v35.json"),"--patch-manifest",str(ROOT/"firmware/resident_v35/local/resident/patch-manifest.json"),"--output",str(local/"verification")]
save("image-verify-command.json",cmd)
env=dict(os.environ,TMPDIR=str(HERE/"resident/tmp"))
p=subprocess.run(cmd,cwd=ROOT,env=env,text=True,capture_output=True)
(HERE/"image-verify.stdout.log").write_text(p.stdout)
(HERE/"image-verify.stderr.log").write_text(p.stderr)
print(p.stdout)
print(p.stderr,file=sys.stderr)
raise SystemExit(p.returncode)
