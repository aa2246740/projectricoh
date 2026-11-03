"""Measure isolated resident ELF budgets. These ELFs are not firmware images."""
import ast
import importlib.util
import json
from pathlib import Path
import re

spec=importlib.util.spec_from_file_location('diag_common',Path(__file__).with_name('common.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


def main():
    c.guard();dest=c.LOCAL/'budget';dest.mkdir(exist_ok=True)
    commands=json.loads((c.R.parent/'local/resident/commands.json').read_text())
    command=next(x['argv'] for x in commands if x.get('name')=='constrained-link')
    original=(c.R/'loader.c').read_text();patched=original
    replacements=[
        ('r->flags|=RF_ATTEMPTED|RF_BUSY;r->state=RV_LOADING;',
         'r->flags|=RF_ATTEMPTED|RF_BUSY;r->state=RV_LOADING;\n    r->grain_settings=1;r->grain_bytes=0;++r->grain_value;'),
        ('address=rv_native_alloc(sizeof(RvLoadWork));','r->grain_settings=2;address=rv_native_alloc(sizeof(RvLoadWork));'),
        ('status=probe(r,2,trust,&c[2],w);','r->grain_settings=3;status=probe(r,2,trust,&c[2],w);'),
        ('address=rv_native_alloc(bytes);','r->grain_settings=4;address=rv_native_alloc(bytes);'),
        ('n=c[chosen].bytes;status=read_one','r->grain_settings=5;n=c[chosen].bytes;status=read_one'),
        ('if(!status&&!rv_validate(work,n,trust,v)&&',
         'r->grain_settings=6;r->grain_bytes=status?0u:(uint32_t)rv_validate(work,n,trust,v);\n        if(!status&&!r->grain_bytes&&'),
        ('status=rv_engine(r,v->entry_offset,q,reply);','r->grain_settings=7;status=rv_engine(r,v->entry_offset,q,reply);'),
        ('status=rv_engine(r,s->entries.init,q,reply);','r->grain_settings=8;status=rv_engine(r,s->entries.init,q,reply);'),
        ('r->state=RV_READY;rv_irq_restore(irq);','r->state=RV_READY;r->grain_settings=9;rv_irq_restore(irq);'),
        ('fail:\n    rv_retire','fail:\n    if(!r->grain_bytes)r->grain_bytes=(uint32_t)status;\n    rv_retire')]
    for old,new in replacements:
        assert patched.count(old)==1,old
        patched=patched.replace(old,new)
    flags=next(ast.literal_eval(x.value) for x in ast.parse((c.R/'build.py').read_text()).body
               if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='FLAGS' for t in x.targets))
    base=c.Elf(c.RESIDENT);old_size=next(s['size'] for s in base.sections if s['name']=='.payload')
    minimum=original.replace('address=rv_native_alloc(bytes);',
        'r->grain_settings=bytes;address=rv_native_alloc(bytes);')
    minimum=minimum.replace('fail:\n    rv_retire','fail:\n    r->grain_bytes=(uint32_t)status;\n    rv_retire')
    small=original
    for old,new in [replacements[0],replacements[3],replacements[6],replacements[7],replacements[8],replacements[9]]:
        small=small.replace(old,new)
    free_only=original.replace('    return RV_OK;\nfail:',
        '    rv_native_free((uint32_t)(uintptr_t)w);\n    return RV_OK;\nfail:')
    relaxed=dest/'physical-only.ld'
    relaxed.write_text((c.R/'resident.ld').read_text().replace('0x20054700 - 300','0x20054700'))
    results=[]
    for name,source in [('baseline',original),('trace-minimum',minimum),('trace-small',small),('free-work-only',free_only),
        ('trace',patched),('trace-free-work',patched.replace(
            '    return RV_OK;\nfail:',
            '    rv_native_free((uint32_t)(uintptr_t)w);\n    return RV_OK;\nfail:'))]:
        src=dest/(name+'.c');src.write_text(source);obj=dest/(name+'.o')
        c.run([c.GCC,*flags,'-mmodel=medium','-I',c.R,'-c',src,'-o',obj],'budget-compile-'+name)
        args=list(command)
        for i,arg in enumerate(args):
            if arg.endswith('/build/loader.o'):args[i]=str(obj)
            if arg.startswith('-Map='):args[i]='-Map='+str(dest/(name+'.map'))
            if i and args[i-1]=='-o':args[i]=str(dest/(name+'.elf'))
        result=c.run(args,'budget-link-'+name,check=False)
        row=dict(variant=name,link_returncode=result.returncode,verified_behavior=False,
                 firmware_image_generated=False,identity_reissued=False)
        size=re.search(r'^\.payload\s+0x[0-9a-f]+\s+0x([0-9a-f]+)',(dest/(name+'.map')).read_text(),re.M)
        assert size
        new_size=int(size[1],16)
        row.update(payload=new_size,delta=new_size-old_size,remaining=8084-new_size)
        if name=='baseline':
            rebuilt=c.Elf(dest/'baseline.elf')
            assert next(rebuilt.content(s) for s in rebuilt.sections if s['name']=='.payload')==next(
                base.content(s) for s in base.sections if s['name']=='.payload')
            row['matches_frozen_payload']=True
        if result.returncode and new_size<=8084:
            adjusted=list(args);adjusted[adjusted.index('-T')+1]=str(relaxed)
            adjusted[adjusted.index('-o')+1]=str(dest/(name+'-physical-only.elf'))
            for i,arg in enumerate(adjusted):
                if arg.startswith('-Map='):adjusted[i]='-Map='+str(dest/(name+'-physical-only.map'))
            c.run(adjusted,'budget-physical-only-'+name)
            row['fits_physical_window_only']=True
        results.append(row)
    c.save(c.LOCAL/'resident-budgets.json',dict(baseline_payload=old_size,baseline_spare=312,
        proposed_reserved_root_offsets=[232,236,240],results=results,
        limit='Size-only ELF experiment; no patched resident behavior or camera acceptance. Never flash these ELFs.'))
    for row in results:print(row)


if __name__=='__main__':main()
