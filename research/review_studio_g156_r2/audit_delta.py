"""Independently reconstruct r1 inputs and nearby variants, then call unmodified boundaries."""
from pathlib import Path
from dataclasses import asdict, replace
from types import SimpleNamespace
import ctypes as CT
import hashlib
import importlib.util
import json
import struct
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse
from gxr_studio.camdata import datcodec as dc, intake
from gxr_studio.api import camdata_routes as routes
from gxr_studio.api.errors import ApiError
from gxr_studio.config import Settings

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
STUDIO=Path('/Volumes/Workspace/Scratch/worktrees/gxr-studio/g156-codec')
sys.dont_write_bytecode=True

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def seal(raw):
    out=bytearray(raw)
    struct.pack_into('>I',out,24,dc.crc(out[256:]))
    struct.pack_into('>I',out,20,0)
    struct.pack_into('>I',out,20,dc.crc(out[:256]))
    return bytes(out)

def patch(raw,offset,value):
    out=bytearray(raw)
    struct.pack_into('>I',out,offset,value)
    return seal(out)

def empty_effect_area(length):
    # A canonical, zero-look GXFX block with a chosen size, accepted by the r1 parser.
    # This avoids conflating a four-byte layout change with an invalid GXFX length.
    align=lambda n:(n+3)&~3
    for capacity in range(49):
        for c0 in range(128):
            for c1 in range(128):
                if 32+32*capacity+align(c0*62)+align(c1*33)!=length:
                    continue
                area=bytearray(length)
                struct.pack_into('>4s6H',area,0,b'GXFX',1,32,capacity,0,32,0)
                area[16:20]=bytes((c0,c1,0,0))
                struct.pack_into('>I',area,24,dc.crc(area[32:]))
                struct.pack_into('>I',area,28,dc.crc(area[:28]))
                return bytes(area)
    raise AssertionError(('no canonical GXFX layout',length))

class RenderBoundary:
    def __init__(self):
        self.notes=[]
        self.replacements=0
    def note_import_generation(self,generation):
        self.notes.append(generation)
    def replace_data(self,operation):
        self.replacements+=1
        raise AssertionError('Rejected input reached storage replacement')

def main():
    assert Path(dc.__file__).resolve()==STUDIO/'src/gxr_studio/camdata/datcodec.py'
    old=load('r2_old_codec',HERE/'old_datcodec.py')
    D=load('dat_format',ROOT/'research/v39_g153/dat_format.py')
    formatter=load('r2_parent_format',ROOT/'research/v39_g153/format_checks.py')
    formatter.PRODUCT=ROOT/'firmware/engine_v68_g156/candidate/containers/product'
    formatter.HERE=HERE
    formatter.TMP=HERE/'tmp/parent-c-gate'
    gate=formatter.library()
    elf_reader=load('r2_elf_reader',ROOT/'firmware/stage2l_switch/tools/build.py')

    def c_gate(raw):
        return [gate.check_dat(CT.create_string_buffer(raw),len(raw),CT.create_string_buffer(formatter.trust(raw)),unit) for unit in range(3)]

    # A nonexistent, repository-external home is checked but never created or written.
    # No validation or privacy function is patched. A storage call is an assertion failure.
    home=Path('/private/tmp/projectricoh-g156-r2-no-write-6a50c77a')
    assert not home.exists()
    render=RenderBoundary()
    context=SimpleNamespace(settings=Settings(home_dir=home,library_dir=HERE/'tmp/library',
                export_dir=HERE/'tmp/export',volumes_roots=()),reader=None,
                sessions=SimpleNamespace(attach_all=lambda cards: []),render=render)
    app=FastAPI()
    app.state.ctx=context
    app.include_router(routes.router)
    @app.exception_handler(ApiError)
    async def api_error(_request,error):
        return JSONResponse(status_code=error.status,content={'error':error.code,'message':error.message,'extra':error.extra})

    packages={}
    roundtrips=[]
    registration=[]
    edits=[]
    for name in ('g156','g156_test','g155c','g155c_test'):
        raw=(ROOT/f'firmware/package_v310_{name}/GXRCE.DAT').read_bytes()
        dat=dc.parse(raw)
        assert dc.pack(dat)==raw
        assert old.pack(old.parse(raw))==raw
        assert intake.inspect_dat(raw).generation==dat.generation
        packages[name]=(raw,dat)
        roundtrips.append(dict(package=name,sha256=sha(raw),bytes=len(raw),generation=dat.generation,roundtrip=True))
        if dat.generation!=156:
            continue
        build='boot-on' if name.endswith('_test') else 'boot-off'
        folder=ROOT/'firmware/engine_v68_g156/candidate/local'/build
        elf_path=folder/'engine.elf'
        elf=elf_reader.Elf(elf_path)
        code=next(s for s in elf.sections if s['name']=='.engine')
        bss=next(s for s in elf.sections if s['name']=='.bss')
        assert elf.content(code)==dat.engine
        rel=(folder/'reloc.bin').read_bytes()
        relocations=tuple(struct.iter_unpack('>II',rel))
        description=dc.EngineDescription(sha(dat.engine),dat.entry,dat.bss,tuple(dat.relocations),len(raw))
        assert description in dc.G156_ENGINES
        assert bss['va']==len(raw) and bss['size']==dat.bss
        assert relocations==tuple(dat.relocations)
        assert elf.entry==elf.symbols['ig_bootstrap']['value']==dat.entry
        registration.append(dict(package=name,description=asdict(description),elf_sha256=sha(elf_path.read_bytes()),
                                 reloc_sha256=sha(rel),elf_engine_equal=True,elf_entry_equal=True,elf_bss_equal=True))
        assert c_gate(raw)==[0,0,0]
        for count in (0,1,30):
            users=[{'base':5,'levels':[1]+[0]*10} for _ in range(count)]
            output=dc.pack(dc.replace_users(dat,users))
            assert dc.parse(output).users==users
            assert intake.inspect_dat(output).generation==156
            assert c_gate(output)==[0,0,0]
            ext=D.sections(raw)[6][0]+dc.LEGACY_BYTES
            assert output[:20]==raw[:20] and output[28:ext]==raw[28:ext]
            assert output[ext+dc.EXT_BYTES:]==raw[ext+dc.EXT_BYTES:]
            path=HERE/'tmp'/f'{name}-users-{count}.dat'
            path.write_bytes(output)
            edits.append(dict(package=name,count=count,sha256=sha(output),bytes=len(output),
                              c_gate=[0,0,0],only_gxui_and_outer_crc_changed=True))

    previous=json.loads((ROOT/'research/review_studio_g156_r1/evidence/dat-audit.json').read_text())
    previous_hashes={r['case']:r.get('sha256') for r in previous['mixed_files']}
    cases=[]
    for name in ('g155c','g155c_test'):
        raw,dat=packages[name]
        target='g156_test' if name.endswith('_test') else 'g156'
        _new_raw,new=packages[target]
        model=replace(dat,generation=156)
        changed=patch(raw,28,156)
        assert sha(changed)==previous_hashes[name+'-only-outer156']
        assert [i for i,(a,b) in enumerate(zip(raw,changed)) if a!=b]==[20,21,22,23,31]
        cases.append((name+'-only-outer156',model,changed))
        model=replace(dat,generation=156,engine=new.engine,relocations=new.relocations,entry=new.entry,bss=new.bss)
        changed=old.pack(model)
        assert sha(changed)==previous_hashes[name+'-with-real-g156-engine']
        cases.append((name+'-with-real-g156-engine',model,changed))

    for name in ('g156','g156_test'):
        raw,dat=packages[name]
        # Same engine length, with first, middle, and final bytes independently changed.
        for position in (0,len(dat.engine)//2,len(dat.engine)-1):
            engine=bytearray(dat.engine)
            engine[position]^=1
            model=replace(dat,engine=bytes(engine))
            cases.append((f'{name}-engine-byte-{position}',model,old.pack(model)))
        for step in (-4,4):
            model=replace(dat,bss=dat.bss+step)
            cases.append((f'{name}-bss-{step:+}',model,old.pack(model)))
            model=replace(dat,entry=dat.entry+step)
            cases.append((f'{name}-entry-{step:+}',model,old.pack(model)))
        p,t=dat.relocations[0]
        model=replace(dat,relocations=[(p,t+4),*dat.relocations[1:]])
        # Pack does not run the parse-only image binding check, so this isolates its registry check.
        cases.append((f'{name}-relocation-target',model,old.pack(model)))
        engine=bytearray(dat.engine)
        struct.pack_into('>I',engine,p-256,t+4)
        model=replace(model,engine=bytes(engine))
        cases.append((f'{name}-relocation-and-image',model,old.pack(model)))
        model=replace(dat,relocations=[])
        cases.append((f'{name}-relocation-removed',model,old.pack(model)))
        q,u=next((q,struct.unpack_from('>I',raw,q)[0])
                 for q in range(256,256+len(dat.engine)-3,4)
                 if q!=p and 256<=struct.unpack_from('>I',raw,q)[0]<len(raw)+dat.bss)
        model=replace(dat,relocations=[(q,u)])
        changed=old.pack(model)
        assert old.parse(changed).engine==dat.engine and len(changed)==len(raw)
        cases.append((f'{name}-relocation-valid-image-same-size',model,changed))
        for step in (-4,4):
            area=empty_effect_area(len(dat.effect_area)+step)
            model=replace(dat,effect_area=area,looks=())
            # Retain the engine and all registered metadata while shifting the data end by four.
            changed=old.pack(model)
            assert len(changed)==len(raw)+step and model.engine==dat.engine
            assert old.pack(old.parse(changed))==changed
            cases.append((f'{name}-data-end-{step:+}',model,changed))

    rejection_rows=[]
    output_dir=HERE/'tmp/counterexamples'
    output_dir.mkdir(parents=True,exist_ok=True)
    with TestClient(app) as client:
        for label,model,raw in cases:
            row=dict(case=label,sha256=sha(raw),bytes=len(raw),paths={})
            (output_dir/(label+'.dat')).write_bytes(raw)
            if label in previous_hashes or label.endswith(('data-end--4','data-end-+4','relocation-valid-image-same-size')):
                assert old.pack(old.parse(raw))==raw
                row['old_parser_accepts_canonical_roundtrip']=True
            row['engine_sha256']=sha(model.engine)
            row['entry']=model.entry
            row['bss']=model.bss
            row['relocations']=model.relocations
            for name,call,kind in (
                ('parse',lambda:dc.parse(raw),dc.DatError),
                ('pack',lambda:dc.pack(model),dc.DatError),
                ('inspect_dat',lambda:intake.inspect_dat(raw),intake.IntakeError),
                ('_install',lambda:routes._install(context,raw,'GXRCE.DAT',{'kind':'file'}),ApiError)):
                try:
                    call()
                except kind as error:
                    if name in ('inspect_dat','_install'):
                        assert error.status==422 and error.code=='dat_invalid'
                    row['paths'][name]=dict(rejected=True,message=str(error),code=getattr(error,'code',None))
                else:
                    raise AssertionError((label,name,'accepted'))
            response=client.post('/api/camdata/import-upload',content=raw)
            assert response.status_code==422 and response.json()['error']=='dat_invalid'
            row['paths']['http-upload']=dict(status=422,code=response.json()['error'])
            assert render.replacements==0 and not home.exists()
            rejection_rows.append(row)

    # Compare old/new behavior on every other registered generation, using actual DATs.
    names={127:'package_v36_g127/local/SD_ROOT',129:'package_v36_g129/local/SD_ROOT',
           131:'package_v36_g131/local/SD_ROOT',135:'package_v37_g135/local/SD_ROOT',
           137:'package_v38_g137/local/SD_ROOT',138:'package_v38_g138/SD_ROOT',
           150:'package_v38_g150',152:'package_v38_g152',153:'package_v39_g153',
           154:'package_v39_g154',155:'package_v310_g155c'}
    older=[]
    for generation,folder in names.items():
        base=ROOT/'firmware'/folder
        path=next(p for p in (base/'GXRCE.DAT',base/'SD_ROOT/GXRCE.DAT',base/'local/SD_ROOT/GXRCE.DAT') if p.is_file())
        raw=path.read_bytes()
        before,after=old.parse(raw),dc.parse(raw)
        assert asdict(old.PROFILES[generation])==asdict(dc.PROFILES[generation])
        assert old.pack(before)==dc.pack(after)==raw
        assert intake.inspect_dat(raw).generation==generation
        for users in ([],[{'base':5,'levels':[1]+[0]*10}]):
            assert old.pack(old.replace_users(before,users))==dc.pack(dc.replace_users(after,users))
        negatives=[]
        for unit in range(3):
            out=bytearray(raw)
            at=D.u32(raw,D.sections(raw)[2][0]+64*unit+16)
            struct.pack_into('>I',out,at+16,156 if generation==155 else 155)
            struct.pack_into('>I',out,at+28,dc.crc(out[at:at+28]))
            for codec in (old,dc):
                try:codec.parse(seal(out))
                except codec.DatError as error:
                    assert str(error)=='配方库头、CRC 或代数不合格'
                else:raise AssertionError((generation,unit,'wrong bank accepted'))
            negatives.append(unit)
        older.append(dict(generation=generation,path=str(path),sha256=sha(raw),roundtrip=True,
                          user_edit_bytes_unchanged=True,rejected_wrong_banks=negatives,profile_equal=True))

    result=dict(status='PASS',head='6a50c77a8ba04c45ada308a1cbc28074a79116fb',
                real_packages=roundtrips,engine_registration=registration,user_edits=edits,
                rejected_cases=rejection_rows,other_generations=older,
                install_layer='Unmodified _guard_home, inspect_dat, _install and upload route; synthetic context; zero storage calls',
                install_home_created=home.exists(),storage_replacements=render.replacements)
    (HERE/'evidence/delta-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='PASS',real_roundtrips=len(roundtrips),registered_engines=len(registration),
                          legitimate_edits=len(edits),rejected_files=len(rejection_rows),
                          rejection_paths_per_file=5,other_generations=len(older)),ensure_ascii=False))

if __name__=='__main__':
    main()
