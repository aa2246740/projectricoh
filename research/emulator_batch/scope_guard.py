"""Reject Python file writes outside this study, its tool copy and TMPDIR; no network."""
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TMP = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/emulator-batch")


def enable():
    allowed = (ROOT / "tools/gxr_emulator_batch", ROOT / "research/emulator_batch", TMP)
    TMP.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(TMP)

    def check(value):
        if value is None or isinstance(value, int):
            return
        path = Path(os.fsdecode(value)).resolve()
        if path == Path("/dev/null"):
            return
        if not any(path.is_relative_to(base) for base in allowed):
            raise PermissionError("write fence refused " + str(path))

    def audit(event, args):
        if event == "open":
            path, mode, flags = args
            if (isinstance(mode, str) and any(x in mode for x in "wax+")) or \
                    flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC):
                check(path)
        elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.truncate"):
            check(args[0])
        elif event in ("os.rename", "os.symlink", "os.link"):
            check(args[0])
            check(args[1])
        elif event in ("socket.connect", "socket.bind"):
            raise PermissionError("network use is outside this study")
    sys.addaudithook(audit)
