"""GR IV index16 descriptor, its channel LUT, and isolated integer composition.

The interpreter executes a bounded arithmetic model in synthetic memory. It
does not execute firmware on a CPU, connect a camera or emulate the ISP.
"""
import struct
import subprocess
from common import HERE, PIPE, module, record, sha

gamma = module('hc_gamma_model', PIPE/'arm_gamma_model.py')
checker = module('hc_color_checker', PIPE/'arm_color_math_check.py')
pmath = module('hc_projection', PIPE/'pipeline_math.py')


def original_block(model,address,count,fmt):
    raw = gamma.inspect.read(model,address,count*struct.calcsize(fmt))
    return {**record(struct.unpack('<'+fmt*count,raw),fmt,'<'),
            'model':model,'vma':hex(address),'payload_offset':hex(gamma.inspect.offset(model,address))}


def compose(base,channel):
    result=[]
    for value in base:
        i,frac=value>>6,value&63
        result.append(channel[255] if i>254 else channel[i]+(channel[i+1]-channel[i])*frac//64)
    return result


def inspect():
    root=0x55053138
    variants=[gamma.inspect.u32('gr4',root+4*(v*34+16)) for v in range(3)]
    if len(set(variants))!=1:
        raise ValueError('GR IV HC variants no longer share descriptor')
    desc=original_block('gr4',variants[0],5,'I')
    base_ptr,flags,r,g,b=desc['values']
    if flags!=1 or len({r,g,b})!=1:
        raise ValueError('Unexpected native HC descriptor')
    channel=original_block('gr4',r,256,'H')
    common=original_block('gr4',base_ptr+8,256,'H')
    cases=[]
    for gain in [8192,11222]:
        base=gamma.effective_curve('gr4',key=0,contrast=0,highlight=0,shadow=0,gain=gain,flag=0)
        expected=compose(base,channel['values'])
        m=checker.ColorA32('gr4');obj,settings=0x61000000,0x61009000
        for i,value in enumerate(base):m.write(obj+2*i,2,value)
        m.write(obj+0x3809,1,1)
        m.write(settings+0x14,4,variants[0])
        m.reg[0],m.reg[1],m.reg[15]=obj,settings,0x5391E340
        m.allowed=[(0x5391E340,0x5391E9B0)]
        m.run()
        outputs=[[m.read(obj+off+2*i,2) for i in range(256)] for off in [0x3008,0x3208,0x3408,0x3608]]
        if not all(v==expected for v in outputs):
            raise ValueError('Isolated original composition differs from independent integer formula')
        cases.append({'numeric_state':{'key':0,'contrast':0,'highlight':0,'shadow':0,'gain':gain,'flag':0},
                      'GRIV_factory_defaults_verified':False,
                      'GammaTuning_common256_u16LE':record(base,'H','<'),
                      'HC_composed256_u16LE':record(expected,'H','<'),
                      'type26_projection':pmath.project_curve(expected,8),
                      'isolated_A32_steps':m.steps,'all_three_channels_and_luma_match_independent_formula':True,
                      'full_camera_HC_effect':False})
    directory=HERE/'arm_analysis';directory.mkdir(exist_ok=True)
    evidence=[]
    for model,start,end in [('gr4',0x5391E340,0x5391E9B0),('gr4',0x53925FE0,0x53926064),
                             ('gr3',0x536E84C8,0x536E8660)]:
        binary=gamma.inspect.read(model,start,end-start)
        path=directory/f'{model}-{start:08x}.elf'
        gamma.inspect.elf_text(binary,start,path)
        assembly=subprocess.run(['/usr/bin/objdump','-d','--triple=armv7-none-eabi',str(path)],
                                check=True,capture_output=True,text=True).stdout
        textpath=path.with_suffix('.asm.txt');textpath.write_text(assembly)
        evidence.append({'model':model,'vma':hex(start),'bytes':len(binary),'sha256':sha(binary),
                         'assembly':str(textpath.relative_to(HERE)),'wrapper_kind':'ET_REL, analysis only'})
    return {'GRIV_index16':{'gamma_table_root':hex(root),'variant_descriptor_pointers':list(map(hex,variants)),
                'descriptor':desc,'shared_base_curve':common,'HC_channel_curve':channel,
                'channel_override_flag_is_set':True,'all_three_native_channel_pointers_are_equal':True,
                'normal_path_composition_function':'0x5391e340',
                'observed_arithmetic':'i=G>>6, frac=G&63; L[i]+trunc0((L[i+1]-L[i])*frac/64), clamp i>254 to L[255]',
                'curve_input_grid':'64*k in u14 domain; not a second direct 12-bit sensor input curve',
                'luma_weights_in_curve_composer':[77,150,29], 'luma_divisor':256,
                'cases':cases,'not_a_complete_HC_renderer':True},
            'GRIII':{'entry_GammaTuning':'0x536e7b64','parameter_wrapper':'0x536e84c8',
                'common_zero_slider_curve_is_not_complete_HC_response':True,
                'mode16_additional_effective_tone_path':'NOT_CLOSED',
                'GRIIIx_selected_component_parity_source':'../gr_complete_pipeline/gr3x_selected_code_parity.json',
                'GRIIIx_full_HC_pipeline_parity_verified':False},
            'evidence':evidence,'camera_execution':False}
