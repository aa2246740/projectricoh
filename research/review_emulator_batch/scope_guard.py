"""Offline review boundary. No writes to reviewed or frozen inputs."""
import os
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TMP = Path('/Volumes/Workspace/Scratch/tmp/projectricoh/review-emulator-batch')


def enable():
    os.environ['TMPDIR'] = str(TMP)
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    tempfile.tempdir = str(TMP)
    allowed = (HERE, TMP)

    def check(value, writing=False):
        if value is None or isinstance(value, int):
            return
        path = Path(os.fsdecode(value)).resolve()
        if str(path) == '/Volumes/RICOHDCX' or str(path).startswith('/Volumes/RICOHDCX/'):
            raise PermissionError('physical medium access refused')
        if writing and path != Path('/dev/null') and not any(path.is_relative_to(p) for p in allowed):
            raise PermissionError('review write boundary refused ' + str(path))

    def audit(event, args):
        if event == 'open':
            path, mode, flags = args
            writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or bool(
                flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
            check(path, writing)
        elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.chmod', 'os.truncate'):
            check(args[0], True)
        elif event in ('os.rename', 'os.symlink', 'os.link'):
            check(args[0], True)
            check(args[1], True)
        elif event in ('socket.connect', 'socket.bind', 'socket.getaddrinfo'):
            raise PermissionError('network access refused')
    sys.addaudithook(audit)


def admit_medium(module):
    original = module.BlockImage.__init__

    def initialize(self, path):
        path = Path(path).resolve()
        if path.is_relative_to(HERE):
            if not path.is_file():
                raise ValueError('review medium must be a regular file')
            self.path, self.size = path, path.stat().st_size
            if not self.size or self.size % module.SECTOR:
                raise ValueError('medium length must be a positive sector multiple')
            self.sectors = self.size // module.SECTOR
            self.read_errors, self.write_errors = set(), set()
            return
        original(self, path)
    module.BlockImage.__init__ = initialize
