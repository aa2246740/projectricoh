"""Recreate all bounded evidence windows with source locations, under local/."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import LOCAL,guard,inp,dump
from static import index,calls

RANGES = (
    (0x2015df5c,0x2015e1b0),(0x2015e1b0,0x2015e29c),
    (0x2015da08,0x2015db48),(0x2015e494,0x2015e56c),(0x2015e850,0x2015e990),
    (0x200f06ac,0x200f0940),(0x200f19e0,0x200f1b00),
    (0x200f2ab8,0x200f2c48),(0x200f3490,0x200f34d8),
    (0x2015fd64,0x2015ff94),(0x201605d0,0x201606c0),(0x2016435c,0x20164388),
    (0x20171f8c,0x20171fec),(0x20171fec,0x20172050),
    (0x20172b48,0x20172c80),(0x2015f854,0x2015fb48),
    (0x2016583c,0x20165ab4),(0x20164e90,0x201655a0),
    (0x200ee244,0x200ee6c4),(0x203ed4f4,0x203ed7b0),
    (0x203f20d0,0x203f2354),(0x203f293c,0x203f29b0),(0x203f2d48,0x203f2dc4),
    (0x200fa524,0x200fa7e0),(0x203c7e5c,0x203c80b0),
    (0x2016a040,0x2016a15c),(0x2016a684,0x2016a704),
    (0x20157064,0x20157110),(0x201677d8,0x20167808),
    (0x2016ece8,0x2016f0d0),(0x20175920,0x201759c0),
    (0x20174f90,0x20175064),(0x20175064,0x201753a0),
    (0x2004bacc,0x2004bae0),(0x20088578,0x20088590),
    (0x20401fe4,0x2040202c),(0x204026f8,0x2040278c),
    (0x2005bf00,0x2005c110))


def main():
    guard();rr=index();cc=calls(rr);notes=[]
    for a,b in RANGES:
        selected=[r for r in rr if a<=r[0]<b]
        p=LOCAL/f'static/{a:08x}-{b:08x}.asm.txt';p.parent.mkdir(exist_ok=True)
        p.write_text('\n'.join(f'{r[0]:08x}: {r[1]} ; {r[2]}:{r[3]}' for r in selected)+'\n')
        notes.append({'range':[hex(a),hex(b)],'instructions':len(selected),
            'file':str(p.relative_to(LOCAL)),'calls':[c for c in cc if a<=c['address']<b]})
    for rel in ('research/grain_raw_feasibility/P1_P4.md',
        'research/grain_raw_feasibility/REPORT.md','research/stage2k_v2_design/OVERLAY.md',
        'research/phase0_drill/FLASH_AND_RECOVERY.md','research/matrix_test_onbody/REPORT.md',
        'research/calibration_20261020/REPORT.md','firmware/stage2j/build/payload.map',
        'firmware/stage2j/platform.c','firmware/stage2j/abi.S',
        'research/closed_loop/targets.py','research/closed_loop/common.py',
        'captures/a12-50/2026-10-13/photos/A1-setting1/R8051129.JPG',
        'captures/a12-50/2026-10-13/photos/A1-setting1/R8051129.DNG',
        'artifacts/downloads/fuji-luts/SHA256SUMS'):
        inp(rel)
    dump('static_windows.json',notes)
    dump('static_findings.json',{
        'native_main_Y_positions':[0,1],
        'native_generic_converter_Cb_Cr_positions':[2,3],
        'direct_K_consumer_to_converter_byte_order_contract_closed':False,
        'resize_descriptor_format_value':1,
        'jpeg_DMA_descriptor_byte16_value':1,
        'DMA_format_bitfields_authoritatively_decoded':False,
        'cache_protocol_closed':False,
        'text_draw_function_has_range_cache_call':False,
        'text_draw_bounded_addresses':['0x201605D0','0x201606C0'],
        'low_address_program_cache_leaf_copy_relation':'0x2040202C -> 0x00010000',
        'main_once_candidate':'call at 0x2015F9D8; generation guard required',
        'all_cancel_and_free_paths_closed':False,
        'isa':'big-endian M32R; not ARM or Thumb',
        'exact_core_and_frequency':'unknown',
        'frequency_budget_mhz':[50,200],
        'frequency_budget_is_not_a_measured_bound':True})
    print('saved',len(notes),'checked static windows')


if __name__=='__main__':
    main()
