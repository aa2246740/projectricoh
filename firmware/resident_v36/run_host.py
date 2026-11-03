"""Run resident v3.6 host checks with ASan/UBSan; output stays in this copy."""
import importlib.util,os
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location("v36_host_builder",HERE/"resident/build.py")
b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
os.environ["TMPDIR"]=str(b.LOCAL/"tmp")
os.environ["CLANG_MODULE_CACHE_PATH"]=str(b.LOCAL/"tmp/clang")
# ASan/UBSan: run the same original source list, with review-local objects.
fixture=b.module(b.HERE/"make_fixture.py","review_original_fixtures")
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
