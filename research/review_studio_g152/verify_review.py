"""Independent review checks; records hashes and observable results, never table bytes."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import random
import shutil
import struct
import subprocess
import sys
from dataclasses import replace

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
STUDIO=PROJECT/'studio'
SCRATCH=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-g152-r1')
sys.path.insert(0,str(STUDIO/'tests'))

def sha(b): return hashlib.sha256(b).hexdigest()
def tree(root): return {str(p.relative_to(root)):sha(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file()}
def save(name, value):
    (HERE/(name+'.json')).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(value,ensure_ascii=False),flush=True)

def reseal(raw):
    from gxr_studio.camdata import datcodec as dc
    b=bytearray(raw)
    struct.pack_into('>I',b,24,dc.crc(b[256:]))
    struct.pack_into('>I',b,20,0)
    struct.pack_into('>I',b,20,dc.crc(b[:256]))
    return bytes(b)

def portable():
    folder=SCRATCH/'portable/project/studio'
    folder.mkdir(parents=True,exist_ok=True)
    for name in ('src','tests','web'):
        shutil.copytree(STUDIO/name,folder/name,ignore=shutil.ignore_patterns('__pycache__'),dirs_exist_ok=True)
    shutil.copy2(STUDIO/'pyproject.toml',folder/'pyproject.toml')
    assert not (folder.parent/'firmware').exists()
    script=folder/'run_portable.py'
    script.write_text("import sys\nfrom pathlib import Path\np=Path(__file__).resolve().parent\nsys.path.insert(0,str(p/'src'))\nsys.path.insert(0,str(p/'tests'))\nimport g152_support\nassert g152_support.ROOT == p.parent\nassert not (g152_support.ROOT/'firmware').exists()\nimport gxr_studio\nassert str(gxr_studio.__file__).startswith(str(p/'src'))\nimport pytest\nraise SystemExit(pytest.main(['-q','tests/test_g152.py','--force-reruns','0','--basetemp',str(p.parents[2]/'pytest-portable'),'--junitxml',"+repr(str(HERE/'pytest-portable.xml'))+"]))\n")
    done=subprocess.run([sys.executable,'-I','-B',str(script)],cwd=folder,timeout=180)
    assert done.returncode==0,done.returncode
    import xml.etree.ElementTree as ET
    cases=list(ET.parse(HERE/'pytest-portable.xml').getroot().iter('testcase'))
    result={'tests':len(cases),'passed':sum(c.find('skipped') is None and c.find('failure') is None and c.find('error') is None for c in cases),
            'skipped':sum(c.find('skipped') is not None for c in cases),'failed':sum(c.find('failure') is not None or c.find('error') is not None for c in cases),
            'firmware_absent':not (folder.parent/'firmware').exists(),'source_loaded_from_copy':True}
    assert result['passed']==8 and result['skipped']==255 and result['failed']==0,result
    save('portable-result',result)

def equality():
    from g152_support import dat_path, CameraReference, UNITS
    from gxr_studio.camdata import datcodec as dc, store
    from gxr_studio.render.params import RecipeSel
    from gxr_studio.render.recipes import CameraData
    from gxr_studio.engine import menu
    input_paths=set()
    for gen,version in ((152,60),(153,62)):
        core=PROJECT/f'firmware/engine_v{version}_g{gen}/candidate'
        input_paths.update(p for p in core.rglob('*') if p.is_file() and p.suffix in ('.c','.h'))
        input_paths.update(dat_path(gen,test) for test in (False,True))
    before={str(p.relative_to(PROJECT)):sha(p.read_bytes()) for p in sorted(input_paths)}
    rows=[]
    for gen in (152,153):
        ref=CameraReference(gen,SCRATCH/f'independent-reference-{gen}')
        for test in (False,True):
            raw=dat_path(gen,test).read_bytes()
            assert dc.pack(dc.parse(raw))==raw
            home=SCRATCH/f'compare-{gen}-{test}'
            store.import_from_dat(raw,home)
            cam=CameraData(home)
            assert cam.menu==menu.load()
            for unit,name in enumerate(UNITS):
                for index in (2,8):
                    item=cam.listing()[unit]['looks'][index]
                    sel=RecipeSel(name,item['slot'],kind='look',id=item['id'])
                    controls=item['controls']
                    cases=[{}, {c['name']:c['levels'][(len(c['levels'])-1)//3] for c in controls},
                              {c['name']:c['levels'][-1 if i%2==0 else 0] for i,c in enumerate(controls)}]
                    for values in cases:
                        actual=cam.resolve(replace(sel,levels=tuple(values.items()))).entry
                        expected=ref.resolve(raw,unit,index,values)
                        assert actual==expected,(gen,test,name,index,values)
                        rows.append({'generation':gen,'test':test,'unit':name,'look':item['name'],'levels':values,
                                     'length':len(actual),'studio_sha256':sha(actual),'camera_sha256':sha(expected),'equal':True})
            if gen==152 and test:
                (SCRATCH/'ui_catalog.json').write_text(json.dumps({'units':cam.listing()}))
                from gxr_studio.finish.catalog import frames_document
                (SCRATCH/'ui_frames.json').write_text(json.dumps(frames_document()))
    after={str(p.relative_to(PROJECT)):sha(p.read_bytes()) for p in sorted(input_paths)}
    assert before==after
    save('independent-equality',{'comparisons':len(rows),'inputs_unchanged':True,'inputs':before,'rows':rows})

def old_generations():
    import e0_support
    from gxr_studio.camdata import datcodec as dc, store
    from gxr_studio.render.params import RecipeSel
    from gxr_studio.render.recipes import CameraData, UNIT_INFO
    def baseline(module_path, name):
        text=subprocess.check_output(['git','--no-optional-locks','show','HEAD:'+module_path],cwd=STUDIO)
        path=SCRATCH/(name.rsplit('.',1)[-1]+'.py')
        path.write_bytes(text)
        spec=importlib.util.spec_from_file_location(name,path)
        mod=importlib.util.module_from_spec(spec)
        sys.modules[name]=mod
        spec.loader.exec_module(mod)
        return mod
    old_dc=baseline('src/gxr_studio/camdata/datcodec.py','review_base_datcodec')
    old_recipes=baseline('src/gxr_studio/render/recipes.py','gxr_studio.render.review_base_recipes')
    paths={**e0_support.FIXTURE_DATS,137:PROJECT/'firmware/package_v38_g137/local/SD_ROOT/GXRCE.DAT',
           138:PROJECT/'firmware/package_v38_g138/SD_ROOT/GXRCE.DAT'}
    results=[]
    for gen,path in paths.items():
        raw=path.read_bytes()
        previous,current=old_dc.parse(raw),dc.parse(raw)
        assert old_dc.pack(previous)==dc.pack(current)==raw
        for field in ('generation','flags','entry','bss','resident_id','abi_id','engine','relocations','ids','ext_config','users','kv2_block'):
            assert getattr(previous,field)==getattr(current,field),(gen,field)
        for earlier_module,later_module in zip(previous.modules,current.modules):
            assert vars(earlier_module)==vars(later_module),(gen,'module')
        for unit in range(3):
            for slot in range(1,17): assert previous.entry_of(unit,slot)==current.entry_of(unit,slot)
        home=SCRATCH/f'old-{gen}'
        store.import_from_dat(raw,home)
        earlier,later=old_recipes.CameraData(home),CameraData(home)
        assert earlier.menu==later.menu
        listing=[{k:v for k,v in u.items() if k not in ('looks','users')} for u in later.listing()]
        assert earlier.listing()==listing
        comparisons=0
        for unit,unit_info in enumerate(UNIT_INFO):
            for slot in range(1,9):
                sel=RecipeSel(unit_info['id'],slot)
                cases=[{}]
                for c in later.controls(unit,slot): cases.extend(({c['name']:c['levels'][0]},{c['name']:c['levels'][-1]}))
                for values in cases:
                    chosen=replace(sel,levels=tuple(values.items()))
                    assert earlier.resolve(chosen).entry==later.resolve(chosen).entry,(gen,unit,slot,values)
                    comparisons+=1
        results.append({'generation':gen,'sha256':sha(raw),'round_trip':True,'all_48_slot_entries_identical':True,
                        'builtin_menu_identical':True,'full_entry_comparisons':comparisons,'user_entries_visible_now':len(current.users),
                        'table_fingerprint_changed':earlier.table_sha256!=later.table_sha256})
    save('old-generations',{'packages':results,'comparisons':sum(r['full_entry_comparisons'] for r in results)})

def table_inventory():
    from g152_support import dat_path
    from gxr_studio.camdata import datcodec as dc, knob_table
    from gxr_studio.engine import menu
    source=menu.TABLE_PATH
    data=menu.load()
    baseline=subprocess.check_output(['git','--no-optional-locks','show','HEAD:src/gxr_studio/engine/data/final.json'],cwd=STUDIO)
    def points(table):return [[(p['level'],p['dose']) for p in item['points']] for item in table['items']]
    checks=[]
    for gen in (150,152,153):
        dat=dc.parse(dat_path(gen).read_bytes())
        external=knob_table.read(dat.kv2_block,data)
        checks.append({'generation':gen,'block_sha256':sha(dat.kv2_block),'all_points_equal':points(external)==points(data)})
    assert all(c['all_points_equal'] for c in checks)
    import zipfile
    package_checks=[]
    for path in (SCRATCH/'preflight-dist').glob('*.whl'):
        with zipfile.ZipFile(path) as z:
            entry='gxr_studio/engine/data/final.json'
            package_checks.append({'wheel':path.name,'member':entry,'same_as_repo':z.read(entry)==source.read_bytes()})
    save('table-inventory-result',{'file':str(source.relative_to(STUDIO)),'sha256':sha(source.read_bytes()),'already_in_HEAD':baseline==source.read_bytes(),
        'recipe_count':len(data['recipes']),'control_item_count':len(data['items']),'point_pair_count':sum(len(i['points']) for i in data['items']),
        'registered_dat_tables':checks,'wheel_checks':package_checks})

def prepare_ui_fix():
    folder=SCRATCH/'patch-proof'
    folder.mkdir(parents=True,exist_ok=True)
    caps=(STUDIO/'web/assets/caps.js').read_text()
    caps=caps.replace("import { api, ApiError } from './api.js';", "import { api, ApiError } from './api.js';\nimport { state, on } from './state.js';")
    caps=caps.replace('const photoCache = new Map();',"const photoCache = new Map();\non('camdata-changed', () => {\n  for (const key of photoCache.keys()) if (key.startsWith('caps:')) photoCache.delete(key);\n});")
    caps=caps.replace('const key = `caps:${id}`;', 'const version = state.camdata?.dataVersion;\n  const key = `caps:${id}:${version}`;')
    caps=caps.replace("photoCache.set(key, probe(`/api/photos/${id}/capabilities`, '配方'))", "photoCache.set(key, probe(`/api/photos/${id}/capabilities`, '配方').then(result => version === state.camdata?.dataVersion ? result : loadPhotoCaps(id)))")
    preview=(STUDIO/'web/assets/preview.js').read_text()
    preview=preview.replace("import { state } from './state.js';","import { state, on } from './state.js';")
    preview=preview.replace('let catalogVersion = 0;',"let catalogVersion = 0;\non('camdata-changed', () => {\n  state.catalog = null;\n  catalogPromise = null;\n  catalogVersion++;\n});")
    preview=preview.replace('(r) => {\n        if (version === catalogVersion) state.catalog = r;', '(r) => {\n        if (version !== catalogVersion) return loadCatalog();\n        if (version === catalogVersion) state.catalog = r;')
    (folder/'caps.js').write_text(caps)
    (folder/'preview.js').write_text(preview)
    save('scratch-fix-files',{'scope':'two scratch copies only, product untouched','files':tree(folder)})

def damaged_files(raw):
    from gxr_studio.camdata import datcodec as dc
    out={'empty':b'','short7':raw[:7],'short255':raw[:255],'short260':raw[:260],'last_byte':raw[:-1]}
    for name,at in (('header_crc',40),('body_crc',5000)):
        b=bytearray(raw);b[at]^=1;out[name]=bytes(b)
    b=bytearray(raw);struct.pack_into('>I',b,28,154);out['generation154']=reseal(b)
    b=bytearray(raw+bytes(dc.PROFILES[dc.peek_generation(raw)].max_file+4-len(raw)))
    struct.pack_into('>I',b,16,len(b));out['oversized']=reseal(b)
    if dc.peek_generation(raw) in (152,153):
        pool=dc.u32(raw,192); area=pool+dc.u32(raw,pool+64); size=dc.u32(raw,pool+68)
        def variant(name,at,value,fmt='>B'):
            b=bytearray(raw);struct.pack_into(fmt,b,at,value)
            struct.pack_into('>I',b,area+24,dc.crc(b[area+32:area+size]))
            struct.pack_into('>I',b,area+28,dc.crc(b[area:area+28]))
            out[name]=reseal(b)
        for name,offset,value,fmt in (
            ('effect_unaligned',pool+64,81,'>I'),('effect_before_header',pool+64,76,'>I'),
            ('effect_outside',pool+64,0xfffffffc,'>I'),('effect_short',pool+68,28,'>I'),
            ('pool_before_header',pool+20,76,'>I'),('capacity49',area+8,49,'>H'),
            ('count_over_capacity',area+10,49,'>H'),('cap128',area+16,128,'>B'),('used_over_cap',area+20,128,'>B'),
            ('base0',area+32,0,'>B'),('base4',area+32,4,'>B'),('mask0',area+50,0,'>B'),('mask8',area+50,8,'>B'),
            ('reserved',area+51,1,'>B'),('name_nonascii',area+52,255,'>B'),('name_empty',area+52,0,'>B'),
            ('effect_index127',area+40,255,'>B'),('stock_index127',area+40,127,'>B'),
        ):variant(name,offset,value,fmt)
        block=dc.u32(raw,204)+dc.LEGACY_BYTES+dc.EXT_BYTES
        b=bytearray(raw);struct.pack_into('>I',b,block+44,0xfffffffe);out['r3_point_offset']=reseal(b)
    return out

def parsing_and_api():
    folder=SCRATCH/'api'
    if folder.exists(): shutil.rmtree(folder)
    from fastapi.testclient import TestClient
    from g152_support import dat_path
    from gxr_studio.camdata import datcodec as dc
    from gxr_studio.config import Settings
    from gxr_studio.app import create_app
    from gxr_studio import audit
    # Same protections as the repository tests; every Settings path is explicit.
    audit.forbid_volumes(); audit.forbid_network(True)
    rows=[]
    all_bad={}
    for gen in (150,152,153):
        for test in (False,True):
            raw=dat_path(gen,test).read_bytes()
            for label,b in damaged_files(raw).items():
                try: dc.parse(b)
                except dc.DatError as exc:
                    rows.append({'generation':gen,'test':test,'case':label,'rejected':True,'reason':str(exc)})
                else: raise AssertionError((gen,test,label,'accepted'))
                if not test: all_bad[f'{gen}/{label}']=b
    rnd=random.Random(20261102)
    raw=dat_path(152).read_bytes();accepted=0;rejected=0;accepted_sections={};changed_module_fields=set()
    original=dc.parse(raw)
    for _ in range(600):
        b=bytearray(raw);at=rnd.randrange(256,len(b));b[at]^=1<<rnd.randrange(8);b=reseal(b)
        try:
            d=dc.parse(b);assert dc.pack(d)==b;accepted+=1
            section=next(i+1 for i in range(7) if dc.u32(raw,132+12*i)<=at<dc.u32(raw,132+12*i)+dc.u32(raw,136+12*i))
            accepted_sections[section]=accepted_sections.get(section,0)+1
            assert d.looks==original.looks and d.users==original.users and d.kv2_block==original.kv2_block
            for u in range(3):
                changed_module_fields.update(k for k in vars(d.modules[u]) if getattr(d.modules[u],k)!=getattr(original.modules[u],k))
                for slot in range(1,17): assert d.entry_of(u,slot)==original.entry_of(u,slot)
        except dc.DatError:rejected+=1
    settings=Settings(home_dir=folder/'home',library_dir=folder/'library',export_dir=folder/'export',
                      volumes_roots=(folder/'volumes',),token='independent-review',port=18746,min_free_bytes=0)
    app=create_app(settings)
    results=[]
    with TestClient(app,base_url='http://127.0.0.1:18746',headers={'X-GXR-Token':settings.token}) as client:
        raw=dat_path(153,True).read_bytes()
        assert client.post('/api/camdata/import-upload',content=raw).status_code==200
        before=tree(settings.home_dir)
        catalog=client.get('/api/recipes').json()
        for label,b in all_bad.items():
            response=client.post('/api/camdata/import-upload',content=b)
            assert response.status_code==422,(label,response.text)
            assert tree(settings.home_dir)==before,label
            status=client.get('/api/camdata/status').json()
            assert status['camera_data']['state']=='ready' and status['camera_data']['generation']==153
            assert client.get('/api/recipes').json()==catalog
            results.append({'case':label,'status':response.status_code,'code':response.json()['error'],'old_data_unchanged':True})
        # Upload stream size limit, independent of profile-size validation.
        response=client.post('/api/camdata/import-upload',content=bytes(2*1024*1024))
        assert response.status_code==422 and tree(settings.home_dir)==before
        results.append({'case':'upload_limit','status':422,'old_data_unchanged':True})
        cards=folder/'volumes'
        for name,content in (('FIRST',all_bad['152/generation154']),('SECOND',dat_path(152,True).read_bytes())):
            root=cards/name;root.mkdir(parents=True);(root/'GXRCE.DAT').write_bytes(content)
        card_before=tree(cards)
        response=client.post('/api/camdata/import-card',json={})
        assert response.status_code==409 and response.json()['error']=='multiple_cards'
        choices=response.json()['cards'];assert len(choices)==2
        first=next(c for c in choices if c['label']=='FIRST')
        second=next(c for c in choices if c['label']=='SECOND')
        response=client.post('/api/camdata/import-card',json={'card_id':first['id']})
        assert response.status_code==422 and tree(settings.home_dir)==before
        response=client.post('/api/camdata/import-card',json={'card_id':second['id']})
        assert response.status_code==200,response.text
        assert len(client.get('/api/recipes').json()['units'][0]['looks'])==10
        assert tree(cards)==card_before
    assert audit.network_attempts()==[]
    save('parsing-api',{'direct_cases':len(rows),'direct_results':rows,'bounded_mutations':{'cases':600,'accepted':accepted,'accepted_by_section':accepted_sections,
        'accepted_entry_rows_and_point_tables_unchanged':True,'changed_module_fields':sorted(changed_module_fields),
        'outer_crc_recomputed':True,'rejected':rejected,'unhandled_exceptions':0},
                        'failed_imports':results,'multi_card':{'choices':2,'first_rejected':True,'second_imported':True,'cards_unchanged':True}})

if __name__=='__main__':
    SCRATCH.mkdir(parents=True,exist_ok=True)
    {'portable':portable,'equality':equality,'old':old_generations,'parsing':parsing_and_api,'tables':table_inventory,'ui-fix':prepare_ui_fix}[sys.argv[1]]()
