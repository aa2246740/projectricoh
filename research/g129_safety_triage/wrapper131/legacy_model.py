"""Validate old entry conversion in a fresh target-model session."""
from pathlib import Path
import hashlib
import json
import struct
import zlib
from legacy_cases import records

ROOT=Path(__file__).resolve().parents[3]

def fixture(output):
    raw=(ROOT/'firmware/package_v36_g129/SD_ROOT/GXRCE.DAT').read_bytes()
    data=bytearray(raw);seventh=struct.unpack_from('>I',data,204)[0];extension=seventh+1408
    samples=records();assert len(samples)==32
    struct.pack_into('>H',data,extension+24,len(samples))
    for index,item in enumerate(samples):data[extension+1216+24*index:extension+1240+24*index]=item
    struct.pack_into('>I',data,extension+16,0)
    struct.pack_into('>I',data,extension+16,zlib.crc32(data[extension:extension+1984])&0xffffffff)
    struct.pack_into('>I',data,24,zlib.crc32(data[256:])&0xffffffff)
    struct.pack_into('>I',data,20,0)
    struct.pack_into('>I',data,20,zlib.crc32(data[:256])&0xffffffff)
    path=Path(output)/'local/old-entry-fixture.dat';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    return path

def verify(session,output):
    raw=(ROOT/'firmware/package_v36_g129/SD_ROOT/GXRCE.DAT').read_bytes();dat=session.p.dat
    section=struct.unpack_from('>II',dat,132)
    assert raw[section[0]:sum(section)]==dat[section[0]:sum(section)]
    assert int.from_bytes(dat[28:32],'big')==129 and len(dat)==len(raw)
    layout=json.loads((ROOT/'research/g129_knobs/adapter-layout.json').read_text())
    fields=json.loads((ROOT/'research/g129_safety_triage/wrapper/session-layout.json').read_text())
    address=session.p.symbol_pc('n');count=0
    assert session.h.u(address+fields['initialized'],1)==1
    for index,item in enumerate(records()):
        old=struct.unpack('11b',item[10:21]);wanted=[100,old[0],old[1],old[2],0,old[3],0,0,0,0]
        actual=list(struct.unpack('>10h',session.h.b.read(address+layout['ui']+layout['ui.saved']+20*index,20)))
        assert actual==wanted,('old_entry_vector',session.unit,index)
        count+=1
    value={'status':'PASS','unit':session.unit,'records':count,'fixture_sha256':hashlib.sha256(dat).hexdigest(),
           'final_dat_sha256':hashlib.sha256(raw).hexdigest(),'code_byte_equal':True,
           'initialization_visits':int(session.p.visited('ig_init')),
           'scope':'Synthetic old entries; actual final engine in a fresh M32R model session.'}
    (Path(output)/('old-entry-model-'+session.unit+'.json')).write_text(json.dumps(value,indent=2)+'\n')
