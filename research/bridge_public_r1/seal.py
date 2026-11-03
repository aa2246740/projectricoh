"""Final scoped artifact hashes, relative to repository root; excludes its own manifest."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as c


def main():
    c.verify()
    manifest=c.HERE/'SHA256SUMS'
    files=sorted(p for folder in (c.HERE,c.DOWNLOADS) for p in folder.rglob('*')
                 if p.is_file() and p!=manifest and '__pycache__' not in p.parts)
    # This is the final stdout write, flushed before hashing the pipeline's seal.log.
    print('sealed delivered files',len(files),flush=True)
    manifest.write_text(''.join(c.sha(p)+'  '+str(p.relative_to(c.ROOT))+'\n' for p in files))
    for line in manifest.read_text().splitlines():
        digest,name=line.split('  ',1)
        assert c.sha(c.ROOT/name)==digest,'artifact changed while sealing: '+name


if __name__=='__main__':main()
