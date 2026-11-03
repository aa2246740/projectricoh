#!/usr/bin/env python3
"""Independent, offline byte-bound storage research. Writes only this directory."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / 'local'
OFFICIAL = ROOT / 'artifacts/firmware/gxr-1.51/ilaunch3'
BODY = ROOT / 'firmware/image_v36/local/package/SD_ROOT/ilaunch3'
OBJDUMP = ROOT / 'research/tooling_m32r/prefix/bin/m32r-elf-objdump'
EXPECTED = {OFFICIAL: 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
            BODY: '50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008'}

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()

def save(name, obj):
    assert re.fullmatch(r'[A-Za-z0-9_.-]+', name), name
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')

def preflight():
    assert sys.flags.isolated and sys.flags.dont_write_bytecode
    p = plistlib.loads(subprocess.check_output(['/usr/sbin/diskutil','info','-plist','/Volumes/Workspace']))
    assert p['MountPoint'] == '/Volumes/Workspace'
    assert p['FilesystemType'] == 'apfs'
    assert p['VolumeUUID'] == '14BE04EB-AF49-497E-B36A-B078B2F7C5E8'
    assert p['WritableVolume']
    assert subprocess.run(['git','check-ignore','-q',str(OUT/'guard')],cwd=ROOT).returncode == 0
    OUT.mkdir(exist_ok=True)
    return {k:p[k] for k in ('MountPoint','FilesystemType','VolumeUUID','WritableVolume')}

class Image:
    def __init__(self):
        for path, digest in EXPECTED.items():
            assert sha(path) == digest, str(path)
        self.data, self.body = OFFICIAL.read_bytes(), BODY.read_bytes()
        self.sections = []
        for i in range(16):
            off, va, size, bss, bn = struct.unpack_from('>5I', self.data, 32+20*i)
            assert off+512+size <= len(self.data)
            self.sections.append(dict(index=i,file=off+512,vma=va,size=size,bss=bss,bss_size=bn))

    def off(self, va, size=1):
        hits = [s['file']+va-s['vma'] for s in self.sections if s['vma'] <= va and va+size <= s['vma']+s['size']]
        assert len(hits) == 1, (hex(va),size)
        return hits[0]

    def raw(self, va, size):
        off = self.off(va,size)
        return self.data[off:off+size]

    def dump(self, start, end, label):
        assert re.fullmatch(r'[A-Za-z0-9_.-]+',label)
        raw = self.raw(start,end-start)
        off = self.off(start,len(raw))
        assert self.body[off:off+len(raw)] == raw, label
        path = OUT / (label+'.bin')
        path.write_bytes(raw)
        asm = subprocess.check_output([str(OBJDUMP),'-D','-b','binary','-m','m32r','-EB',
                        '--adjust-vma='+hex(start),str(path)],text=True)
        (OUT/(label+'.asm.txt')).write_text('# Official bytes equal fixed v3.6 body. Linear disassembly may include data.\n'
            + '# File '+hex(off)+', VMA '+hex(start)+'\n'+asm)
        return dict(label=label,start=hex(start),end=hex(end),file=hex(off),bytes=len(raw),sha256=sha(path),official_equals_body=True)

def verify_references():
    rows, protected = [], {str(p.relative_to(ROOT)):sha(p) for p in (*EXPECTED,OBJDUMP)}
    for task in ('user_storage_r1','user_storage_r2','user_storage_r3'):
        manifest = ROOT/'research'/task/'SHA256SUMS'
        checked = 0
        for line in manifest.read_text().splitlines():
            if not line.strip():
                continue
            digest, rel = line.split(maxsplit=1)
            rel = rel.removeprefix('*')
            assert rel.startswith('research/'+task+'/'), rel
            path = ROOT/rel
            assert path.is_file() and sha(path) == digest, rel
            protected[rel] = digest
            checked += 1
        protected[str(manifest.relative_to(ROOT))] = sha(manifest)
        rows.append(dict(path=str(manifest.relative_to(ROOT)),sha256=sha(manifest),entries=checked,status='PASS'))
    return rows,protected

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action',choices=('init','dump','words','pointers','after'))
    ap.add_argument('args',nargs='*')
    args = ap.parse_args()
    volume = preflight()
    im = Image()
    if args.action == 'init':
        assert not (OUT/'protected-before.json').exists()
        rows, protected = verify_references()
        save('references.json',rows)
        save('protected-before.json',protected)
        save('volume.json',volume)
        save('sections.json',im.sections)
        print(json.dumps(dict(status='PASS',references=rows,protected_files=len(protected))))
    elif args.action == 'after':
        before=json.loads((OUT/'protected-before.json').read_text())
        changed=[rel for rel,digest in before.items() if not (ROOT/rel).is_file() or sha(ROOT/rel)!=digest]
        save('protected-check.json',dict(status='PASS' if not changed else 'FAIL',checked=len(before),changed=changed))
        assert not changed,changed
        print('PASS protected inputs:',len(before))
    elif args.action == 'dump':
        row=im.dump(int(args.args[0],0),int(args.args[1],0),args.args[2])
        index=OUT/'windows.json'
        rows=json.loads(index.read_text()) if index.exists() else []
        rows=[r for r in rows if r['label']!=row['label']]+[row]
        save('windows.json',rows)
        print(json.dumps(row))
    elif args.action == 'words':
        start,end=map(lambda x:int(x,0),args.args)
        for va in range(start,end,16):
            raw=im.raw(va,min(16,end-va))
            print(hex(va),raw.hex(),' '.join(hex(x) for x in struct.unpack('>'+str(len(raw)//4)+'I',raw[:len(raw)//4*4])))
    elif args.action == 'pointers':
        target=int(args.args[0],0)
        rows=[]
        for s in im.sections:
            raw=im.raw(s['vma'],s['size'])
            at=raw.find(target.to_bytes(4,'big'))
            while at>=0:
                rows.append(dict(vma=hex(s['vma']+at),file=hex(s['file']+at),target=hex(target),aligned4=(s['vma']+at)%4==0))
                at=raw.find(target.to_bytes(4,'big'),at+1)
        save('pointers-'+hex(target)+'.json',rows)
        print(json.dumps(rows))
if __name__=='__main__':
    main()
