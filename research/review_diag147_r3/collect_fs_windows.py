"""Regenerate the file-system instruction window directly from the checked body."""
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scope
scope.enable_fence()
import collect
collect.BODY = scope.ROOT / 'firmware/package_v38_g137/local/SD_ROOT/ilaunch3'
collect.EXPECTED = {collect.OFFICIAL: 'da1980e9d6f3996ede4953b8311cf0ce2abeb4bb300b6ee60a38f38e29a3cdf7',
                    collect.BODY: 'd4fa3b46da137b8b7c7c703e66750a8249c0715271290c0fdb490a2f7a239a90'}
collect.OUT = HERE / 'local/native-listings'
collect.Image().dump(0x200a3000, 0x200bc000, 'filesystem-full')
collect.Image().dump(0x20062000, 0x20064000, 'string-memory-utils')
collect.Image().dump(0x200bc000, 0x200bd000, 'filesystem-utils')
