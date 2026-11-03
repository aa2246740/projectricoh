"""Check frozen body identities and Studio byte-for-byte final-DAT roundtrips."""
import hashlib
import argparse
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--name',default='final-increment-static');a=p.parse_args()
    frozen=json.loads((ROOT/'research/review_v310_body_r1/evidence/inputs-before.json').read_text())['files']
    selected={name:meta for name,meta in frozen.items() if
        name.startswith('firmware/image_v310/') or name.startswith('firmware/resident_v310_g155/') or
        name.startswith('firmware/package_v310_g155b/local/SD_ROOT/') or
        name=='research/v310_resident/ABI.md'}
    rows=[]
    for name,meta in sorted(selected.items()):
        raw=(ROOT/name).read_bytes();digest=hashlib.sha256(raw).hexdigest()
        assert len(raw)==meta['bytes'] and digest==meta['sha256'],name
        rows.append(dict(path=name,bytes=len(raw),sha256=digest))
    companions=[r for r in rows if r['path'].startswith('firmware/package_v310_g155b/local/SD_ROOT/') and Path(r['path']).name not in ('ilaunch3','GXRCE.DAT')]
    assert len(companions)==28,len(companions)
    module_path=ROOT/'studio/src/gxr_studio/camdata/datcodec.py'
    spec=importlib.util.spec_from_file_location('tweak_studio_codec',module_path)
    codec=importlib.util.module_from_spec(spec);sys.modules[spec.name]=codec;spec.loader.exec_module(codec)
    roundtrip=[]
    for name in ('package_v310_g155c','package_v310_g155c_test'):
        path=ROOT/'firmware'/name/'GXRCE.DAT';raw=path.read_bytes();dat=codec.parse(raw)
        packed=codec.pack(dat);assert packed==raw
        parent_path=ROOT/'firmware'/name.replace('g155c','g155b')/'GXRCE.DAT'
        parent_raw=parent_path.read_bytes()
        assert hashlib.sha256(parent_raw).hexdigest()==frozen[str(parent_path.relative_to(ROOT))]['sha256']
        parent=codec.parse(parent_raw)
        assert dat.resident_id==parent.resident_id and dat.abi_id==parent.abi_id
        assert dat.ids==parent.ids and dat.kv2_block==parent.kv2_block
        assert dat.users==parent.users and dat.user_names==parent.user_names and dat.looks==parent.looks
        entries=[]
        for unit in range(3):
            assert dat.modules[unit].map==parent.modules[unit].map
            assert dat.modules[unit].records==parent.modules[unit].records
            for slot in range(1,9):
                entry=dat.entry_of(unit,slot);assert entry==parent.entry_of(unit,slot)
                entries.append(dict(unit=unit,slot=slot,bytes=len(entry),sha256=hashlib.sha256(entry).hexdigest()))
        roundtrip.append(dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest(),
            compared_bytes=len(raw),generation=dat.generation,byte_equal=True,
            parent_sha256=hashlib.sha256(parent_path.read_bytes()).hexdigest(),
            parent_entries_equal=entries,looks_equal=len(dat.looks),users_equal=len(dat.users),
            knob_block_equal=True,unit_maps_and_records_equal=True))
    out=HERE/'evidence'/(a.name+'.json');assert not out.exists()
    out.write_text(json.dumps(dict(status='PASS',layer='静态与 Studio 实际编解码器',
        freeze_reference='research/review_v310_body_r1/evidence/inputs-before.json',frozen_files=rows,
        companion_count=len(companions),Studio_codec_sha256=hashlib.sha256(module_path.read_bytes()).hexdigest(),
        Studio_roundtrip=roundtrip),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',frozen_files=len(rows),companions=len(companions),roundtrips=roundtrip)))


if __name__=='__main__':main()
