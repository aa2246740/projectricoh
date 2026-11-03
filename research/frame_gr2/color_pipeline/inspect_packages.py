#!/usr/bin/env python3
"""Offline package inventory and javap disassembly. Never loads target classes."""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile

H=Path(__file__).resolve().parent
E=H/'evidence'
sha=lambda b:hashlib.sha256(b).hexdigest()
apk=H/'assets/FRAME-Android-0.65.3.apk'
assert sha(apk.read_bytes())=='ac4a17544695d2a41cfb725f20bcb60c96252d4d089dade99028e7a5bc8eb148'
z=zipfile.ZipFile(apk)
inventory=[]
selected=[]
for i in z.infolist():
    inventory.append(dict(member=i.filename,size=i.file_size,compressed_size=i.compress_size))
    wanted=i.filename.startswith(('assets/luts/','assets/licenses/','assets/flutter_assets/assets/profiles/')) or i.filename in ['assets/gallery.json','lib/arm64-v8a/libapp.so','classes.dex']
    if wanted:
        p=H/'assets/apk'/i.filename
        assert p.resolve().is_relative_to((H/'assets/apk').resolve())
        p.parent.mkdir(parents=True,exist_ok=True)
        data=z.read(i);p.write_bytes(data)
        selected.append(dict(member=i.filename,size=len(data),sha256=sha(data)))
(E/'apk-inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
(E/'apk-selected-members.json').write_text(json.dumps(selected,indent=2)+'\n')
jar=H/'assets/macos/frame-core.jar'
assert sha(jar.read_bytes())=='ef59a0a3585010958cf20b0302dc93d7ff52dc457bafe5292b5b69c8960bc232'
# The existing Homebrew JDK is an analysis tool, not the runtime bundled by FRAME.
candidates=sorted(Path('/opt/homebrew/Cellar/openjdk').glob('*/libexec/openjdk.jdk/Contents/Home/bin/javap'))
if not candidates:raise SystemExit('Host javap missing; no installation or bundled-runtime fallback.')
javap=candidates[-1]
classes=['dev.gr2.filters.BalancedProfileCodec','dev.gr2.filters.ProfileCodec2']+['dev.gr2.profile2.'+n for n in ['ProfileDocument','ProfileChannel','LibraryClient','LibraryClient$Catalog','NativeGeometry','NativeBalancedFitter','NativeQualityFitter','NativeCurveFitter','NativeColorFitter','NativeRgbColorFitter','CubeLut','CubeLut$Fit','PostMatrix','ColorSpaces','MainActivity']]
out=E/'javap';out.mkdir(exist_ok=True)
rows=[]
for c in classes:
    command=[str(javap),'-c','-p','-constants','-s','-classpath',str(jar),c]
    result=subprocess.run(command,check=True,capture_output=True,text=True)
    p=out/(c.rsplit('.',1)[-1]+'.txt');p.write_text(result.stdout)
    rows.append(dict(class_name=c,output=str(p.relative_to(H)),lines=result.stdout.count('\n'),sha256=sha(result.stdout.encode())))
(E/'javap-manifest.json').write_text(json.dumps(dict(tool=str(javap),version=subprocess.run([str(javap),'-version'],check=True,capture_output=True,text=True).stdout.strip(),jar_sha256=sha(jar.read_bytes()),classes=rows),indent=2)+'\n')
print(f'PASS: {len(inventory)} APK members, {len(selected)} selected members, {len(classes)} static class listings.')
