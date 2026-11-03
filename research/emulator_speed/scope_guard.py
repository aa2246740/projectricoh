"""Reject Python file writes outside the two authorized directories."""
import os
from pathlib import Path
import sys
import tempfile


def enable():
    root = Path(__file__).resolve().parents[2]
    allowed = (root / "tools/gxr_emulator", root / "research/emulator_speed")
    temporary = allowed[1] / "local/temporary"
    temporary.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(temporary)
    def check(value):
        if value is None or isinstance(value, int):
            return
        path = Path(os.fsdecode(value)).resolve()
        if path == Path("/dev/null"):
            return
        if not any(path.is_relative_to(base) for base in allowed):
            raise PermissionError("write fence refused a path outside this study")
    def audit(event, args):
        if event == "open":
            path, mode, flags = args
            if (isinstance(mode, str) and any(x in mode for x in "wax+")) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
                check(path)
        elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.truncate"):
            check(args[0])
        elif event in ("os.rename", "os.symlink", "os.link"):
            check(args[0])
            check(args[1])
        elif event in ("socket.connect", "socket.bind"):
            raise PermissionError("network use is outside this study")
    sys.addaudithook(audit)
