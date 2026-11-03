"""Additional native helper listings, extracted from the frozen body image."""
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import scope
import m32r_listing
raw = (scope.ROOT/'firmware/package_v38_g137/local/SD_ROOT/ilaunch3').read_bytes()
windows = {
    'directory-search':(0x200b62a8,0x200b6740),
    'directory-cache':(0x200b86ec,0x200b8890),
    'directory-work':(0x200b8b40,0x200b8d00),
    'ascii-core':(0x201d330c,0x201d36e0),
    'read-geometry':(0x200b3af8,0x200b3e80),
}
for name,(start,end) in windows.items():
    (HERE/'focused-listings'/(name+'.txt')).write_text(m32r_listing.dis(raw,start,end)+'\n')
print('FOCUSED_LISTINGS_DONE',len(windows))
