"""Check linked limits and contiguous native-model startup allocations."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import *

def main():
    layout=json.loads((TREE/'candidate/local/full-r13/layout.json').read_text())
    assert len(DAT.read_bytes())==layout['file_bytes']<=98304
    assert layout['engine_bytes']<=65536
    assert layout['file_bytes']+layout['bss_bytes']<=114688
    units={}
    for unit in ('50mm','28mm','mount'):
        path=OUT/'local/nested'/(unit+'-list-before_redraw-right.json')
        value=json.loads(path.read_text())
        assert value['dat_sha256']==sha(DAT.read_bytes()) and value['status'].startswith('PASS')
        root=value['cold']['root']
        loader=root['block']-12-root['heap_begin']
        assert root['block']+root['block_bytes']==root['ui_block']-12
        total=loader+root['alloc_bytes']+root['ui_alloc_bytes']
        assert total==root['ui_block']-12+root['ui_alloc_bytes']-root['heap_begin']
        capacity=root['heap_end']-root['heap_begin']
        assert 0<total<capacity
        units[unit]=dict(record=str(path.relative_to(ROOT)),loader_workspace_with_header=loader,
                        engine_with_header=root['alloc_bytes'],UI_with_header=root['ui_alloc_bytes'],
                        model_startup_bytes=total,model_heap_capacity=capacity,remaining=capacity-total)
    save('evidence/memory-budget.json',dict(status='PASS',dat_sha256=sha(DAT.read_bytes()),
         file_bytes=layout['file_bytes'],engine_bytes=layout['engine_bytes'],bss_bytes=layout['bss_bytes'],
         image_plus_BSS=layout['file_bytes']+layout['bss_bytes'],units=units,
         scope='Linked size limits and observed contiguous loader/main/UI allocations in the native host model. Excludes unrelated camera allocations; no RTOS stack or physical heap high-water claim.'))
    print('PASS sizes and model startup allocations',units)

if __name__=='__main__':main()
