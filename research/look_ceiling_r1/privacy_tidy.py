"""Keep source camera metadata and original matrices in the ignored local folder."""
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
LOCAL=HERE/'local'

def write(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
    p=HERE/'protocol.json'
    doc=json.loads(p.read_text())
    if not (LOCAL/'protocol_private.json').exists():write(LOCAL/'protocol_private.json',doc)
    doc['scene_inventory']=[{k:v for k,v in row.items() if k not in ('matrix','neutral','as_shot_neutral')}
                            for row in doc['scene_inventory']]
    write(p,doc)
    p=HERE/'legacy_gr_checks.json'
    if p.exists():
        doc=json.loads(p.read_text())
        private={k:doc.pop(k) for k in ('bridge','native_renderer') if k in doc}
        if private:write(LOCAL/'legacy_gr_evidence.json',private)
        write(p,doc)

if __name__=='__main__':main()
