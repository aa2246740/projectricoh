"""Static byte accounting and explicitly conditional software-LUT time estimates."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import struct
import csv
import runtime as rt
from runtime import np,ROOT,HERE,LOCAL

def align4(n):return (int(n)+3)&~3

def signed8(v):
    v=int(v);assert -127<=v<=127
    return 128-v if v<0 else v

def coefficient(v):
    v=int(v);assert -2047<=v<=2047
    return 2048-v if v<0 else v

def parameter_rows(p):
    q=np.asarray(p['curve_y_u8'],int)
    if len(q)==1:q=np.repeat(q,3,axis=0)
    A,B=np.asarray(p['sector_a'],int),np.asarray(p['sector_b'],int)
    cd=np.asarray(p['sector_cd'],int)
    colour=bytes(signed8(v) for row in zip(A,B,cd[0],cd[1]) for v in row)
    C=np.asarray(p['matrix_q10'],int)
    # Size accounting only. Tail words below are a signed-9-bit offset hypothesis.
    tail=np.array([0,128,128,0,0])+np.asarray(p['matrix_offset_integer_hypothesis'],int)
    words=[coefficient(v) for v in C.ravel()]+[(256-int(v) if v<0 else int(v)) for v in tail]
    assert all(0<=w<=65535 for w in words)
    one=struct.pack('>14H',*words)
    matrix=one+one  # Conservative 56B row; does not claim the second-half consumer is verified.
    inputs=struct.pack('>31H',*map(int,p['curve_x_u12'][1:-1]))
    rows=[bytes(map(int,row)) for row in q]
    assert len(inputs)==62 and all(len(row)==33 for row in rows) and len(colour)==96 and len(matrix)==56
    return [[inputs],rows,[colour],[matrix]]

def main():
    kernel=rt.read(ROOT/'research/cpu_speed_r1/evidence/kernel/summary.json')
    observed=[r['per_pair'] for r in kernel['results']]
    pairs=4288*2848//2
    peak=123_000_000
    instructions={
        'buffer_loop':12,'coordinate_extract':18,'index_and_fraction_addressing':28,
        'two_fraction_sorts':40,'vertex_loads':24,'six_channel_interpolation':60,
        'round_clip_pack':36}
    scenarios=[]
    for count in (200,sum(instructions.values()),260):
        for efficiency in (1.,.7,.35):
            for share in (1.,.5,.25,.1):
                scenarios.append(dict(label='电脑预测，条件预算',instructions_per_pair=count,
                    instruction_efficiency=efficiency,available_CPU_share=share,
                    seconds=pairs*count/(peak*efficiency*share)))
    cpu=dict(label='电脑预测，规划估算',resolution=[4288,2848],pixels=pairs*2,pairs=pairs,
        assumed_peak_instructions_per_second=peak,peak_is_user_supplied_scenario_not_verified_clock=True,
        existing_instruction_count_per_pair=dict(min=min(observed),max=max(observed)),
        existing_instruction_only_seconds=dict(min=pairs*min(observed)/peak,max=pairs*max(observed)/peak),
        optimized_budget_instructions_per_pair=instructions,optimized_budget_range=[200,260],
        optimized_instruction_only_seconds=[pairs*200/peak,pairs*260/peak],
        scenarios=scenarios,optimized_assembly_written=False,optimized_kernel_executed=False,
        firmware_built=False,physical_timing_measured=False,
        existing_kernel_already_uses=['fixed point','tetrahedral interpolation','YUV422 buffer','two luma samples per pair'],
        unknown_costs=['load-use waits','instruction fetch and LUT cache misses','DMA contention','IRQ/RTOS preemption','JPEG decode/encode','file I/O'],
        memory=dict(lut17_Q8_8=17**3*6,lut33_Q8_8=33**3*6,coordinate_table=1024,
            full_YUV422_frame=4288*2848*2,double_YUV422_frames=4288*2848*4,
            strip64_YUV422=4288*64*2,
            all_51_profiles_17cube=51*17**3*6,all_51_profiles_33cube=51*33**3*6),
        background_contract=['Own or copy the source frame until processing and JPEG completion',
            'Yield between bounded strips; preserve UI and capture task priorities',
            'Queue/backpressure/cancel policy, power-off and media-error recovery',
            'A larger DAT region does not by itself supply a 24MB image buffer'])
    rt.dump('software_lut_estimates.json',cpu)
    from gxr_studio.camdata.datcodec import parse,POOL_LENGTHS,POOL_LIMITS
    packages={
        'g154_release':ROOT/'firmware/package_v39_g154/SD_ROOT/GXRCE.DAT',
        'g155_release':ROOT/'firmware/package_v310_g155/local/SD_ROOT/GXRCE.DAT',
        'g155_test':ROOT/'firmware/package_v310_g155_test/local/SD_ROOT/GXRCE.DAT'}
    package_rows=[]
    dat155=None;raw155=None
    for name,path in packages.items():
        raw=path.read_bytes();dat=parse(raw)
        request=7628+align4(len(raw)+dat.bss)
        package_rows.append(dict(name=name,path=str(path.relative_to(ROOT)),sha256=rt.sha(path),
            dat_bytes=len(raw),code_bytes=len(dat.engine),bss_bytes=dat.bss,
            main_request_bytes=request,request_limit=107612,request_margin=107612-request,
            file_limit=98304,file_margin=98304-len(raw),effect_area_bytes=len(dat.effect_area),
            look_capacity=struct.unpack_from('>H',dat.effect_area,8)[0],
            look_count=struct.unpack_from('>H',dat.effect_area,10)[0],
            effect_bank_capacity=list(dat.effect_area[16:20]),effect_bank_used=list(dat.effect_area[20:24])))
        if name=='g155_release':dat155,raw155=dat,raw
    shared=struct.unpack_from('>I',raw155,128+12*5+4)[0]
    original_pools=[]
    for kind,size in enumerate(POOL_LENGTHS):
        count,actual_size,offset,_=struct.unpack_from('>HHII',raw155,shared+16+12*kind)
        assert actual_size==size
        original_pools.append(set(raw155[shared+offset+j*size:shared+offset+(j+1)*size] for j in range(count)))
    estimates=[];per_profile=[]
    keys=['L0','L1','L2_Y_post','L3_Y_post_add_after','L4_Y_post_add_after_Rbefore']
    for layer,key in enumerate(keys):
        pool=[set() for _ in POOL_LENGTHS];newdata=[set() for _ in POOL_LENGTHS]
        builtin_rows=[set() for _ in POOL_LENGTHS];look_rows=[set() for _ in POOL_LENGTHS]
        extras=[set(),set(),set()];profiles=0
        for meta_path in sorted(LOCAL.glob('target_[0-9][0-9].json')):
            meta=rt.read(meta_path);fitbase=LOCAL/'fits'/f'{meta["index"]:02d}'
            oldbase=LOCAL/'original_flog2/fits'/f'{meta["index"]:02d}'
            historical=meta['index'] in (31,32,39,40,47,48) and (oldbase/'L0.json').exists()
            if historical:fitbase=oldbase
            p=fitbase/(key+'.json')
            physical=p.with_name(key+'_physical.json')
            if layer==4 and physical.exists():p=physical
            full=p.with_name(key+'_fullfields.json')
            if layer>=2 and full.exists():p=full
            if not p.exists():continue
            params=rt.read(p)['parameters'];profiles+=1
            profile_rows=parameter_rows(params)
            isolated=sum(align4(len(set(rr))*size) for rr,size in zip(profile_rows,POOL_LENGTHS))
            incremental=sum(align4(len(set(rr)-old)*size) for rr,old,size in zip(profile_rows,original_pools,POOL_LENGTHS))
            additional=(24 if layer>=2 else 0)+(4 if layer>=3 else 0)+(260 if layer>=4 else 0)
            per_profile.append(dict(label='电脑参数静态计数',index=meta['index'],name=meta['name'],unit=meta.get('unit','shared-50mm-fit'),
                layer='L'+str(layer),variant=p.stem,expanded_state_bytes=[552,552,576,580,840][layer],
                target_variant='historical_FLog2_65' if historical else 'declared',
                standalone_unique_row_payload_bytes=isolated,
                row_payload_not_in_current_global_pool_bytes=incremental,
                extra_banks_aligned_bytes=additional,standalone_Look_descriptor_bytes=32,
                isolated_new_Look_data_bytes=32+isolated+additional,
                incremental_new_Look_data_bytes=32+incremental+additional,
                pool_headers_code_BSS_excluded=True))
            for kind,rows in enumerate(profile_rows):
                for row in rows:
                    pool[kind].add(row)
                    (builtin_rows if meta.get('builtin_slot') else look_rows)[kind].add(row)
                    if row not in original_pools[kind]:newdata[kind].add(row)
            if layer>=2:
                extras[0].add(struct.pack('>7H9B',*params['c120_nodes_u14'],*params['c120_gains_u8']))
            if layer>=3:
                extras[1].add(bytes(signed8(v) for v in params['c004_signed_integer']))
            if layer>=4:
                extras[2].add(struct.pack('>31H99H',*params['rlut_input_u12'][1:-1],
                    *np.asarray(params['rlut_output_u12'],int).ravel()))
        required=sum(align4(len(rows)*size) for rows,size in zip(pool,POOL_LENGTHS))
        append_bytes=sum(align4(len(rows)*size) for rows,size in zip(newdata,POOL_LENGTHS))
        extra_bytes=sum(sum(align4(len(row)) for row in rows) for rows in extras)
        global_new=[new-old for new,old in zip(builtin_rows,original_pools)]
        effect_new=[look-(old|new) for look,old,new in zip(look_rows,original_pools,builtin_rows)]
        split_payload=sum(align4(len(rows)*size) for rows,size in zip(global_new,POOL_LENGTHS))
        split_payload+=sum(align4(len(rows)*size) for rows,size in zip(effect_new,POOL_LENGTHS))
        repacked=len(raw155)-len(dat155.effect_area)+split_payload+extra_bytes+32+27*32
        # No encoded DAT is constructed. Headers, descriptors, code and BSS are extra.
        estimates.append(dict(layer=layer,key=key,profiles_seen=profiles,
            unique_rows=[len(p) for p in pool],unique_row_payload_bytes=required,
            new_rows_not_in_builtin_pool=[len(p) for p in newdata],new_row_payload_bytes=append_bytes,
            extra_bank_unique_rows=[len(p) for p in extras],extra_payload_bytes=extra_bytes,
            data_only_append_bytes=append_bytes+extra_bytes,
            split_global_new_rows=[len(p) for p in global_new],split_effect_new_rows=[len(p) for p in effect_new],
            split_pool_new_payload_bytes=split_payload,
            split_global_pool_over_limit=[len(old|new)>lim for old,new,lim in zip(original_pools,builtin_rows,POOL_LIMITS)],
            split_effect_pool_over_limit=[len(rows)>127 for rows in effect_new],
            repacked_zero_code_growth_dat_estimate=repacked,
            repacked_zero_code_growth_request_estimate=7628+align4(repacked+dat155.bss),
            old_pool_count=[len(p) for p in original_pools],pool_limits=POOL_LIMITS,
            append_exceeds_pool_limits=[len(old|new)>lim for old,new,lim in zip(original_pools,newdata,POOL_LIMITS)],
            descriptors_and_headers_excluded=True,code_and_BSS_unmeasured=True,
            matrix_second_half_is_size_assumption=True,
            current_format_supported=layer<=1))
    rt.dump('storage_costs.json',dict(packages=package_rows,payload_profiles=estimates,
        live_expanded_state_bytes=[552,552,576,580,840],
        extra_payload_definition=dict(C120=23,C004=2,RLUT=260,C040_optional=48,MCR_hypothesis=13),
        GXFX_descriptor_bytes=32,three_unit_distinct_profiles_require_individual_masks_or_owner_descriptors=True,
        format_changes_required=['C120/C004/RLUT row kinds and owning/restoring paths',
            'T1 base flags and MOUNT compatibility','full C100 offset/range validation',
            'full24 software-mask bypass','actual code/BSS/stack/IRQ link accounting before a build claim'],
        built_DAT=False))
    with (HERE/'look_payload_costs.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(per_profile[0]));writer.writeheader();writer.writerows(per_profile)
    rt.finish('costs')
    print('Static costs and conditional software time estimates written',flush=True)

if __name__=='__main__':main()
