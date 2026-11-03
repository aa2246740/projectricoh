"""Decode explicitly declared native version 7; no implicit conversion."""
from pathlib import Path
import argparse,json,sys,struct
sys.path.insert(0,str(Path(__file__).resolve().parent))
import scope as s
import native_gate as g
def decode(raw,dat_hash,reference=None,reference_hash=None):
    source=(s.HERE/'reference-v7.json').read_bytes() if reference is None else reference
    if reference_hash is None:raise ValueError('independent reference digest required')
    return g.expand(raw,dat_hash,g.reference(source,reference_hash),reference_hash)
def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('record',type=Path);p.add_argument('--dat-sha256',required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--reference-sha256',required=True);p.add_argument('--output',type=Path);a=p.parse_args(argv)
    try:result=decode(a.record.read_bytes(),a.dat_sha256,a.reference.read_bytes(),a.reference_sha256)
    except (ValueError,OSError,KeyError,TypeError,struct.error,g.old.g.InvalidRecord) as error:result=g.incomplete(str(error))
    output=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if a.output:
        if not s.allowed(a.output):raise ValueError('output outside task')
        a.output.write_text(output)
    else:print(output,end='')
    return 0 if result['records_complete'] else 2
if __name__=='__main__':raise SystemExit(main())
