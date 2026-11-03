from pathlib import Path
import json
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope import ROOT, WORK, sha, save, setup
from build_tools import load

def main():
    setup()
    package = ROOT / 'firmware/package_v38_g137/SD_ROOT'
    files = sorted(package.iterdir())
    assert len(files)==30 and all(p.is_file() for p in files)
    previous = ROOT / 'firmware/package_v37_g135/SD_ROOT'
    body, old = (package/'ilaunch3').read_bytes(), (previous/'ilaunch3').read_bytes()
    assert sha(previous/'ilaunch3')=='d00607405a5bd33290f99e9eda20df31a46386b6e0891cd5e62b15a9e3376283'
    assert sha(previous/'GXRCE.DAT')=='57743bc105bc3d51b7fa65b44efd90afb022b2356d4e7846d470cc0c641c438a'
    assert len(body)==len(old)
    checksum = sum(sum(body[0x200+k::6])*(k+2) for k in range(6))&0xffffffff
    assert checksum==struct.unpack_from('>I',body,0x16c)[0]
    legacy = load(ROOT/'firmware/stage2l_switch/tools/build.py','artifact137_elf')
    elf_path = ROOT/'firmware/resident_v38/local/resident/build/resident.elf'
    elf = legacy.Elf(elf_path)
    section = next(x for x in elf.sections if x['name']=='.resident')
    offset = lambda address: address-0x2004b000+0x200
    content = elf.content(section)
    assert body[offset(section['va']):offset(section['va'])+len(content)]==content
    assert body[offset(0x20054700):offset(0x200547f4)]==b'\xff'*244
    margin = 0x20054700-section['va']-len(content)
    assert margin>=176
    table = json.loads((ROOT/'firmware/resident_v38/local/resident/patch-manifest.json').read_text())
    ranges = [(0x16c,0x170),(offset(0x2005276c),offset(0x20054800))]
    for entry in table:
        if entry['enabled']:
            address = int(entry['address'],16)
            start = offset(address)
            expected = bytes.fromhex(entry['replacement'])
            assert body[start:start+len(expected)]==expected
            ranges.append((start,start+entry['length']))
    differences = [i for i,(a,b) in enumerate(zip(old,body)) if a!=b]
    assert all(any(start<=i<end for start,end in ranges) for i in differences)
    dat = (package/'GXRCE.DAT').read_bytes()
    layout = json.loads((ROOT/'firmware/engine_v54_g137/candidate/local/full-r13/layout.json').read_text())
    request = len(dat)+layout['bss_bytes']+7504
    assert request<=108124
    sections = [(int.from_bytes(dat[132+12*i:136+12*i],'big'),int.from_bytes(dat[136+12*i:140+12*i],'big')) for i in range(7)]
    assert sections[6][1]==20776
    assert int.from_bytes(dat[28:32],'big')==137
    trust = json.loads((ROOT/'firmware/resident_v38/local/resident/trust.json').read_text())
    assert dat[80:112].hex()==trust['resident_build_id']
    assert dat[212:228].hex()==trust['resident_abi_id']
    fixed = [p.name for p in files if p.name not in ('ilaunch3','GXRCE.DAT')]
    assert len(fixed)==28 and all((package/name).read_bytes()==(previous/name).read_bytes() for name in fixed)
    result={'status':'PASS_STATIC','files':30,'fixed_equal':28,'body_sha256':sha(package/'ilaunch3'),
            'dat_sha256':sha(package/'GXRCE.DAT'),'resident_elf_sha256':sha(elf_path),
            'resident_bytes':len(content),'resident_margin':margin,'checksum':f'{checksum:08x}',
            'body_changed_bytes':len(differences),'change_ranges_checked':True,'main_request':request,
            'main_limit':108124,'section7_bytes':sections[6][1],'generation':137,**trust}
    save(WORK/'artifact-results.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('modules','limits','pin_service')}))

if __name__=='__main__':
    main()
