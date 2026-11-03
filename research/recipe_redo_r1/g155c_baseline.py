"""Read and freeze the actual g155c records; count rows without building a DAT."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import struct

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PRIVATE=HERE/'local/g155c_baseline'
UNITS=('a12-50','a12-28','mount-a12')
BUILTINS=('01 GRPos','02 GRNeg','03 HC BW','04 Std','05 F-CC','06 F-CN','07 L-Chr','08 L-Viv')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):return json.loads(Path(path).read_text())


def dump(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def decoder():
    spec=importlib.util.spec_from_file_location('recipe_g155c_reader',PRIVATE/'dat_format.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def freeze():
    PRIVATE.mkdir(exist_ok=False)
    source=ROOT/'research/v39_g153/dat_format.py'
    shutil.copyfile(source,PRIVATE/'dat_format.py')
    D=decoder();receipts=[];all_records={}
    for profile in ('release','test'):
        package=ROOT/('firmware/package_v310_g155c'+('_test' if profile=='test' else ''))/'GXRCE.DAT'
        maps=ROOT/'research/g156/evidence'/('r2-maps-'+profile+'.json')
        if not maps.exists():maps=ROOT/'research/g156/local/round1/evidence'/('maps-'+profile+'.json')
        raw=package.read_bytes();D.sections(raw);D.strict_effects(raw)
        (PRIVATE/(profile+'.source.dat')).write_bytes(raw)
        shutil.copyfile(maps,PRIVATE/(profile+'.maps.json'))
        mapping=read(maps)['before'];area,_=D.effect_area(raw)
        effects=[]
        for index in range(D.u16(raw,area+10)):
            entry=raw[area+32+32*index:area+64+32*index]
            effects.append((entry[20:32].split(b'\0')[0].decode(),entry[18],D.expand_effect(raw,index)))
        records={}
        for ui,unit in enumerate(UNITS):
            rows=[]
            for slot,name in enumerate(BUILTINS,1):
                rows.append((name,'builtin',slot,D.expand(raw,ui,slot)))
            rows += [(name,'look',ordinal+1,entry) for ordinal,(name,mask,entry) in
                     enumerate((r for r in effects if r[1]&(1<<ui)))]
            assert sum(kind=='look' for name,kind,slot,entry in rows)==10
            base_flags=rows[4][3][1];assert base_flags==1
            unit_rows=[]
            for name,kind,slot,entry in rows:
                evidence=next(r for r in mapping[unit] if r['kind']==kind and r['slot']==slot)
                digest=hashlib.sha256(entry).hexdigest();assert evidence['name']==name and evidence['sha256']==digest
                if kind=='look':assert entry[1]==base_flags
                filename=PRIVATE/'records'/profile/unit/(f'{kind}_{slot:02d}.record552')
                filename.parent.mkdir(parents=True,exist_ok=True);filename.write_bytes(entry)
                unit_rows.append(dict(name=name,kind=kind,slot=slot,record_file=str(filename.relative_to(HERE)),
                                      record_sha256=digest,flags=entry[1],base05_flags=base_flags))
            records[unit]=unit_rows
        all_records[profile]=records
        receipts.append(dict(profile=profile,source=str(package.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest(),
            maps_source=str(maps.relative_to(ROOT)),maps_sha256=sha(maps),DAT_bytes=len(raw),BSS_bytes=D.u32(raw,116),
            shared_table_bytes=D.u32(raw,196),generation=D.u32(raw,28)))
    assert [[r['record_sha256'] for r in all_records['release'][u]] for u in UNITS]==[
        [r['record_sha256'] for r in all_records['test'][u]] for u in UNITS]
    dump(PRIVATE/'manifest.json',dict(profiles=receipts,records=all_records,reader_source=str(source.relative_to(ROOT)),
        reader_sha256=sha(source),published_looks_per_unit=10,no_DAT_built=True))
    dump(HERE/'g155c_baseline_summary.json',dict(published_looks_per_unit=10,units={u:[r for r in all_records['release'][u] if r['kind']=='look'] for u in UNITS},
        sources=receipts,manifest_sha256=sha(PRIVATE/'manifest.json'),no_DAT_built=True))
    print('Frozen g155c:',len(all_records['release']),'units,10 published Looks each; flags1; no DAT written')


def records():
    return read(PRIVATE/'manifest.json')['records']['release']


def table_cost(replacements):
    """The g156 row-deduplication rules, with no serialized DAT output."""
    D=decoder();base=records();pools=[[] for _ in D.LENGTHS];extras=[[] for _ in D.LENGTHS]
    def rows(entry,effect):
        for kind,offset in zip(D.KINDS,D.OFFSETS):
            row=entry[offset:offset+D.LENGTHS[kind]]
            if row in pools[kind]:continue
            target=extras[kind] if effect else pools[kind]
            if row not in target:target.append(row)
    for unit in UNITS:
        for item in base[unit]:
            if item['kind']=='builtin':rows(replacements.get((unit,item['name']),HERE/item['record_file']).read_bytes(),False)
    labels=[r['name'] for r in base[UNITS[0]] if r['kind']=='look'];descriptors=0
    for label in labels:
        groups={}
        for ui,unit in enumerate(UNITS):
            item=next(r for r in base[unit] if r['kind']=='look' and r['name']==label)
            changed=(unit,label) in replacements
            entry=replacements.get((unit,label),HERE/item['record_file']).read_bytes()
            groups[(entry,changed)]=groups.get((entry,changed),0)|(1<<ui)
        for (entry,changed),mask in groups.items():
            if changed:assert struct.unpack_from('>I',entry,4)[0]==D.content_crc(entry,mask)
            rows(entry,True);descriptors+=1
    shared=80+3*176+sum(D.align4(len(p)*size) for p,size in zip(pools,D.LENGTHS))
    fx=32+32*descriptors+sum(D.align4(len(p)*size) for p,size in zip(extras,D.LENGTHS))
    manifest=read(PRIVATE/'manifest.json');packages=[]
    for p in manifest['profiles']:
        length=p['DAT_bytes']+shared+fx-p['shared_table_bytes']
        allocated=7628+D.align4(length+p['BSS_bytes'])
        packages.append(dict(profile=p['profile'],predicted_DAT_bytes=length,predicted_main_allocation_bytes=allocated,
                             limit=107612,over_limit_bytes=max(0,allocated-107612)))
    return dict(shared_row_counts=list(map(len,pools)),extra_row_counts=list(map(len,extras)),
        total_unique_rows=sum(map(len,pools))+sum(map(len,extras)),look_descriptors=descriptors,
        row_sizes=list(D.LENGTHS),data_table_bytes=shared+fx,packages=packages,
        scope='Static row and descriptor accounting only; no DAT or firmware built')


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');args=ap.parse_args()
    if args.freeze:freeze()
    else:print(json.dumps(table_cost({}),ensure_ascii=False,indent=2))
