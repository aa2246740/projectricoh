"""Create disposable, emulator-only images and DAT identity fixtures."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT/'research/v310_window'
TEMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/v310-window-r1')
DAT = ROOT/'firmware/package_v39_g153_test/local/SD_ROOT/GXRCE.DAT'
DAT_SHA = '5afc388902c9931d55c831e5afc27684d032193c9775e77a8509e9098e65ba7b'
ENGINE = ROOT/'firmware/engine_v62_g153/candidate/local/full-r13/engine.elf'
OFFICIAL = ROOT/'artifacts/firmware/gxr-1.51/ilaunch3'


def sha(value):
    return hashlib.sha256(value if isinstance(value,bytes) else Path(value).read_bytes()).hexdigest()


def write_data(path,data):
    if path.exists() and path.read_bytes()==data:return
    assert path.is_relative_to(TEMP)
    temporary=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
    temporary.write_bytes(data);temporary.replace(path)


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
    return mod


def prepare(name):
    assert Path(os.environ['TMPDIR']).resolve()==TEMP
    assert sha(DAT)==DAT_SHA
    folder=HERE/'options'/name
    size=json.loads((folder/'measurement.json').read_text())
    assert size['link_ok']
    sys.path.insert(0,str(ROOT/'research/review_body_v39/checks'))
    import static_check as S
    elf=folder/'build/resident.elf'
    image=S.rebuild(OFFICIAL.read_bytes(),S.Elf(elf),json.loads((folder/'patch-manifest.json').read_text()))
    assert len(image)==len(OFFICIAL.read_bytes())
    assert struct.unpack_from('>I',image,0x16c)[0]==S.checksum(image)
    trust=json.loads((folder/'trust.json').read_text())
    data=bytearray(DAT.read_bytes())
    assert data[48:80].hex()==trust['body_sha256']
    data[80:112]=bytes.fromhex(trust['resident_build_id'])
    data[212:228]=bytes.fromhex(trust['resident_abi_id'])
    struct.pack_into('>I',data,20,zlib.crc32(data[:20]+bytes(4)+data[24:256]))
    old=DAT.read_bytes()
    changed=[i for i,(a,b) in enumerate(zip(old,data)) if a!=b]
    allowed=set(range(20,24))|set(range(80,112))|set(range(212,228))
    assert set(changed)<=allowed and data[256:]==old[256:]
    target=TEMP/'fixtures'/name;target.mkdir(parents=True,exist_ok=True)
    body=target/'main-image.bin';write_data(body,image)
    dat=target/'test-data.dat';write_data(dat,bytes(data))
    result=dict(name=name,elf=str(elf),elf_sha256=sha(elf),body=str(body),body_sha256=sha(image),
                dat=str(dat),dat_sha256=sha(bytes(data)),original_dat_sha256=DAT_SHA,
                dat_changed_offsets=changed,dat_body_unchanged=True,engine=str(ENGINE),engine_sha256=sha(ENGINE),
                code_bytes=size['code_bytes'],free_above_margin=size['free_above_margin'])
    evidence=HERE/'evidence';evidence.mkdir(exist_ok=True)
    (evidence/('fixture-'+name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    for name in sys.argv[1:]:
        result=prepare(name)
        print(json.dumps({k:result[k]for k in ['name','code_bytes','free_above_margin','body_sha256','dat_sha256']}))
