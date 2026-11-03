"""Apply the final generation 121 source set to the prepared working tree."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,TREE,file_sha

def main():
    records=json.loads((OUT/'source-update.json').read_text())['files']
    for row in records:
        path=TREE/row['path']
        actual=file_sha(path) if path.exists() else None
        assert actual in (row['base_sha256'],row['sha256']),(row['path'],actual)
    for row in records:
        path=TREE/row['path'];path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(row['text'])
        assert file_sha(path)==row['sha256']
    print('PASS final source set',len(records),flush=True)

if __name__=='__main__':main()
