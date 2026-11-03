"""Native menu storage spans observed at the concurrent switch boundary."""
UI_RANGES=(
    (0x2022f5a8,0x2022f5b0,'list pointer and row count'),
    (0x2022f71c,0x2022f73c,'native list state'),
    (0x2037f3bc,0x2037f3c0,'native overlay'),
    (0x205a279c,0x205a27e0,'native view array and stack publication'),
    (0x205a280c,0x205a2814,'native menu activity data'),
    (0x205a293c,0x205a2948,'native row state cache'),
    (0x205d9bf8,0x205d9c04,'native active item and constructor'),
)
def touches_ui(event):
    if event.address>=0x205d9c04:
        return False
    end=event.address+len(event.data)
    return any(event.address<hi and end>lo for lo,hi,_ in UI_RANGES)
def scope_records():
    return [dict(begin=hex(lo),end=hex(hi),purpose=name) for lo,hi,name in UI_RANGES]
