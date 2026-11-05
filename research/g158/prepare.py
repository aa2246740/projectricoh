"""Freeze g157 and prepare a data-identical, generation-158 workspace."""
from pathlib import Path
import hashlib,json,os,plistlib,re,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];HERE=ROOT/'research/g158';LOCAL=HERE/'local'
assert os.getpriority(os.PRIO_PROCESS,0)>=15
info=plistlib.loads(subprocess.check_output(['diskutil','info','-plist','/Volumes/Workspace']))
assert info['VolumeUUID']=='14BE04EB-AF49-497E-B36A-B078B2F7C5E8' and info['FilesystemType']=='apfs' and info['WritableVolume']
sys.path.insert(0,str(ROOT/'tools'));import loadgate
workers,load_info=loadgate.workers()
assert workers,'LOAD_DEFERRED '+json.dumps(load_info)
old=ROOT/'research/g157';engine=ROOT/'firmware/engine_v70_g158';prior=ROOT/'firmware/engine_v69_g157'
LOCAL.mkdir(exist_ok=True);before=LOCAL/'before';before.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
expected={'test':'2b8904592ce56ab03649ced52c8479b0bbac4e45bf9a47505d220795bb3ec56c','release':'3ebc261cf290a376d59ffc24b4d5b6f9ab1dd5b9d5a8cd7242561d45707107b6'}
if not engine.exists():
    engine.mkdir();(engine/'.gitignore').write_text('local/\n**/local/\ncandidate/\n')
    shutil.copytree(prior/'resident',engine/'resident')
    shutil.copytree(prior/'candidate',engine/'candidate',ignore=shutil.ignore_patterns('local','__pycache__'))
product=engine/'candidate/containers/product';sources={}
for p in (prior/'candidate/containers/product').rglob('*'):
    if p.is_file() and p.suffix in ('.c','.h','.py','.S','.ld') and 'local' not in p.relative_to(prior/'candidate/containers/product').parts:
        rel=p.relative_to(prior/'candidate/containers/product');target=before/'source'/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():shutil.copyfile(p,target)
        sources[str(rel)]=sha(target)
for profile,digest in expected.items():
    package=ROOT/('firmware/package_v310_g157'+('_test' if profile=='test' else ''))
    assert sha(package/'local/SD_ROOT/GXRCE.DAT')==digest
    dest=before/profile;dest.mkdir(exist_ok=True)
    for name,source in [('GXRCE.DAT',package/'local/SD_ROOT/GXRCE.DAT'),('MANIFEST',package/'MANIFEST'),('records.json',old/'local'/('model-records-'+profile+'.json'))]:
        if not (dest/name).exists():shutil.copyfile(source,dest/name)
    if not (dest/'build').exists():
        (dest/'build').mkdir()
        for name in ('engine.elf','engine.bin','reloc.bin','size.json','relocations.json','engine.map'):
            shutil.copyfile(prior/'candidate/local'/('model-boot-on' if profile=='test' else 'model-boot-off')/name,dest/'build'/name)
    manifest=json.loads((dest/'records.json').read_text());manifest['schema']='g158-record-manifest/1';manifest['generation']=158
    (LOCAL/('model-records-'+profile+'.json')).write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    target=ROOT/('firmware/package_v310_g158'+('_test' if profile=='test' else ''));target.mkdir(exist_ok=True);(target/'.gitignore').write_text('local/\n')
for name in ('common.py','build.py','layout.py','records.py','static.py','host_probe.py','service_probe.py','replay.py','reference_input.py'):
    text=(old/name).read_text().replace('g157','g158').replace('G157','G158').replace('engine_v69_g158','engine_v70_g158')
    if name=='common.py':text=text.replace("BASE = ROOT/'firmware/engine_v68_g156'","BASE = ROOT/'firmware/engine_v69_g157'")
    if name in ('build.py','records.py','static.py'):
        text=re.sub(r'\b157\b','158',text)
    if name=='records.py':text=text.replace("return (C.LOCAL/'inputs'/path).read_bytes()","return (C.ROOT/'research/g157/local/inputs'/path).read_bytes()")
    if name=='static.py':text=text.replace('for generation in (156,155,158):','for generation in (157,156,159):')
    if name=='service_probe.py':
        text=text.replace("old=C.load(C.HERE/'records.py','g158_probe_records').frozen(Path('firmware/package_v310_g156/GXRCE.DAT'))","old=(C.ROOT/'firmware/package_v310_g157/local/SD_ROOT/GXRCE.DAT').read_bytes()")
        text=text.replace("'g156-DAT-binding'","'g157-DAT-binding'")
    (HERE/name).write_text(text)
shutil.copyfile(old/'local/fix-r1/final/run.py',HERE/'run.py')
text=(HERE/'run.py').read_text().replace('g157','g158').replace('G157','G158')
(HERE/'run.py').write_text(text)
for name in ('layout.json','frozen.json'):
    if not (LOCAL/name).exists():shutil.copyfile(old/'local'/name,LOCAL/name)
for name in ('gate.c','eng_data.c','ui_v2_data.c','pack.py','adapter.c','diagnostic.c','diagnostic.h','boot_adapter.inc.c'):
    choices=list(product.rglob(name));assert len(choices)==1,(name,choices)
    p=choices[0];text=p.read_text();text=re.sub(r'\b157\b','158',text).replace('g157','g158').replace('G157','G158');p.write_text(text)
p=product/'boot_adapter.inc.c';text=p.read_text()
oldgate='''    /* The existing proven native branch. No physical M/P/A/S mapping is invented. */
    if(RV_BYTE(0x205d9a7f)!=0||!valid||RV_WORD(settings+0x2fc)!=0x8001)bits|=BF_MODE;'''
newgate='''    /* g158: field-confirmed PASM pairs; retain the original AUTO branch.
     * Exact selection matching also excludes movie/scene variants. */
    {
        static const uint16_t pasm[4]={0x8010,0x8020,0x8008,0x8800};
        unsigned mode=RV_BYTE(0x205d9a7f),sub=RV_BYTE(0x205d9a9f);
        if(!valid||!((mode==0&&RV_WORD(settings+0x2fc)==0x8001)||
            (mode==4&&sub<4&&RV_WORD(settings+0x2fc)==pasm[sub])))bits|=BF_MODE;
    }'''
assert oldgate in text or newgate in text
p.write_text(text.replace(oldgate,newgate))
field=[line for line in (ROOT/'decisions.tsv').read_text().splitlines() if '\tg157-field-' in line]
(LOCAL/'field-decisions.tsv').write_text('\n'.join(field)+'\n')
freeze=dict(status='PASS',source_sha256=sources,DAT=expected,deadline_utc='2026-11-05T05:00:24+00:00',field_decisions_sha256=sha(LOCAL/'field-decisions.tsv'))
(LOCAL/'freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
(HERE/'REPORT.md').write_text('有缺陷\n\ng158 正在构建与验收；截至 2026-11-05 05:00:24 UTC。配方数据沿用 g157，唯一功能改动为 BOOT PASM 模式门。\n')
print(json.dumps(dict(status='PREPARED',source_files=len(sources),field_rows=len(field))))
