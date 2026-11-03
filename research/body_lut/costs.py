"""Explicit design assumptions, not a target-CPU benchmark."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import guard,dump


def main():
    guard()
    pixels=4288*2848;pairs=pixels//2
    rows=[]
    for n in (9,17,33):
        rows.append({'n':n,'nodes':n**3,'uint8_bytes':3*n**3,'q8_8_bytes':6*n**3,
            'four_slots_q8_8_bytes':24*n**3})
    report={'evidence':'hand operation budget and parameter sensitivity; not measured camera time',
        'pixels':pixels,'pairs':pairs,'image_bytes':pixels*2,'image_read_write_bytes':pixels*4,
        'tetra_pair':{'dynamic_instructions':[170,230],
            'integer_multiply':18,'node_halfword_loads':24,'coordinate_word_loads':4,
            'input_word_loads':1,'output_word_stores':1,
            'logical_bytes_no_spills':72,'logical_frame_bytes_no_spills':pairs*72,
            'ALU_and_address_cycles':[110,120], 'multiply_latency':[1,4],
            'load_latency':[2,30], 'branch_and_spill_cycles':[32,108],
            'assumed_total_cycles_per_pair':[220,1200]},
        'frequency_mhz_is_unknown':True,'illustrative_frequency_mhz':[25,50,100,200,300],
        'tables':rows,'coordinate_lut_bytes':1024,'18_slot_state_plus_header_bytes':496,
        'time_seconds':{str(mhz):[pairs*c/(mhz*1e6) for c in (220,1200)] for mhz in (25,50,100,200,300)},
        'separable_pair_cycles_assumption':[80,240],
        'separable_time_seconds':{str(mhz):[pairs*c/(mhz*1e6) for c in (80,240)] for mhz in (50,100,200)},
        'code_budget_bytes':{
            'M32R_actual_target':{'pixel_loop':[640,1152],'guards_generation_lifecycle':[400,800],
                'table_file_and_format':[320,640],'native_ABI_and_cache':[160,352],
                'resident_dispatch_and_loader':[664,1068],'total':[2184,4012]},
            'ARM_A32_counterfactual_not_executable_on_GXR':{'total':[3000,5200]},
            'Thumb2_counterfactual_not_executable_on_GXR':{'total':[2200,4200]},
            'Thumb1_counterfactual_not_executable_on_GXR':{'total':[2800,5000]}},
        'known_payload_bytes':284,'known_max_contiguous_bytes':256,'heap_total_bytes':262144,
        'estimated_existing_2j_heap_bytes':7176,
        'heap_request_17_four_slots_with_4096_code':6*17**3*4+1520+4096+7176,
        'heap_request_33_one_slot_with_4096_code':6*33**3+1520+4096+7176,
        'no_allocator_overhead_or_fragmentation_in_heap_sums':True}
    dump('costs.json',report)
    print({n:report['time_seconds'][str(n)] for n in (50,100,200)})


if __name__=='__main__':
    main()
