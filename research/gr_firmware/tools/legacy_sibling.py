"""GXR / GR DIGITAL IV static format comparison; no installed tool execution."""
import csv
import hashlib
import json
import pathlib
import re
import struct

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
SCRATCH = pathlib.Path('/tmp/gxr_gr_firmware')


def sections(data):
    out = []
    for i in range(16):
        source, load, size, bss, bss_size = struct.unpack_from('>5I',data,32+20*i)
        if not (size and source+512+size<=len(data) and 0x10000000<=load<0xF0000000):
            continue
        out.append(dict(index=i,record_offset=32+20*i,file_offset=source+512,load_address=load,initialized_size=size,bss_address=bss,bss_size=bss_size))
    return out


def mapped_vma(regions, offset):
    section = next((s for s in regions if s['file_offset']<=offset<s['file_offset']+s['initialized_size']),None)
    return None if section is None else offset-section['file_offset']+section['load_address']


def references(data, regions, lower, upper):
    out = []
    for offset in range(0,min(len(data)-32,0x110000),2):
        if data[offset]&0xF0!=0xD0 or data[offset+1]!=0xC0:
            continue
        reg, high = data[offset]&15, int.from_bytes(data[offset+2:offset+4],'big')
        for at in range(offset+4,offset+24,2):
            if data[at]==0x80|reg and data[at+1]==0xE0|reg:
                addr=(high<<16)|int.from_bytes(data[at+2:at+4],'big')
                if lower<=addr<upper:
                    out.append(dict(seth_file_offset=offset,seth_vma=mapped_vma(regions,offset),or3_file_offset=at,address=addr))
    return out


def script(data):
    region, domain, address = None, None, 0
    cells, domains = {}, {}
    for line in data[512:].decode('ascii',errors='replace').splitlines():
        line=line.strip('\0\xff\r\n ')
        if re.fullmatch(r'X[0-9a-fA-F]{4}',line):region=line[1:].upper()
        elif re.fullmatch(r'UEEF[0-9]',line):domain=line
        elif re.fullmatch(r'V[0-9a-fA-F]{4}',line):address=int(line[1:],16)
        elif re.fullmatch(r'W[0-9a-fA-F]{4}',line):
            key=(region,domain)
            cells.setdefault(key,{})[address]=int(line[1:],16)
            address+=2
    results=[]
    masks=[0x780,0x1F000,0x7C0000,0x60,0x1E]
    for (region,domain),words in cells.items():
        size=max(words)+2
        memory=bytearray(b'\xff'*size)
        for at,value in words.items():memory[at:at+2]=value.to_bytes(2,'big')
        hits={hex(mask):[m.start() for m in re.finditer(re.escape(mask.to_bytes(4,'big')),memory)] for mask in masks}
        target=SCRATCH/'unpacked'/'grd4-2.30'/f'parameters-{region}-{domain}.bin'
        target.write_bytes(memory)
        results.append(dict(region=region,domain=domain,word_count=len(words),extent=size,sha256=hashlib.sha256(memory).hexdigest(),mask_occurrences=hits))
        domains[(region,domain)]=words
    return results,domains


def main():
    file=SCRATCH/'unpacked/grd4-2.30/g04firm3.bin'
    b=file.read_bytes()
    regions=sections(b)
    result=dict(model='GR DIGITAL IV',version='2.30',source_sha256=hashlib.sha256(b).hexdigest(),sections=regions,tables=[],architecture_evidence=[],mode_attribution='unresolved')
    for label,base,rows,count,fmt in [('tone-A',0x100EEC,32,31,'H'),('tone-B',0x101CC4,32,33,'B'),('color-24xu32',0xFDD4C,34,24,'I'),('color-12xu32',0xFD71C,33,12,'I')]:
        stride=count*struct.calcsize('>'+fmt)
        raw=b[base:base+rows*stride]
        values=[list(struct.unpack_from('>'+fmt*count,b,base+i*stride)) for i in range(rows)]
        record=dict(id=label,file_offset=base,vma=hex(mapped_vma(regions,base)),rows=rows,columns=count,scalar={'H':'u16BE','B':'u8','I':'u32BE'}[fmt],size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),values=values,all_monotone=all(all(a<=c for a,c in zip(v,v[1:])) for v in values),association='generic ISP bank, Positive Film / Bleach Bypass selection unresolved')
        result['tables'].append(record)
        with (ROOT/'data'/('grd4-'+label+'.csv')).open('w',newline='') as out:
            writer=csv.writer(out);writer.writerow(['row','node','value','file_offset','vma'])
            for row,vs in enumerate(values):
                for node,value in enumerate(vs):
                    offset=base+row*stride+node*struct.calcsize('>'+fmt)
                    writer.writerow([row+1,node,value,hex(offset),hex(mapped_vma(regions,offset))])
    result['references']=references(b,regions,0x2014ECEC,0x20150200)
    result['references']=[r for r in result['references'] if r['address'] in (0x2014ECEC,0x2014FAC4,0x2014FEE4,0x2014FF05)]
    for offset,note in [(0xDFE34,'cmpi r0,#33: bank A accepts IDs 1..32'),(0xDFE48,'ldi r1,#62; mul r0,r1: 31 x u16 row stride'),(0xDFECC,'cmpi r5,#33: bank B accepts IDs 1..32'),(0xDFE1C,'push r8; push r9: M32R packer prologue matching GXR'),(0xDFE50,'or3 r1,r1,#0xecec follows seth r1,#0x2014'),(0xDC104,'cmpi r0,#35: 24xu32 bank accepts IDs 1..34'),(0xDC134,'slli r4,#24; ldi r0,#96: 24xu32 row size'),(0xDC148,'or3 r1,r1,#0xbb4c follows seth r1,#0x2014'),(0xDC168,'cmpi r0,#34: 12xu32 bank accepts IDs 1..33')]:
        result['architecture_evidence'].append(dict(file_offset=hex(offset),vma=hex(mapped_vma(regions,offset)),bytes=b[offset:offset+4].hex(),interpretation=note))
    for addr in [0xF0349000,0xF034C080]:
        matches=[m.start() for m in re.finditer(re.escape(struct.pack('>I',addr)),b)]
        result.setdefault('isp_register_descriptors',[]).append(dict(register=hex(addr),offsets=[hex(p) for p in matches]))
    params=SCRATCH/'unpacked/grd4-2.30/g04firm8.bin'
    result['parameter_script'],domains=script(params.read_bytes())
    # The exact known GXR table rows provide structural evidence, not mode labels.
    gxr=(PROJECT/'artifacts/firmware/gxr-1.51/jlaunch3').read_bytes()
    result['gxr_reference_sha256']=hashlib.sha256(gxr).hexdigest()
    comparisons=[]
    for bank,base,rows,size in [('color-24xu32',0xE17D4,29,96),('tone-A',0xE460C,22,62),('tone-B',0xE5178,22,33)]:
        for row in range(rows):
            raw=gxr[base+row*size:base+(row+1)*size]
            informative=len(set(raw))>2
            hits=[m.start() for m in re.finditer(re.escape(raw),b)] if informative else []
            comparisons.append(dict(bank=bank,gxr_row=row+1,gxr_file_offset=hex(base+row*size),sha256=hashlib.sha256(raw).hexdigest(),informative_pattern=informative,grd4_file_offsets=[hex(p) for p in hits]))
    result['gxr_exact_row_matches']=comparisons
    (ROOT/'data/grd4-sibling.json').write_text(json.dumps(result,indent=2)+'\n')
    print('GR DIGITAL IV banks',[(t['id'],t['rows'],t['columns']) for t in result['tables']])
    print('script domains',result['parameter_script'])
    print('matched color rows',sum(bool(r['grd4_file_offsets']) for r in comparisons if r['bank']=='color-24xu32'))


if __name__=='__main__':main()
