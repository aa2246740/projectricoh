"""Remove only this review's temporary root after checking process ownership."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import time

OUT = Path(__file__).resolve().parent
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-gpu-r3')
started = time.monotonic()
volume = subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace'])
info = plistlib.loads(volume)
assert info['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and info['FilesystemType'] == 'apfs' and info['WritableVolume']
(OUT/'volume.plist').write_bytes(volume)
(OUT/'df-final.txt').write_bytes(subprocess.check_output(['/bin/df','-h','/Volumes/Workspace']))
assert TMP.is_dir() and not TMP.is_symlink() and str(TMP.resolve()) == str(TMP)
events = [json.loads(s) for s in (OUT/'browser-lifecycle.jsonl').read_text().splitlines() if s]
starts = [e for e in events if e['event']=='start']
closes = [e for e in events if e['event']=='closed']
assert {e['pid'] for e in starts} == {e['pid'] for e in closes}
ps = subprocess.check_output(['/bin/ps','-axo','pid=,ppid=,ni=,command='],text=True)
remaining = []
for line in ps.splitlines():
    if any(marker in line for marker in (str(TMP), str(OUT/'run_review.py'), str(OUT/'pinned_chrome.mjs'))):
        remaining.append(line.strip())
assert not remaining, remaining
ports = sorted({int(__import__('urllib.parse',fromlist=['urlparse']).urlparse(e['url']).port) for e in starts})
guard = json.loads((OUT/'windows-loop-guard.json').read_text())
for s in guard['network_attempts_after']:
    match = re.search(r"127\.0\.0\.1', (\d+)",s)
    if match:ports.append(int(match[1]))
ports=sorted(set(ports))
assert 49667 not in ports
listen = subprocess.run(['/usr/sbin/lsof','-nP',*[f'-iTCP:{port}' for port in ports],'-sTCP:LISTEN'],capture_output=True,text=True)
assert listen.returncode in (0,1) and not listen.stdout.strip(), listen.stdout + listen.stderr
count = size = links = 0
for folder,dirs,files in os.walk(TMP,followlinks=False):
    for name in dirs+files:
        p=Path(folder)/name
        if p.is_symlink():links+=1
    for name in files:
        st=(Path(folder)/name).lstat()
        count+=1;size+=st.st_size
shutil.rmtree(TMP)
assert not TMP.exists()
receipt = {'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'temporary_root':str(TMP),'temporary_root_removed':True,
           'ordinary_files_and_file_links_removed':count,'file_bytes_removed':size,'symlinks_removed':links,
           'browser_starts':len(starts),'browser_normal_closes':len(closes),
           'owned_browser_processes_remaining':remaining,'owned_ports_checked':ports,
           'listeners_remaining':listen.stdout,'listener_check_exit_code':listen.returncode,
           'volume_uuid':info['VolumeUUID'],'elapsed_seconds':time.monotonic()-started}
(OUT/'cleanup.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
