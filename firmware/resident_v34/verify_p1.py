"""Local P1 fixtures and an isolated exact-stub proof, never product acceptance."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'local/p1-checks'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(argv, label):
    for suffix in ('stdout', 'stderr'):
        previous = OUT / (label + '.' + suffix + '.log')
        if previous.is_file() and previous.stat().st_size:
            data = previous.read_bytes()
            failures = OUT / 'history'
            failures.mkdir(exist_ok=True)
            (failures / (label + '.' + suffix + '-' + hashlib.sha256(data).hexdigest()[:12] + '.log')).write_bytes(data)
    result = subprocess.run([str(a) for a in argv], cwd=ROOT, text=True, capture_output=True,
        env=dict(os.environ, TMPDIR=str(OUT / 'tmp'), PYTHONDONTWRITEBYTECODE='1',
                 ASAN_OPTIONS='detect_leaks=0:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1'))
    (OUT / (label + '.stdout.log')).write_text(result.stdout)
    (OUT / (label + '.stderr.log')).write_text(result.stderr)
    assert result.returncode == 0, label + ': ' + result.stdout[-1500:] + result.stderr[-2000:]
    return result.stdout


def main():
    b = load(HERE / 'resident/build.py', 'p1_build')
    b.preflight()
    (OUT / 'tmp').mkdir(parents=True, exist_ok=True)
    sources = ['resident.c', 'loader.c', 'shared.c', 'hooks.c', 'permit.c', 'validate_envelope.inc.c']
    executable = OUT / 'p1-host'
    run(['/usr/bin/clang', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
         '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-DRV_HOST',
         '-I', HERE / 'resident', *[HERE / 'resident' / s for s in sources],
         HERE / 'tests/p1_host.c', '-o', executable], 'host-compile')
    host = run([executable], 'host-run')
    match = re.search(r'cases=(\d+) assertions=(\d+)', host)
    assert match
    # This ELF contains the actual generated stubs, a no-op observer, and pins.
    # It is deliberately not a resident candidate or a firmware image.
    shim = OUT / 'observer.S'
    shim.write_text('.section .text.rv_hook_observe,"ax"\n.balign 4\n'
                    '.global rv_hook_observe\nrv_hook_observe:\njmp lr\nnop\n'
                    '.section .root_pins,"a"\n.balign 4\n'
                    '.long 0xf09fe7b4,0xfb3fbcb2,0x95f3dca9\n')
    run([b.GCC, *b.FLAGS, '-c', shim, '-o', OUT / 'observer.o'], 'shim-compile')
    hooks = json.loads((b.LOCAL / 'hooks.json').read_text())
    active = [h for h in hooks if h['number'] in (1, 2, 5, 6, 7, 8, 9, 40)]
    # Regenerate, then prove the exact object used by the final standard build.
    extra = b.hooks_source(active)
    linked = HERE / 'local/resident/p1-final-os/linked_hooks.o'
    assert linked.is_file()
    run([b.GCC, *b.FLAGS, '-c', b.LOCAL / 'linked_hooks.S', '-o', OUT / 'hooks.o'], 'hooks-compile')
    assert (OUT / 'hooks.o').read_bytes() == linked.read_bytes(), 'not the final stub object'
    defs = [f'--defsym=rv_resume_{h["number"]:02}={h["replay_resume"]}' for h in active if h['number'] != 40]
    elf = OUT / 'isolated-h40-proof.elf'
    run([b.LD, '--gc-sections', '--no-undefined', '--orphan-handling=error', *extra, *defs,
         '-T', HERE / 'resident/resident.ld', '-Map=' + str(OUT / 'isolated-h40-proof.map'),
         '-o', elf, OUT / 'hooks.o', OUT / 'observer.o'], 'shim-link')
    policy = load(ROOT / 'firmware/resident_v33/policy_machine.py', 'p1_frozen_cpu')
    policy.LOCAL = OUT
    program = policy.Program('isolated-h40-proof', elf)
    vectors = []
    rng = random.Random(3401)
    for fp in (0, 1, 0x80000000, 0xffffffff):
        for flags in [*range(128), 0x00400000, 0x80000000, 0xffffffff]:
            cpu = policy.Cpu(program)
            cpu.r = [rng.getrandbits(32) for _ in range(16)]
            cpu.r[13] = fp
            cpu.r[14] = policy.END
            cpu.r[15] = 0x206eff00
            cpu.psw = flags
            original = cpu.r.copy()
            native_target = []
            def observe(c):
                assert c.r[0] == 0x20054700 and c.r[1] == 40
                frame = c.r[2]
                assert frame + 17 * 4 == original[15]
                assert c.read(frame) == flags
                assert [c.read(frame + 4 * i) for i in range(2, 16)] == list(reversed(original[:14]))
                assert c.read(frame + 16 * 4) == original[14]
                for i in range(14):
                    c.r[i] ^= 0xffffffff
                c.psw ^= 0xffffffff
            cpu.stubs[program.symbols['rv_hook_observe']] = observe
            for address in (0x202b115c, 0x202b1364):
                cpu.stubs[address] = lambda c, a=address: native_target.append(a)
            cpu.run('rv_hook_40')
            assert cpu.r == original and cpu.psw == flags
            assert native_target == [0x202b115c if fp else 0x202b1364]
            vectors.append(dict(fp=fp, psw=flags, native_target=native_target[0]))
    # IRQ helpers are unchanged assembly, checked exhaustively from compiled bytes.
    irq_module = load(ROOT / 'firmware/resident_v33/machine_checks.py', 'p1_frozen_irq')
    reader = policy.reader
    parsed = reader.Elf(HERE / 'local/resident/p1-final-os/bridges.o')
    def extract(name, n):
        symbol = parsed.symbols[name]
        section = parsed.sections[symbol['section']]
        return parsed.content(section)[symbol['value']:symbol['value'] + n]
    save, restore = extract('rv_irq_save', 12), extract('rv_irq_restore', 4)
    for flags in range(65536):
        cpu = irq_module.IRQ(flags)
        cpu.run(save)
        assert cpu.psw == (flags & ~0x40) and cpu.r[0] == flags
        cpu.run(restore)
        assert cpu.psw == flags
    formats = load(HERE / 'local/formats.py', 'p1_wire_decoder')
    templates = {}
    for name in ('GXRBX0.BIN', 'GXRBX1.BIN'):
        p = HERE / 'local/controls' / name
        formats.read_log(p.read_bytes())
        templates[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    result = dict(status='PASS_P1_LOCAL_CHECKS_ONLY',
        host_cases=int(match[1]), host_assertions=int(match[2]),
        h40_stub_vectors=len(vectors), h40_stub_bytes=28, irq_psw_vectors=65536,
        blackbox_template_decodes=2, templates=templates,
        isolated_proof_elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
        host_executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(),
        full_resident_link_passed=False, product_acceptance=False,
        continuous_native_replay=False, camera_acceptance=False,
        limits='C gate fixtures use native doubles and manual dispatch coordinates. H40 proof replaces its C observer. No product engine, full boot, constructor, image, or camera was exercised.')
    (OUT / 'h40-vectors.json').write_text(json.dumps(vectors, indent=2) + '\n')
    (OUT / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
