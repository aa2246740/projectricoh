"""Original build functions, original sources/toolchain, review-only output."""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from review_common import HERE, ROOT, module, save
from image_loader import Elf
b=module(ROOT/"firmware/resident_v35/resident/build.py","review_original_resident_builder")
b.LOCAL=HERE/"resident"
b.LOCAL.mkdir(exist_ok=True)
(b.LOCAL/"tmp").mkdir(exist_ok=True)
os.environ["TMPDIR"]=str(b.LOCAL/"tmp")
os.environ["CLANG_MODULE_CACHE_PATH"]=str(b.LOCAL/"tmp/clang")
b.trust_source()
hooks=json.loads((ROOT/"firmware/resident_v35/local/resident/hooks.json").read_text())
enabled=[h for h in hooks if h["number"] not in set(range(10,38))]
extra=b.hooks_source(enabled)
out=b.LOCAL/"build";out.mkdir(exist_ok=True)
objects=[]
for src in [*(b.HERE/n for n in b.SOURCES),b.LOCAL/"trust.c",b.LOCAL/"linked_hooks.S"]:
    obj=out/(src.stem+".o");objects.append(obj)
    b.run([b.GCC,*b.FLAGS,*( ["-mmodel=medium"] if src.suffix==".c" else []),"-I",b.HERE,"-c",src,"-o",obj],"compile-"+src.stem)
defs=[f'--defsym=rv_resume_{h["number"]:02}={int(h["replay_resume"],16):#x}' for h in enabled if h["number"] not in (3,4)]
elf=out/"resident.elf"
b.run([b.LD,"--gc-sections","--no-undefined","--orphan-handling=error",*extra,*defs,"-T",b.HERE/"resident.ld",f'-Map={out/"resident.map"}',"-o",elf,*objects],"link")
e=Elf(elf);original=Elf(ROOT/"firmware/resident_v35/local/resident/build/resident.elf")
for name in (".payload",".root_pins"):
    assert next(s for s in e.sections if s["name"]==name)["data"]==next(s for s in original.sections if s["name"]==name)["data"]
assert e.symbols==original.symbols
assert b.build_identity().hex()=="9cc5359e073a3b65a223ca3af41055fd10e52b5e701db1fe08426023aea731ba"
assert e.symbols["__resident_code_end"]==0x20054634
b.run([b.OBJDUMP,"-d",elf],"disassembly")
save("resident-rebuild.json",dict(build_id=b.build_identity().hex(),abi=json.loads((b.LOCAL/"trust.json").read_text())["resident_abi_id"],
     code_end=hex(e.symbols["__resident_code_end"]),payload=next(s for s in e.sections if s["name"]==".payload")["size"],
     identical_load_sections=True,identical_symbols=True,elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
     original_elf_sha256=hashlib.sha256(original.raw).hexdigest()))

# ASan/UBSan: run the same original source list, with review-local objects.
fixture=module(b.HERE/"make_fixture.py","review_original_fixtures")
fixture.LOCAL=b.LOCAL
fixture.main()
flags=["clang","-std=c11","-O1","-g","-Wall","-Wextra","-Werror","-DRV_HOST","-fsanitize=address,undefined","-fno-omit-frame-pointer","-I",str(b.HERE)]
sources=[(b.HERE/n,False) for n in ("resident.c","loader.c","shared.c","hooks.c","runtime.c","validate_envelope.inc.c")]
sources += [(b.HERE.parent/"engine_services"/n,True) for n in ("services.c","api.c","runtime.c","crc.c","mark.c","native_seed.c")]
sources += [(b.HERE/"shared.c",True),(b.HERE/"v3_checks.c",False),(b.LOCAL/"trust.c",False)]
host=b.LOCAL/"host";host.mkdir(exist_ok=True);objects=[]
for i,(src,service) in enumerate(sources):
    obj=host/(str(i)+"-"+src.stem+".o");objects.append(obj)
    extra=["-DRV_ENGINE_SERVICES"] if service else []
    if src.name=="runtime.c":extra += ["-Dmemcpy="+("es_test_memcpy" if service else "rv_test_memcpy"),"-Dmemset="+("es_test_memset" if service else "rv_test_memset")]
    b.run([*flags,*extra,"-c",src,"-o",obj],"host-compile-"+str(i))
binary=host/"checks"
b.run(["clang","-fsanitize=address,undefined",*objects,"-o",binary],"host-link")
os.environ["ASAN_OPTIONS"]="detect_leaks=0:halt_on_error=1"
os.environ["UBSAN_OPTIONS"]="halt_on_error=1:print_stacktrace=1"
p=b.run([binary,b.LOCAL/"fixtures/synthetic-container.fixture"],"host-checks")
print(p.stdout)
