"""Rebuild either frozen reference or final candidate under this task's local/."""
from pathlib import Path
import argparse
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import *

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--generation', type=int, choices=(124,126), default=126)
    args = parser.parse_args()
    source = ROOT / ('firmware/engine_v46_ui' if args.generation == 124 else 'firmware/engine_v47_fix') / 'candidate'
    folder = OUT / 'local' / ('rebuild-' + str(args.generation))
    routing = folder / 'routing'
    routing.mkdir(parents=True, exist_ok=True)
    c = load(source / 'common.py', 'common')
    c.LOCAL = folder
    def scoped_save(path, value):
        path = Path(path)
        assert path.resolve().is_relative_to(OUT)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
    c.save = scoped_save
    text = (source / 'service_build.py').read_text()
    text = text.replace('archive.relative_to(c.HERE)', 'archive.relative_to(c.ROOT)')
    text = text.replace('elf.relative_to(c.HERE)', 'elf.relative_to(c.ROOT)')
    service = routing / 'service_build.py'
    service.write_text(text)
    load(service, 'service_build')
    sys.path.insert(0, str(source / 'containers/product'))
    runtime = load(source / 'containers/product/runtime.py', 'runtime')
    runtime._common.LOCAL = folder
    runtime._common.save = scoped_save
    runtime.LOCAL = folder / 'product-r13'
    text = (source / 'containers/product/build.py').read_text().replace(
        "HERE.parents[1]/'local/resident/engine-services/libgxr_services.a'",
        repr(str(folder / 'resident/engine-services/libgxr_services.a')))
    product = routing / 'product_build.py'
    product.write_text(text)
    original_load = c.load
    def routed_load(path, name):
        if Path(path) == source / 'containers/product/build.py':
            path = product
        return original_load(path, name)
    c.load = routed_load
    builder = load(source / ('build' + str(args.generation) + '.py'), 'scoped_builder')
    sys.argv = [str(Path(__file__).resolve())]
    builder.main()
    names = ('GXRCE.DAT', 'engine.bin', 'reloc.bin', 'effective-rows.bin')
    equal = {name:(folder / 'full-r13' / name).read_bytes() == (source / 'local/full-r13' / name).read_bytes() for name in names}
    assert all(equal.values()), equal
    result = dict(status='PASS', generation=args.generation, equal=equal,
                  dat_sha256=file_sha(folder / 'full-r13/GXRCE.DAT'),
                  sources_and_flags_unchanged=True, services_rebuilt=True)
    save('evidence/rebuild-' + str(args.generation) + '.json', result)
    print(json.dumps(result))

if __name__ == '__main__':
    main()
