"""Independently bind packages, ELF sections, identities, limits and source delta."""
from collections import Counter
import argparse
import difflib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name',default='static')
    args=parser.parse_args()
    sys.path.insert(0,str(C.ROOT/'tools/native_harness_c'))
    from image_loader import Elf
    rows=[]
    parent=C.ROOT/'firmware/engine_v66_g155b'
    current=C.ROOT/'firmware/engine_v67_g155c'
    def files(root):
        return {str(p.relative_to(root)):p for p in root.rglob('*') if p.is_file() and
                not {'local','__pycache__'} & set(p.relative_to(root).parts)}
    old,new=files(parent),files(current)
    differences=[]
    patch=[]
    for name in sorted(old.keys()|new.keys()):
        a=old[name].read_bytes() if name in old else b''
        b=new[name].read_bytes() if name in new else b''
        if a!=b:
            differences.append(dict(path=name,old_sha256=C.digest(a),new_sha256=C.digest(b)))
            patch.extend(difflib.unified_diff(a.decode().splitlines(True),b.decode().splitlines(True),
                                             fromfile='g155b/'+name,tofile='g155c/'+name))
    (C.HERE/'evidence/source-delta.patch').write_text(''.join(patch))
    assert {r['path'] for r in differences}=={
        'candidate/build155.py','candidate/containers/product/adapter.c',
        'candidate/containers/product/boot_adapter.inc.c'},differences
    frozen=json.loads((C.ROOT/'research/review_v310_body_r1/evidence/inputs-before.json').read_text())['files']
    retained=[]
    for name,info in sorted(frozen.items()):
        if name.startswith(('firmware/image_v310/','firmware/resident_v310_g155/',
                            'firmware/package_v310_g155b/local/SD_ROOT/')) or name=='research/v310_resident/ABI.md':
            actual=C.file_info(C.ROOT/name)
            assert actual['bytes']==info['bytes'] and actual['sha256']==info['sha256'],name
            retained.append(actual)
    companions=[r for r in retained if r['path'].startswith('firmware/package_v310_g155b/local/SD_ROOT/')
                and Path(r['path']).name not in ('ilaunch3','GXRCE.DAT')]
    assert len(companions)==28
    assert C.digest((C.ROOT/'firmware/image_v310/local/ilaunch3').read_bytes())=='a04f1ed40143b2c54d7f28e3af8af1f9a5ef5e115edf49eb404b8e26a53509c8'
    trust=json.loads((C.ROOT/'firmware/resident_v310_g155/local/resident/trust.json').read_text())
    module_path=C.ROOT/'studio/src/gxr_studio/camdata/datcodec.py'
    spec=importlib.util.spec_from_file_location('g155c_review_codec',module_path)
    codec=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=codec
    spec.loader.exec_module(codec)
    for profile,build in (('test','boot-on'),('release','boot-off')):
        raw=C.dat(profile)
        header=bytearray(raw[:256])
        header[20:24]=bytes(4)
        assert zlib.crc32(header)==int.from_bytes(raw[20:24],'big')
        assert zlib.crc32(raw[256:])==int.from_bytes(raw[24:28],'big')
        assert int.from_bytes(raw[16:20],'big')==len(raw)
        assert raw[80:112].hex()==trust['resident_build_id'] and raw[212:228].hex()==trust['resident_abi_id']
        folder=C.ROOT/'firmware'/('package_v310_g155c_test' if profile=='test' else 'package_v310_g155c')
        assert {p.name for p in folder.iterdir()}=={'GXRCE.DAT','MANIFEST'}
        manifest=json.loads((folder/'MANIFEST').read_text())
        assert manifest['dat_sha256']==C.digest(raw) and manifest['boot']==int(profile=='test')
        linked=current/'candidate/local'/build
        elf=Elf(linked/'engine.elf')
        engine=next(s for s in elf.sections if s['name']=='.engine')
        bss=next(s for s in elf.sections if s['name']=='.bss')
        code_at,code_bytes=struct.unpack_from('>II',raw,132)
        assert engine['base']==code_at==256 and engine['data']==raw[code_at:code_at+code_bytes]
        assert (linked/'engine.bin').read_bytes()==engine['data']
        assert bss['base']==len(raw) and bss['size']==manifest['bss_bytes']==int.from_bytes(raw[116:120],'big')
        assert code_bytes<=trust['limits']['engine']==69632 and len(raw)<=98304 and len(raw)+bss['size']<=114688
        reloc_at,reloc_bytes=struct.unpack_from('>II',raw,144)
        assert reloc_bytes==8*int.from_bytes(raw[120:122],'big')
        relocations=[]
        for at in range(reloc_at,reloc_at+reloc_bytes,8):
            patch,target=struct.unpack_from('>II',raw,at)
            assert patch%4==0 and 256<=patch<256+code_bytes
            assert int.from_bytes(raw[patch:patch+4],'big')==target and 256<=target<len(raw)+bss['size']
            relocations.append(dict(patch=patch,target=target))
        listing=subprocess.check_output([str(C.ROOT/'research/tooling_m32r/prefix/bin/m32r-elf-objdump'),'-r',str(linked/'engine.elf')],text=True)
        kinds=Counter(__import__('re').findall(r'R_M32R_[A-Z0-9_]+',listing))
        assert kinds['R_M32R_GOTOFF_HI_SLO']==kinds['R_M32R_GOTOFF_LO']>0
        parsed=codec.parse(raw)
        assert codec.pack(parsed)==raw
        parent_raw=(C.ROOT/'firmware'/folder.name.replace('g155c','g155b')/'GXRCE.DAT').read_bytes()
        before=codec.parse(parent_raw)
        assert parsed.resident_id==before.resident_id and parsed.abi_id==before.abi_id
        assert parsed.kv2_block==before.kv2_block and parsed.users==before.users and parsed.looks==before.looks
        for unit in range(3):
            assert parsed.modules[unit].map==before.modules[unit].map and parsed.modules[unit].records==before.modules[unit].records
            for slot in range(1,9):assert parsed.entry_of(unit,slot)==before.entry_of(unit,slot)
        allocation=7628+((len(raw)+bss['size']+3)&~3)
        assert allocation==manifest['main_request']<=107612
        rows.append(dict(profile=profile,sha256=C.digest(raw),DAT_bytes=len(raw),code_bytes=code_bytes,
                         code_headroom=69632-code_bytes,bss_bytes=bss['size'],bss_base=bss['base'],
                         main_request=allocation,main_headroom=107612-allocation,
                         relocation_rows=relocations,ELF_relocation_counts=dict(kinds),
                         ELF_and_engine_bin_equal_DAT=True,Studio_roundtrip_equal=True,
                         all_24_parent_entries_equal=True,parent_knobs_users_looks_equal=True,
                         ABI_code_limit_doc_is_stale=True))
    C.save(args.name,dict(status='PASS',rows=rows,source_differences=differences,
                         frozen_body_and_package_files=retained,companions=len(companions),
                         Studio_codec=C.file_info(module_path),
                         boundary='No new build/relink. Final ELF bytes, BSS and relocation tables checked directly; prior relink evidence is hash-bound.'))


if __name__=='__main__':main()
