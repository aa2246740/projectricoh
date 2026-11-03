import hashlib
import json
import runpy
import struct
import zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'research/review_v38_g137'
fixture_path=OUT/'local/jobs/user-tool/local/checks/review_g124/local/user-fixture-78dcbb9a2735/GXRCE.DAT'
base=(ROOT/'firmware/package_v38_g137/local/SD_ROOT/GXRCE.DAT').read_bytes()
fixture=fixture_path.read_bytes()
digest=lambda raw:hashlib.sha256(raw).hexdigest()
assert digest(base)=='78dcbb9a2735cd84e55385683ce0296b97818ddf90f8b492d9003512dbeff3f8'
assert digest(fixture)=='061f781ff2b966c7beeafd2607fdf1baa31707a9fe9aaa4b3fe1f4747e893f2b'
assert len(base)==len(fixture)==89936
assert struct.unpack_from('>I',fixture,28)[0]==137
header=bytearray(fixture[:256]);header[20:24]=b'\0'*4
assert zlib.crc32(header)==int.from_bytes(fixture[20:24],'big')
assert zlib.crc32(fixture[256:])==int.from_bytes(fixture[24:28],'big')
sections=[]
for index in range(7):
    row=struct.unpack_from('>HHII',base,128+12*index)
    assert row==struct.unpack_from('>HHII',fixture,128+12*index)
    kind,flags,start,size=row
    diff=[offset for offset in range(start,start+size) if base[offset]!=fixture[offset]]
    ranges=[]
    for offset in diff:
        if ranges and ranges[-1][1]+1==offset:ranges[-1][1]=offset
        else:ranges.append([offset,offset])
    sections.append({'kind':kind,'bytes':size,'equal':not diff,'changed_bytes':len(diff),'changed_ranges':ranges})
assert all(row['equal'] for row in sections[:6])
header_diff=[offset for offset in range(256) if base[offset]!=fixture[offset]]
assert all(20<=offset<28 for offset in header_diff)
tool=runpy.run_path(str(OUT/'users_gxui.py'),run_name='current_users_api')
parsed=tool['parse_dat'](fixture)
assert len(parsed[3])==32
empty=tool['replace_users'](fixture,[])
assert empty==base
result={'status':'PASS_STATIC','base_sha256':digest(base),'fixture_sha256':digest(fixture),
        'fixture':str(fixture_path.relative_to(ROOT)),'generation':137,'bytes':len(fixture),
        'header_changed_offsets':header_diff,'sections':sections,'header_and_data_crc_checked':True,
        'first_six_sections_equal':True,'fixture_parse_passed':True,'user_entries':len(parsed[3]),
        'roundtrip_empty_exact':True,'old_tool':'research/review_g135_gpt/users_gxui.py'}
(OUT/'evidence/users-fixture-resume.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({key:value for key,value in result.items() if key!='sections'}))
