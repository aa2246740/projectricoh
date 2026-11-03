"""Seal public and ignored artifacts. Hash bases are explicit; manifests exclude themselves."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import HERE,LOCAL,guard,sha


def paths(base, public=False):
    out=[]
    for p in base.rglob('*'):
        if public and p.is_relative_to(LOCAL):
            continue
        if p.is_symlink():
            raise ValueError(f'symlink in deliverable: {p}')
        if p.is_file() and p != base/'SHA256SUMS':
            out.append(p)
    return sorted(out)


def main():
    guard()
    for base,public,label in ((HERE,True,'research/body_lut/'),
                              (LOCAL,False,'research/body_lut/local/')):
        files=paths(base,public)
        text=f'# SHA-256 base directory: {label}\n# This manifest excludes only itself.\n'
        text+=''.join(f'{sha(p)}  {p.relative_to(base).as_posix()}\n' for p in files)
        (base/'SHA256SUMS').write_text(text)
        print(label,len(files),'files')


if __name__=='__main__':
    main()
