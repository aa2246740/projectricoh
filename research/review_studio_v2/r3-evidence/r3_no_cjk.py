"""Process-local simulation: neither product CJK lookup nor tests may see system CJK files."""
from pathlib import Path

def pytest_sessionstart(session):
    from gxr_studio.finish import stamp
    stamp._CJK_FONTS = ()
    original = Path.is_file
    def is_file(path):
        if str(path).startswith('/System/Library/Fonts/'):
            return False
        return original(path)
    Path.is_file = is_file
