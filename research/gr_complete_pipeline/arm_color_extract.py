"""Independent, byte-grounded read-only extraction of Ricoh ARM color stages.

Writes only gr_complete_pipeline/arm_color_analysis.json. Run python3 -I.
Firmware is read, never modified or executed.
"""
import hashlib
import importlib.util
import json
import pathlib
import struct

ROOT = pathlib.Path('/Users/wu/.t3/projects/projectricoh/research/gr_complete_pipeline')
spec = importlib.util.spec_from_file_location('arm_color_disasm', ROOT / 'arm_color_disasm.py')
dis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dis)

def unpack(fmt, data):
    return list(struct.unpack('<' + fmt, data))

def reshape(items, width):
    return [items[k:k+width] for k in range(0, len(items), width)]

def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

CONFIG = {
    'gr3': {'cm':0x55018d94, 'ma':0x55018cf0, 'satmap':0x53dc1400, 'gain':0x53dc140c, 'white':0x53dc1444, 'modes':{'Standard':11, 'Positive Film':17, 'Negative Film':25, 'Hi-Contrast B&W':16}, 'code':[(0x536deddc,0x536df13c,'ColorMatrix math'),(0x536df484,0x536e4470,'MultiAxial Calc and writer'),(0x536db7d8,0x536dc0f4,'slider dispatch'),(0x536dc474,0x536dc680,'settings fill')]},
    'gr4': {'cm':0x55053780, 'ma':0x55053504, 'satmap':0x54048498, 'gain':0x540484a4, 'white':0x540484f0, 'modes':{'Standard':11, 'Positive Film':17, 'Negative Film':24, 'Hi-Contrast B&W':16}, 'code':[(0x53914d30,0x5391506c,'ColorMatrix math'),(0x539153b4,0x5391a3a0,'MultiAxial Calc and writer'),(0x539113d8,0x53911a00,'slider dispatch'),(0x53912f70,0x53913180,'settings fill')]},
}

def extract(model):
    data, offset, read = dis.read_model(model)
    c = CONFIG[model]
    def word(va): return unpack('I', read(va,4))[0]
    def block(va, size, fmt):
        raw = read(va, size)
        return {'vma':hex(va), 'payload_offset':offset(va), 'bytes':size, 'sha256':hashlib.sha256(raw).hexdigest(), 'hex':raw.hex(), 'values':unpack(fmt,raw)}
    def matrix(va):
        b = block(va,18,'9h')
        b['Q13'] = reshape(b['values'], 3)
        b['normalized'] = reshape([n/8192 for n in b['values']], 3)
        return b
    modes = {}
    for mode, ix in c['modes'].items():
        rec = word(c['cm'] + 4*ix)
        r = block(rec,84,'21I')
        w = r['values']
        sensor = matrix(w[0])
        look = matrix(w[1])
        sat = []
        if mode != 'Hi-Contrast B&W':
            for k in range(9):
                m = matrix(word(w[2] + 4*k))
                m['array_index'] = k
                sat.append(m)
        pre = mul(look['normalized'], sensor['normalized'])
        ma_rec = word(c['ma'] + 4*ix)
        ma = block(ma_rec,24,'6I')
        mw = ma['values']
        mat_header = block(mw[2],32,'8I')
        mat_va = mat_header['values'][4]
        mat_bank = block(mat_va,2160,'540i')
        banks = [reshape(mat_bank['values'][k:k+45],9) for k in range(0,540,45)]
        ma.update({'bounds':block(mw[0],32,'16H'), 'bank_indices':block(mw[1],20,'20B'), 'matrix_pointer_array':mat_header, 'matrix_bank':mat_bank, 'banks_12_by_5_by_9':banks, 'controls':block(mw[4],42,'21H'), 'rgb_to_ycc':block(mw[5],18,'9h')})
        ma['all_five_rows_equal_within_each_bank'] = all(all(row == bank[0] for row in bank) for bank in banks)
        ma['all_banks_identity'] = all(row == [1024,0,0,0,1024,0,0,0,1024] for bank in banks for row in bank)
        toning=[]
        for k in range(11,15):
            toning.append({'record_word':k, **block(w[k],20,'10h')})
        modes[mode] = {'index':ix, 'record':r, 'sensor_ccm':sensor, 'look_matrix':look, 'saturation_array_vma':hex(w[2]), 'saturation_matrices':sat, 'sensor_then_look_float_matrix':pre, 'toning_tables':toning, 'MultiAxial':ma, 'neutral_sat_array_index':4 if sat else None, 'factory_default_sliders':None, 'factory_default_status':'未知: mode records contain transforms, not saved/default UI slider values.'}
        if model=='gr4':
            modes[mode]['variant_pointers']={k:[hex(word(c[k]+4*(34*v+ix))) for v in range(3)] for k in ['cm','ma']}
    code=[]
    for start,end,label in c['code']:
        raw=read(start,end-start)
        code.append({'label':label,'start_vma':hex(start),'end_vma_exclusive':hex(end),'payload_offset':offset(start),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    return {'source_path':dis.CONFIG[model][0], 'source_bytes':len(data), 'source_sha256':hashlib.sha256(data).hexdigest(), 'sat_index_map':block(c['satmap'],9,'9B'), 'gain_factors':block(c['gain'],34,'17H'), 'modes':modes,'code_evidence':code}

def main():
    out = {'evidence_status':'静态确认: addresses, raw bytes, integer tables, matrix call order. 推断: hardware signal order and MultiAxial pixel semantics unless explicitly grounded. 未知: factory default sliders and runtime WB/gain/exposure.', 'models':{name:extract(name) for name in CONFIG}}
    out['confirmed_findings']=[
        {'status':'静态确认','claim':'GR III ColorMatrix computes A[saturation] times look, then sensor CCM. Mono mixes precede sensor CCM. Fixed sensor CCM pointer does not depend on WB.', 'addresses':['0x536df114','0x536df130','0x536def90','0x536defd0']},
        {'status':'静态确认','claim':'GR IV computes look times sensor CCM into front matrix. Its saturation or monochrome mix goes into a distinct second matrix output at object+0x32.', 'addresses':['0x53914e74','0x53914ebc','0x53914ff8','0x53915008','0x53915024','0x53915060']},
        {'status':'推断','claim':'Forward signal convention is WB-adjusted camera RGB, fixed sensor CCM, look, MultiAxial, tone. GR IV saturation second matrix is interpreted as post-tone from separate register bank; this research did not recover ISP hardware signal routing.'},
        {'status':'静态确认','claim':'GR III SI+0x77d/77e/77f/780/781/782 and GR IV SI+0x79d/79e/79f/7a0/7a1/7a2 map to saturation/hue/key/contrast/highlight/shadow at context+0x1e0/1e2/1e4/1e6/1e8/1ea. Standard, Positive and Negative read saved values, not hard-coded mode-specific defaults.', 'addresses':['0x536db8fc','0x536dbaa4','0x536dc024','0x53911614','0x53911928']},
        {'status':'静态确认','claim':'Normal setting fill uses strength setting+0x5a=256 and falls back to gain-factor index setting+0x58=8. The gain table at index8 is128. These are runtime normal-branch values, not proof of factory image-control slider values.', 'addresses':['0x536dc608','0x536dc610','0x536dc6a8','0x53913104','0x53913108','0x53913230']},
        {'status':'静态确认','claim':'ColorMatrix gain quantization produces row sum256 for color modes in the explicit normal branch, writes coefficients clamped to signed12 bits. GR IV second color matrix at sRGB, saturation0 is diagonal512.', 'addresses':['0x536df014','0x536df03c','0x536df090','0x536df0b0','0x53914f00','0x53915008']},
        {'status':'推断','claim':'Dividing front coefficients by256 and the GR IV second matrix by512 gives grey-preserving pixel-scale candidates. Hardware pixel scaling was not directly observed.'},
        {'status':'静态确认','claim':'MultiAxial Calc normal branch reads matrix-array entry+0x10 and copies pointers only. Its unrolled writer stores all540 i32 coefficients into signed12-bit fields at register offset0x100+bank*0x80+row*0x14+element*2. All16 bounds and20 bank selectors independently match the interpreted writer.'},
        {'status':'静态确认','claim':'GR III all four modes and GR IV Negative/Hi-Contrast B&W produce identical MultiAxial register images from this normal path. Their first matrix is [420,76,16;38,458,16;38,76,398], row sum512. Thus a literal identity-matrix claim is false.'},
        {'status':'未知','claim':'Bank nibble0 bypass behavior, exact control bit5 semantics, pixel hue-coordinate formula, five-row selection/interpolation and luma-weighting arithmetic need ISP hardware semantics. Complete GR IV Positive Film pixel emulation is not established.'},
        {'status':'未知','claim':'Factory default saturation, key, contrast, highlight and shadow values are not closed. The dispatcher reads saved state. A neutral hypothesis is explicitly all signed sliders0, not an extracted default.'},
        {'status':'未知','claim':'The MakerNote0x0247 writer was not traced; correspondence of its seven signed values to the confirmed SI reader fields remains a semantic inference unless independently attributed.'}
    ]
    out['disassembly_evidence'] = [{'path':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(ROOT.glob('arm_color_*.asm.txt'))]
    (ROOT / 'arm_color_analysis.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
    for model, item in out['models'].items():
        print(model, 'sha256', item['source_sha256'], 'satmap', item['sat_index_map']['values'], 'gain',item['gain_factors']['values'])
        for mode, m in item['modes'].items():
            ma=m['MultiAxial']
            print(mode, 'record',m['record']['vma'],'sensor',m['sensor_ccm']['Q13'],'look',m['look_matrix']['Q13'])
            print('sat4',m['saturation_matrices'][4]['Q13'] if m['saturation_matrices'] else None,'toning0',[b['values'][0] for b in m['toning_tables']])
            print('ma',ma['vma'],'bounds',ma['bounds']['values'],'banks',ma['bank_indices']['values'],'controls',ma['controls']['values'],'ycc',ma['rgb_to_ycc']['values'],'identities',ma['all_banks_identity'],'rows_equal',ma['all_five_rows_equal_within_each_bank'])

if __name__ == '__main__': main()
