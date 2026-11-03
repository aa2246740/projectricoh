"""Content-addressed compiler artifacts bound to each request environment."""
import copy
import contextlib
import fcntl
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import time
import types
from common import LOCAL, ROOT, digest, emit, private, sha


def tool_identity(executable, environment=None):
    environment = dict(os.environ) if environment is None else dict(environment)
    found = shutil.which(str(executable), path=environment.get('PATH', os.defpath))
    if found is None:
        raise FileNotFoundError(str(executable))
    path = Path(found).absolute()
    selected = path
    if path.parent == Path('/usr/bin') and path.name in ('clang', 'clang++', 'cc', 'c++'):
        selected = Path(subprocess.check_output(['/usr/bin/xcrun', '--find', path.name], text=True, timeout=3600, env=environment).strip()).absolute()
    version = subprocess.check_output([str(selected), '--version'], text=True, timeout=3600, env=environment)
    # The Mach-O image plus imported non-system dylibs bind the tool implementation.
    linked = subprocess.run(['/usr/bin/otool', '-L', str(selected)], text=True, capture_output=True, check=True, timeout=3600, env=environment)
    libraries = {}
    for row in linked.stdout.splitlines()[1:]:
        name = row.strip().split(' (', 1)[0]
        p = Path(name)
        if p.is_absolute() and p.is_file():
            libraries[str(p)] = sha(p)
        else:
            libraries[name] = 'system-cache-or-loader-relative'
    return {'path': str(path), 'sha256': sha(path), 'selected_path': str(selected), 'selected_sha256': sha(selected), 'version': version, 'libraries': libraries,
            'system': platform.platform(), 'machine': platform.machine(),
            'environment_sha256': digest(environment), 'environment': {k: v for k, v in sorted(environment.items()) if k.startswith(('DYLD_', 'LC_')) or k in ('LANG', 'TZ', 'PATH', 'DEVELOPER_DIR', 'SDKROOT', 'MACOSX_DEPLOYMENT_TARGET', 'CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'OBJC_INCLUDE_PATH', 'LIBRARY_PATH', 'COMPILER_PATH')}}


class CommandCache:
    def __init__(self, category):
        if category != 'compile':
            raise ValueError('unsupported content cache')
        self.root = LOCAL / 'cache' / category
        self.root.mkdir(parents=True, exist_ok=True)
        self.stats = {'hits': 0, 'misses': 0, 'invalid': 0, 'commands': 0,
                      'lookup_seconds': 0.0, 'execute_seconds': 0.0, 'lock_wait_seconds': 0.0}
        self.category = category
        self.artifacts = []

    @contextlib.contextmanager
    def locked(self,key):
        with (self.root/(key+'.lock')).open('a') as guard:
            began=time.monotonic()
            fcntl.flock(guard,fcntl.LOCK_EX)
            self.stats['lock_wait_seconds']+=time.monotonic()-began
            yield

    def identity(self, executable, environment=None):
        # A CommandCache can survive environment changes and fork; never reuse an earlier identity.
        return tool_identity(executable, environment)

    def compile(self, compiler, flags, sources, output_name, enabled=True):
        started = time.monotonic()
        environment = dict(os.environ)
        tool = self.identity(str(compiler), environment)
        compiler = tool["selected_path"]
        flags = list(map(str, flags)); sources = list(map(str, sources))
        if Path(output_name).name != output_name:
            raise ValueError('simple compiler output name required')
        # Ask the actual preprocessor for all transitive headers, including SDK headers.
        dep_flags = [s for s in flags if s not in ('-shared', '-fPIC') and not s.startswith('-Wl,')]
        command = [compiler, '-M', '-MT', 'speedlab'] + dep_flags + sources
        dependencies = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=3600, check=True, env=environment)
        tokens = shlex.split(dependencies.stdout.replace('\\\n', ' '))
        paths = sorted({str(Path(t).resolve()) for t in tokens if t != 'speedlab:'})
        if not paths or any(not Path(p).is_file() for p in paths):
            raise ValueError('compiler dependency scan is incomplete')
        bound = {'format': 3, 'tool': tool, 'flags': flags, 'sources': sources,
                 'dependencies': {p: sha(p) for p in paths}, 'output_name': output_name}
        key = digest(bound)
        folder = self.root / key; folder.mkdir(exist_ok=True)
        with self.locked(key):
            artifact = folder / output_name
            receipt = folder / 'receipt.json'
            self.stats['commands'] += 1
            if enabled and artifact.exists() and receipt.exists():
                saved = json.loads(receipt.read_text())
                if saved.get('binding') == bound and saved.get('artifact_sha256') == sha(artifact):
                    self.stats['hits'] += 1
                    self.stats['lookup_seconds'] += time.monotonic() - started
                    self.artifacts.append({'key': key, 'sha256': sha(artifact), 'bytes': artifact.stat().st_size, 'path': str(artifact)})
                    return artifact, saved['stdout'] + saved['stderr'], bound
                self.stats['invalid'] += 1
            self.stats['misses'] += 1
            self.stats['lookup_seconds'] += time.monotonic() - started
            began = time.monotonic()
            staging=folder/'.build'/output_name
            staging.parent.mkdir(exist_ok=True)
            result = subprocess.run([compiler] + flags + sources + ['-o', str(staging)], cwd=ROOT,
                                    capture_output=True, text=True, timeout=3600, env=environment)
            self.stats['execute_seconds'] += time.monotonic() - began
            if result.returncode:
                raise RuntimeError('host compilation failed: ' + result.stderr[-5000:])
            if any(sha(Path(p)) != wanted for p, wanted in bound['dependencies'].items()):
                raise RuntimeError('compiler dependency changed during compilation')
            if sha(Path(tool['path'])) != tool['sha256'] or sha(Path(tool['selected_path'])) != tool['selected_sha256']:
                raise RuntimeError('compiler changed during compilation')
            os.replace(staging,artifact)
            emit(receipt, {'binding': bound, 'artifact_sha256': sha(artifact),
                           'stdout': result.stdout, 'stderr': result.stderr, 'returncode': 0})
            self.artifacts.append({'key': key, 'sha256': sha(artifact), 'bytes': artifact.stat().st_size, 'path': str(artifact)})
            return artifact, result.stdout + result.stderr, bound
