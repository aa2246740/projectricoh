"""Regenerate the combined manifest, table index and static selection evidence."""
import csv
import hashlib
import json
import pathlib
import re
import runpy
import struct

ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'data'


def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def main():
    allrows=[]
    for name in ['sources/latest_download_manifest.json','historical_download_manifest.json','sources/additional_download_manifest.json']:
        allrows+=json.loads((ROOT/name).read_text())
    assert len({(x['model'],x['version']) for x in allrows})==len(allrows)
    dump(ROOT/'download_manifest.json',allrows)
    dump(ROOT/'sources/all_download_requests.json',[{k:x[k] for k in ['model','version','url']} for x in allrows])
    tables=json.loads((DATA/'candidate_index.json').read_text())
    with (DATA/'candidate_index.csv').open('w',newline='') as stream:
        fields=['model','version','mode','id','vma','payload_offset_hex','format','size','sha256','association','note']
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(tables)
    latest=json.loads((DATA/'unpack_manifest.json').read_text())
    additional=json.loads((DATA/'additional_unpack_manifest.json').read_text())
    results=[]
    for old in additional:
        new=next(x for x in latest if x['model']==old['model'])
        if old['model']=='gr3x':
            doc=json.loads((DATA/'gr3x-1.60-tables.json').read_text())
            before=pathlib.Path(old['images'][0]['path']).read_bytes();after=pathlib.Path(new['images'][0]['path']).read_bytes()
            selected=[(t['id'],t['sha256'],t['payload_offset'],t['size']) for t in doc['tables'] if t['id'] in ['Positive_Film-look-matrix','Negative_Film-look-matrix']]
        else:
            doc=json.loads((DATA/'grd4-sibling.json').read_text())
            before=pathlib.Path(next(i for i in old['images'] if i['path'].endswith('g04firm3.bin'))['path']).read_bytes()
            after=pathlib.Path(next(i for i in new['images'] if i['path'].endswith('g04firm3.bin'))['path']).read_bytes()
            selected=[(t['id'],t['sha256'],t['file_offset'],t['size']) for t in doc['tables']]
        for name,digest,offset,size in selected:
            raw=after[offset:offset+size]
            assert hashlib.sha256(raw).hexdigest()==digest
            hits=[m.start() for m in re.finditer(re.escape(raw),before)]
            results.append(dict(model=old['model'],version=old['version'],table_id=name,sha256=digest,offsets=hits))
    dump(DATA/'additional_cross_version.json',results)
    conversions=[]
    listings=runpy.run_path(str(ROOT/'tools/arm_static.py'))['listing']
    for model,version,file,bias,table,length in [('gr3','2.10','fwdc239b.bin.decoded',0x52FEF790,0x53289074,13),('gr4','1.11','fwdc248b.bin.decoded',0x52FE82F0,0x53374134,21)]:
        raw=pathlib.Path('/tmp/gxr_gr_firmware/unpacked',model+'-'+version,file).read_bytes()
        cases=[]
        for index in range(length):
            target=struct.unpack_from('<I',raw,table-bias+index*4)[0]
            word=struct.unpack_from('<I',raw,target-bias)[0]
            immediate=word&255 if word&0xFFFFF000==0xE3A00000 else None
            cases.append(dict(ui_value=index,jump_entry_vma=hex(table+index*4),case_vma=hex(target),first_word=hex(word),returned_internal_index=immediate))
        conversions.append(dict(model=model,version=version,jump_table_vma=hex(table),cases=cases))
        start,end=(0x536DC26C,0x536DC2C8) if model=='gr3' else (0x53925F84,0x53926008)
        (DATA/(model+'-mode-selection.asm.txt')).write_text(listings(raw,start,end,bias))
    dump(DATA/'enum_conversions.json',conversions)
    record=next(x for x in latest if x['model']=='gr4')
    blob=pathlib.Path(record['images'][0]['path']).read_bytes()
    def offset(address):
        if 0x55000000<=address<0x55057480:address=0x5437B640+address-0x55000000
        return address-0x52FE82F0
    variants=[]
    for mode,index in [('Positive Film',17),('Negative Film',24)]:
        for name,base in [('ColorMatrix',0x55053780),('MultiAxial',0x55053504),('Gamma',0x55053138)]:
            values=[struct.unpack_from('<I',blob,offset(base+4*(index+34*variant)))[0] for variant in range(3)]
            assert len(set(values))==1
            variants.append(dict(mode=mode,table=name,index=index,pointers=[hex(v) for v in values],all_equal=True))
    dump(DATA/'gr4_pointer_variants.json',variants)
    print('combined official packages',len(allrows),'indexed table blocks',len(tables))


if __name__=='__main__':main()
