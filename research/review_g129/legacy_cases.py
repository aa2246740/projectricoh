"""Thirty-two old-format entries for conversion checks."""
import struct

def records():
    groups=('GRP','GRN','HCB','STD','FCC','FCN','LCH','LVI')
    result=[]
    for slot,group in enumerate(groups,1):
        patterns=[(0,0,0,0),(1,0,0,0),(0,1,-1,0),(1,-1,1,0 if slot==3 else -1)]
        for ordinal,values in enumerate(patterns,1):
            record=bytearray(24);record[0]=slot
            record[2:9]=(group+('*' if any(values) else '-')+str(ordinal).zfill(3)).encode()
            record[10:21]=struct.pack('11b',*values,*([0]*7))
            struct.pack_into('>H',record,22,ordinal)
            result.append(bytes(record))
    assert len(result)==32
    return result
