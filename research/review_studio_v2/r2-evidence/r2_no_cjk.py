"""Host simulation of CI without the macOS font paths; product source unchanged."""
def pytest_sessionstart(session):
    from gxr_studio.finish import stamp
    stamp._CJK_FONTS = ()
