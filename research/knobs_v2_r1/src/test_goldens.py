"""Literal user-observable results on a mathematical fixture, no Ricoh arrays."""
import struct
import knobs as k
from bridge import compare


def run(c):
    fixture=bytearray(552);fixture[0]=4;fixture[1]=1;struct.pack_into('>H',fixture,445,2)
    for at in (20,284,456):struct.pack_into('>31H',fixture,at,*(128*i for i in range(1,32)))
    ramp=bytes([8*i for i in range(32)]+[255])
    for at in (82,346,379,412,518):fixture[at:at+33]=ramp
    fixture[115:211]=bytes((32,0,128,32))*24
    pure_R=(1024,0,0,0,0,0,0,0,0,0,128,128,0,0)
    struct.pack_into('>28H',fixture,216,*(pure_R+pure_R));k.checksum(fixture);base=bytes(fixture)
    pos=k.request_for('warmth',4096)
    out,_=compare(c,base,base,pos)
    expected=[1024,0,0,-140,0,0,180,0,0,0,128,128,0,0]
    assert k.words(out)==expected*2
    out,_=compare(c,base,base,k.request_for('contrast',4096))
    assert [out[82+i] for i in (0,8,16,24,32)]==[0,8,128,248,255]
    out,_=compare(c,base,base,k.request_for('fade',4096))
    assert [out[82+i] for i in (0,8,16,24,32)]==[80,124,168,212,255]
    out,_=compare(c,base,base,k.request_for('fade',-4096))
    assert [out[82+i] for i in (0,8,16,24,32)]==[0,5,15,41,255]
    out,_=compare(c,base,base,k.request_for('split',4096))
    assert [out[379+i] for i in (0,8,16,24,32)]==[0,8,128,248,255]
    assert [out[412+i] for i in (0,8,16,24,32)]==[0,120,128,136,255]
    assert out[82:115]==ramp and out[1]&6==6 and out[445:447]==b'\0\0'
    for dose,expected in ((-4096,[96,896,32]),(4096,[930,80,14])):
        out,_=compare(c,base,base,k.request_for('filter',dose));assert k.words(out)[:3]==expected
    assert compare(c,base,base,k.Request())[0]==base
    return 8
