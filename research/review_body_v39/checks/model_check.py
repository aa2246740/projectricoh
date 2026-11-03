#!/usr/bin/python3 -I
"""Run retained body cases with explicit output and the batch interpreter."""
from pathlib import Path
import importlib.util
import json
import os
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import batch_model as B


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    mode, unit, *arguments = sys.argv[1:]
    output = B.OUT / os.environ['REVIEW_CASE']
    (output / 'evidence').mkdir(parents=True, exist_ok=True)
    (output / 'tests').mkdir()
    source = B.ROOT / 'research/body_v39/tests'
    host = load('v39_host', source / 'v39_host.py')
    B.bind_host(host, output / 'model')
    if mode == 'body':
        module = load('review_body_cases', source / 'dat_body.py')
        module.OUT = output / 'evidence'
        sys.argv = [str(source / 'dat_body.py'), unit, *arguments]
    elif mode == 'route':
        module = load('review_route_cases', source / 'load_routes.py')
        scenario = arguments[0]
        old = {'g137': 'firmware/package_v38_g137/local/SD_ROOT/GXRCE.DAT',
               'probe148': 'firmware/package_v38_cpuprobe/SD_ROOT/GXRCE.DAT'}
        if scenario in old:
            module.G139 = B.ROOT / old[scenario]
            scenario = 'old-dat'
        module.HERE = output / 'tests'
        sys.argv = [str(source / 'load_routes.py'), unit, scenario]
    elif mode == 'checks':
        module = load('review_retained_checks', source / 'g139_check_v39.py')
        module.HERE = output / 'tests'
        sys.argv = [str(source / 'g139_check_v39.py'), *arguments, '--unit', unit]
    else:
        raise SystemExit('unknown model case')
    module.main()
    assert B.INSTANCES
    assert sum(item.batch_stats.get('batch-steps', 0) for item in B.INSTANCES) > 0
    print(json.dumps({'batch_instances': len(B.INSTANCES),
                      'batch_steps': sum(item.batch_stats.get('batch-steps', 0) for item in B.INSTANCES)}))


if __name__ == '__main__':
    main()
