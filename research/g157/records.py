"""One manifest replaces recipe bytes without changing or recompiling engine logic."""
from pathlib import Path
import argparse
import json
import struct
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import common as C
D=C.D
def frozen(path): return (C.LOCAL/'inputs'/path).read_bytes()
def parse(raw):
    D.sections(raw)
    slots=[{s:D.expand(raw,u,s) for s in range(1,9)} for u in range(3)]
    looks=[{} for _ in range(3)];a,_=D.effect_area(raw)
    for i in range(D.u16(raw,a+10)):
        entry=raw[a+32+32*i:a+64+32*i]
        name=entry[20:].split(b'\0')[0].decode()
        for u in range(3):
            if entry[18]>>u&1:looks[u][name]=D.expand_effect(raw,i)
    return slots,looks
def initialize():
    release=frozen(Path('firmware/package_v310_g156/GXRCE.DAT'))
    test=frozen(Path('firmware/package_v310_g156_test/GXRCE.DAT'))
    old=frozen(Path('firmware/package_v39_g154_looks18_test/local/SD_ROOT/GXRCE.DAT'))
    slots,looks=parse(release);ts,tl=parse(test);_,ol=parse(old)
    origins=[{('builtin',str(s)):'g156 release' for s in range(1,9)} for _ in range(3)]
    for u in range(3):origins[u].update({('look',n):'g156 release' for n in looks[u]})
    slots[0][3]=ts[0][3];looks[0]['Tri-X 400']=tl[0]['Tri-X 400']
    origins[0]['builtin','3']=origins[0]['look','Tri-X 400']='g156 test compatible HC BW/Tri-X pair'
    for u in range(3):
        for n in C.RESTORE:looks[u][n]=ol[u][n];origins[u]['look',n]='G154L full legacy record'
    handoff=json.loads(frozen(Path('research/library_28mm_r1/local/g157_handoff.json')))
    selected=[r for r in handoff['profiles'] if r['accepted']]
    assert {r['name'] for r in selected}=={'HNCS LowSat','01 GRPos','06 F-CN','08 L-Viv'}
    exact=set()
    for row in selected:
        rel=Path(row['record_file']).relative_to(C.ROOT)
        raw=frozen(rel);assert C.sha(raw)==row['record_sha256']
        if row['name']=='HNCS LowSat':looks[1][row['name']]=raw;kind,key='look',row['name'];exact.add((1,key))
        else:kind,key='builtin',row['name'][:2];slots[1][int(key)]=raw;key=str(int(key))
        origins[1][kind,key]='library_28mm_r1 reference-exact frozen handoff'
    manifest=dict(schema='g157-record-manifest/1',generation=157,units=[],users_source='firmware/package_v310_g156_test/GXRCE.DAT',
        base='firmware/package_v310_g156/GXRCE.DAT',tradeoff='50mm HC BW and Tri-X use g156 test; keep three other release-only improvements and 50mm Metropolis')
    for u in range(3):
        unit=dict(unit=C.UNITS[u],builtins=[],looks=[])
        for kind,rows in (('builtin',slots[u].items()),('look',looks[u].items())):
            for key,raw in rows:
                digest=C.sha(raw);dest=C.LOCAL/'records'/(digest+'.bin');dest.parent.mkdir(exist_ok=True);dest.write_bytes(raw)
                entry=dict(slot=key) if kind=='builtin' else dict(name=key,exact_identity=(u,key) in exact)
                entry.update(file=str(dest.relative_to(C.ROOT)),sha256=digest,source=origins[u][kind,str(key)])
                unit['builtins' if kind=='builtin' else 'looks'].append(entry)
        manifest['units'].append(unit)
    C.save(C.LOCAL/'records.json',manifest)
    return manifest
def read_manifest(path):
    manifest=json.loads(Path(path).read_text())
    assert manifest['schema']=='g157-record-manifest/1' and manifest['generation']==157
    slots=[];looks=[]
    for u,unit in enumerate(manifest['units']):
        assert unit['unit']==C.UNITS[u]
        def record(row):
            p=C.ROOT/row['file'];raw=p.read_bytes()
            assert len(raw)==552 and C.sha(raw)==row['sha256'] and D.refresh_entry(raw)==raw,p
            return raw
        base={r['slot']:record(r) for r in unit['builtins']}
        assert set(base)==set(range(1,9))
        assert all(raw[0]==s for s,raw in base.items())
        assert base[4]==D.expand(frozen(Path(manifest['base'])),u,4)
        names=[r['name'] for r in unit['looks']]
        assert len(names)==18 and len(set(names))==18 and set(C.RESTORE)<=set(names) and 'Metropolis' in names
        fx=[(r['name'],record(r),r.get('exact_identity',False)) for r in unit['looks']]
        assert all(raw[0] in base and raw[0]!=4 and raw[1]==base[raw[0]][1] for _,raw,_ in fx)
        assert all(raw[1]==base[5][1] for _,raw,_ in fx)
        for row in unit['looks']:
            required=row.get('requires',{})
            assert set(required)<=set(('builtins','looks'))
            for slot,digest in required.get('builtins',{}).items():
                assert int(slot) in base and C.sha(base[int(slot)])==digest, 'dependency: '+unit['unit']+' '+row['name']+' slot '+slot
            for name,digest in required.get('looks',{}).items():
                peer=next((r for r in unit['looks'] if r['name']==name),None)
                assert peer and peer['sha256']==digest, 'dependency: '+unit['unit']+' '+row['name']+' Look '+name
        slots.append(base);looks.append(fx)
    assert len(slots)==3
    return manifest,slots,looks
def serialize(path):
    manifest,slots,looks=read_manifest(path)
    raw=frozen(Path(manifest['base']));test=frozen(Path(manifest['users_source']))
    pools=[[] for _ in D.LENGTHS];extras=[[] for _ in D.LENGTHS]
    def refs(record,effect=False):
        out=[]
        for k,o in zip(D.KINDS,D.OFFSETS):
            row=record[o:o+D.LENGTHS[k]]
            if row in pools[k]:index=pools[k].index(row);assert not effect or index<128
            elif effect:
                if row not in extras[k]:extras[k].append(row)
                index=128+extras[k].index(row)
            else:pools[k].append(row);index=len(pools[k])-1
            assert index<256;out.append(index)
        return bytes(out)
    tables=[]
    for u,base in enumerate(slots):
        directory=D.u32(raw,156)+64*u;at=D.u32(raw,directory+20);count=raw[directory+30]
        entries=bytearray()
        for i in range(count):
            record=base[raw[at+16+20*i]]
            entries+=record[:2]+record[445:447]+record[4:8]+refs(record)+bytes(2)
        header=bytearray(raw[at:at+16]);struct.pack_into('>I',header,12,D.crc(entries));tables.append(header+entries)
    labels=list(dict.fromkeys(n for rows in looks for n,_,_ in rows));descriptors=[];packed=bytearray()
    for name in labels:
        groups={}
        for u,rows in enumerate(looks):
            _,record,exact=next(r for r in rows if r[0]==name)
            key=(record if exact else record[:4]+record[8:],exact)
            group=groups.setdefault(key,dict(record=record,mask=0,exact=exact));group['mask']|=1<<u
        for group in groups.values():
            record=bytearray(group['record']);mask=group['mask'];struct.pack_into('>I',record,4,D.content_crc(record,mask))
            assert not group['exact'] or record==group['record']
            label=name.encode('ascii');assert 1<=len(label)<=12
            packed+=record[:2]+record[445:447]+record[4:8]+refs(record,True)+bytes((mask,0))+label+bytes(12-len(label))
            descriptors.append(dict(name=name,mask=mask,index=len(descriptors),sha256=C.sha(record),record_code=64+len(descriptors)))
    assert len(descriptors)<=48
    fx=bytearray(32)+packed
    for pool,size in zip(extras,D.LENGTHS):
        assert len(pool)<=127;data=b''.join(pool);fx+=data+bytes(D.align4(len(data))-len(data))
    struct.pack_into('>4s6H',fx,0,b'GXFX',1,32,len(descriptors),len(descriptors),32,0)
    fx[16:20]=fx[20:24]=bytes(map(len,extras));struct.pack_into('>II',fx,24,D.crc(fx[32:]),0);struct.pack_into('>I',fx,28,D.crc(fx[:28]))
    start=D.u32(raw,192);shared=bytearray(raw[start:start+80]);table_offsets=[]
    for table in tables:table_offsets.append(start+len(shared));shared+=table
    for k,(pool,size) in enumerate(zip(pools,D.LENGTHS)):
        assert len(pool)<=(144,240,48,48)[k]
        data=b''.join(pool);struct.pack_into('>HHII',shared,16+12*k,len(pool),size,len(shared),D.crc(data));shared+=data+bytes(D.align4(len(data))-len(data))
    struct.pack_into('>II',shared,64,len(shared),len(fx));shared+=fx;struct.pack_into('>I',shared,8,len(shared))
    out=bytearray(raw[:start])+shared+raw[D.u32(raw,204):];delta=len(out)-len(raw)
    struct.pack_into('>I',out,16,len(out));struct.pack_into('>I',out,28,157);struct.pack_into('>I',out,196,len(shared));struct.pack_into('>I',out,204,D.u32(raw,204)+delta)
    for u,table in enumerate(table_offsets):
        directory=D.u32(raw,156)+64*u
        struct.pack_into('>II',out,directory+20,table,D.u32(raw,directory+24)+delta)
        bank=D.u32(out,directory+16);struct.pack_into('>I',out,bank+16,157);struct.pack_into('>I',out,bank+28,D.crc(out[bank:bank+28]))
    # Preserve the three existing test users, full UI extension and knob tables.
    at=D.u32(out,204)+1408;old=D.u32(test,204)+1408;out[at:at+1984]=test[old:old+1984]
    out=D.seal(out);D.sections(out);D.strict_effects(out)
    assert len(labels)==18
    for u in range(3):
        assert sum(r['mask']>>u&1 for r in descriptors)==18
        for s in range(1,9):assert D.expand(out,u,s)==slots[u][s]
    C.save(C.LOCAL/'packing.json',dict(descriptors=descriptors,base_rows=list(map(len,pools)),extra_rows=list(map(len,extras)),shared_bytes=len(shared),manifest_sha256=C.sha(Path(path).read_bytes()),data_bytes=len(out)-256-D.u32(out,136)-D.u32(out,148)))
    return out
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--init',action='store_true');p.add_argument('--manifest',type=Path,default=C.LOCAL/'records.json');a=p.parse_args()
    C.setup();C.compute_gate('records')
    if a.init:initialize()
    raw=serialize(a.manifest);(C.LOCAL/'data-template.DAT').write_bytes(raw)
    print(json.dumps(dict(template_bytes=len(raw),generation=157,descriptors=D.strict_effects(raw)['count'],looks_per_unit=18)))
