"""Replay every native RPC write against byte-level whitelists, including aligned neighbours."""
import json
import struct
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_review import ROOT,LOCAL,PACKAGE,sha,save,setup
U16=lambda b,o:struct.unpack_from('>H',b,o)[0]
U32=lambda b,o:struct.unpack_from('>I',b,o)[0]

def main():
    setup();sys.path.insert(0,str(ROOT/'tools/native_harness_c'))
    from image_loader import Image
    raw=(PACKAGE/'local/SD_ROOT/GXRCE.DAT').read_bytes();receipts=[]
    for unit,name,index,firmware in [('mount','mount-owner-c',2,'l08firm3'),('50mm','j-owner-c',0,'jlaunch3'),('28mm','q-owner-c',1,'qlaunch3')]:
        result=json.loads((LOCAL/'native'/name/'result.json').read_text())
        assert result['status']=='PASS' and result['error'] is None
        directory=U32(raw,156)+64*index
        start=U32(raw,directory+12);mapping=raw[start:start+152]
        rows=[(U32(mapping,32+12*i),U16(mapping,36+12*i)) for i in range(9)]
        allowed={address for start,size in rows for address in range(start,start+size)}
        image=Image(ROOT/'artifacts/firmware/gxr-1.51'/firmware)
        page=None;cursor=None;overlay={};writes=0;neighbours=0;tvalues=[];tbefore=2
        tpage,taddress=U16(mapping,28),U16(mapping,30)
        t_selected=False
        for row in result['native_log']:
            if row['op']!='rpc':
                assert row['op'] in ('open','close','read','sd_id'),row
                if row['op']=='open':
                    assert row['path'] in ('/ATA1/GXRCE.DAT','/ATA1/GXRCE.CTL') and row.get('flags',0)==0
                continue
            assert row['slot']==8 and row['cmd'] in (21,22,23)
            command,value=row['cmd'],row['value']
            if command==23:
                page=value;t_selected=False
            elif command==21:
                if page==tpage:
                    assert value==taddress,(unit,'T selector outside whitelist',value,taddress)
                    cursor=None;t_selected=True
                else:
                    cursor=(page<<16)|(value&0xfffe)
            elif page==tpage:
                assert t_selected
                assert value>>8==tbefore>>8 and value&255 in (0,2)
                tvalues.append(value);tbefore=value
            else:
                assert cursor is not None
                assert {cursor,cursor+1}&allowed,(unit,hex(cursor),'write outside whitelist')
                old=overlay.get(cursor)
                if old is None:old=int.from_bytes(image.bytes_at(cursor,2),'big')
                for address,shift in ((cursor,8),(cursor+1,0)):
                    if address not in allowed:
                        assert (old>>shift)&255==(value>>shift)&255
                        neighbours+=1
                overlay[cursor]=value;writes+=1;cursor+=2
        assert writes>0 and tvalues
        assert all(row['S_equal_MAIN'] for row in result['owner_closes'])
        receipts.append(dict(unit=unit,row_write_halfwords=writes,unique_halfwords=len(overlay),
            whitelist_bytes=len(allowed),unchanged_neighbour_checks=neighbours,
            T_values=sorted(set(tvalues)),T_selector_checked=True,
            nonwhitelist_byte_changes=0,file_writes=0,persistent_S_changes=0))
    save(LOCAL/'rpc-whitelist.json',dict(status='PASS',dat_sha256=sha(raw),cases=receipts))
    print(json.dumps(receipts))

if __name__=='__main__':main()
