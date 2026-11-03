"""Verify the named APFS workspace before any output is opened."""
from pathlib import Path
import plistlib
import subprocess
import sys


def guard():
    volume = Path("/Volumes/Workspace")
    if sys.platform != "darwin" or not volume.is_mount():
        raise RuntimeError("the authorized macOS Workspace volume is not mounted")
    info = plistlib.loads(subprocess.check_output(["/usr/sbin/diskutil", "info", "-plist", str(volume)]))
    if not (info.get("FilesystemType") == "apfs" and
            info.get("VolumeUUID", "").upper() == "14BE04EB-AF49-497E-B36A-B078B2F7C5E8" and
            info.get("WritableVolume") and info.get("WritableMedia")):
        raise RuntimeError("Workspace volume identity, filesystem or write permission mismatch")
