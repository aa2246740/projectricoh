"""Relink frozen LTO objects into this review directory and retain GCC proofs."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
def main():
    gen=int(sys.argv[1]) if len(sys.argv)>1 else 117
    out=OUT/('compiler' if gen==117 else 'compiler116');out.mkdir(exist_ok=True);(out/'tmp').mkdir(exist_ok=True)
    source=ROOT/('firmware/engine_v38_ro/candidate' if gen==117 else 'firmware/engine_v37/candidate')
    script=source/'containers/product/engine.ld';(out/'engine.ld').write_bytes(script.read_bytes())
    objs=sorted((source/'local/product-r13/m32r-lto').glob('*.o'))
    flags=['-Os','-fstack-usage','-fno-partial-inlining','-fno-ipa-sra','-fno-inline-small-functions','-flto','-m32r','-nostdlib',
           '-fdump-ipa-cp-details','-fdump-tree-optimized','-fdump-ipa-pure-const-details','-fdump-ipa-inline-details']
    ld=['--no-undefined','--orphan-handling=error','--emit-relocs','--gc-sections','-Bsymbolic','--defsym=BSS_START='+str(55500 if gen==117 else 66488),'--defsym=IMAGE_BASE=0','-T'+str(out/'engine.ld'),'-Map='+str(out/'engine.map')]
    cmd=[str(ROOT/'research/tooling_m32r_c/prefix/gcc/bin/m32r-elf-gcc'),*flags,*['-Wl,'+s for s in ld],'-o',str(out/'engine.elf'),*map(str,objs),str(source/'local/resident/engine-services/libgxr_services.a')]
    env=dict(os.environ,TMPDIR=str(out/'tmp'),LC_ALL='C',PYTHONDONTWRITEBYTECODE='1')
    result=subprocess.run(cmd,cwd=out,env=env,capture_output=True,text=True,timeout=120)
    (out/'stdout').write_text(result.stdout);(out/'stderr').write_text(result.stderr)
    same=result.returncode==0 and (out/'engine.elf').read_bytes()==(OUT/f'engine{gen}.elf').read_bytes()
    (out/'command.json').write_text(json.dumps(dict(argv=cmd,returncode=result.returncode,elf_byte_equal=same),indent=2)+'\n')
    print('compiler_dump',result.returncode,'ELF identical',same)
    if result.returncode:print(result.stderr[-2500:])
if __name__=='__main__':main()
