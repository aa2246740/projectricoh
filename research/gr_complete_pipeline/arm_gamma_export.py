"""Export default-mode gamma reconstruction and source-bound verification records."""
from pathlib import Path
import importlib.util, struct, hashlib, json
ROOT=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('g',ROOT/'arm_gamma_model.py');g=importlib.util.module_from_spec(sp);sp.loader.exec_module(g)
sha=lambda b:hashlib.sha256(b).hexdigest()
def block(model,va,size,meaning):
 b=g.inspect.read(model,va,size)
 return {'model':model,'vma':hex(va),'file_offset':hex(g.inspect.offset(model,va)),'size':size,'sha256':sha(b),'bytes_hex':b.hex(),'meaning':meaning}
def ref(name,p,gain,model,kind):
 a,details=g.effective_curve(model,**p,gain=gain,flag=0,details=True)
 return {'id':f'{model}-{name}-gain{gain}','mode':name,'model':model,'evidence_level':'静态确认' if kind=='gr3-initialization-default-parameters' else '推断','state_kind':kind,'sliders':p,'runtime_gain':gain,'runtime_gain_source':'explicit controlled state; the original photograph\'s runtime gain is unknown','flag':0,'curve_u16_256':a,'sha256_u16le':sha(struct.pack('<256H',*a)),**details}
init=json.loads((ROOT/'arm_gamma_gr3_defaults.json').read_text())
modes={
 'Standard':{'index_gr3':11,'index_gr4':11,'sliders':{'key':0,'contrast':0,'highlight':0,'shadow':0}},
 'PositiveFilm':{'index_gr3':17,'index_gr4':17,'sliders':{'key':-1,'contrast':3,'highlight':-1,'shadow':-2}},
 'NegativeFilm':{'index_gr3':25,'index_gr3_runtime_ui':22,'index_gr4':24,'sliders':{'key':1,'contrast':1,'highlight':0,'shadow':-1}},
 'HighContrastBW':{'index_gr3':16,'index_gr4':16,'sliders':{'key':0,'contrast':0,'highlight':0,'shadow':0}},
}
source=[]
for model in ['gr3','gr4']:
 c=g.MODELS[model];t=g.tables(model)
 source.extend([block(model,c['entry'],c['end']-c['entry'],'isolated GammaTuning builder body before literal pool'),block(model,c['key'],36,'signed-key lookup'),block(model,c['smoothing'],194,'97x u16 transition smoothing'),block(model,c['unit'],2,'normalization/anchor base unit')])
 source.append(block(model,c['families'],12,'three-family pointer root table'))
 for fam in range(3):
  source.append(block(model,g.inspect.u32(model,c['families']+4*fam),20,f'five band pointers for family {fam}'))
  for band in range(5):source.append(block(model,t['pointers'][fam][band],512,f'base family {fam} band {band}'))
source.extend([block('gr3',0x5323f424,0x12d8,'named property initialization-default constructor'),block('gr3',0x536e82c8,8,'builder literal pool'),block('gr4',0x5391e238,8,'builder literal pool'),block('gr3',0x538f3504,24,'initial family and blend weight arrays'),block('gr4',0x53b4d668,24,'initial family and blend weight arrays'),block('gr3',0x536db7d8,0x94,'runtime image-control dispatch'),block('gr3',0x536dc280,0x4c,'negative22 maps table25; look-specific tables'),block('gr3',0x536e84cc,0x9c,'settings to signed gamma args'),block('gr3',0x536dc644,0x34,'runtime gain producer'),block('gr4',0x53913148,0x28,'runtime gain producer'),block('gr4',0x5391e240,0x94,'settings to gamma args; flag explicitly zero'),block('gr3',0x536e8a90,0x58,'gamma initial cache neutral/gain8192, not shot default')])
records=[]
for model in ['gr3','gr4']:
 for name,m in modes.items():
  for gain in [8192,11222]:records.append(ref(name,m['sliders'],gain,model,'gr3-initialization-default-parameters' if model=='gr3' else 'explicit-GRIII-default-slider-state-projected-into-GRIV-algorithm'))
rawsources={model:{'path':g.inspect.MODELS[model]['path'],'sha256':sha(g.inspect.image(model)),'size':len(g.inspect.image(model)),'bias':hex(g.inspect.MODELS[model]['bias']),'data_source':hex(g.inspect.MODELS[model]['data_source'])} for model in ['gr3','gr4']}
formula={
 'input':'key, contrast, highlight, shadow in -4..4; runtime gain is low16 of a shot context value; flag is explicit',
 'key_lookup':g.tables('gr3')['keys'],
 'knee':'clamp(128,2048, (gain * trunc(key_table[key+4]*(flag?256:512)/256)) >>13)',
 'region_order':['highlight','mid','shadow'],
 'region_contrast':'clamp(-12,12,2*contrast + [highlight,0,-shadow][region])',
 'family_weight':'positive contrast blend family0/high and family1/normal by floor(k*512/12); nonpositive blend family1/normal and family2/low by floor((k+12)*512/12)',
 'band_selection':'white bands knee [128..255],[256..511],[512..1023],[1024..2048], choose adjacent 0/1,1/2,2/3,3/4; knee sample is floor(knee/16)',
 'band_anchor':'anchor=unit64*118=7552. Per region family-mix two band values at knee; lower-band weight floor((7552-high)*512/(low-high)), with observed branch rules for invalid/inverted/above-anchor intervals.',
 'fixedpoint_rounding':'every family and band blend uses (a*w+b*(512-w)+256)>>9',
 'transition':'mid curve near knee. At x>knee high-range weight S[clamp(0,96,floor(32*x/knee)-32)]/2048; at x<knee shadow-range weight S[clamp(0,96,floor(32*knee/x)-32)]/2048; >=4*knee or <=knee/4 is full range curve. Round +1024 then >>11.',
 'final':'min(16384, floor(y*16384/0x3f02)); samples x=16*i, i0..255. The final node is x4080, not4095.',
 'mode_dependence':'No look/mode index enters GammaTuning. Mode-specific defaults supply different slider values before this common arithmetic.',
 'gr4_vs_gr3':'All15 basecurve byte arrays, key lookup, smoothing, unit are identical; instruction body has only relocatable constant/call target changes.'}
comparison=[]
a,b=g.inspect.read('gr3',g.MODELS['gr3']['entry'],0x764),g.inspect.read('gr4',g.MODELS['gr4']['entry'],0x764)
for o in range(0,len(a),4):
 wa,wb=struct.unpack_from('<I',a,o)[0],struct.unpack_from('<I',b,o)[0]
 if wa!=wb:comparison.append({'relative_offset':hex(o),'gr3_vma':hex(g.MODELS['gr3']['entry']+o),'gr4_vma':hex(g.MODELS['gr4']['entry']+o),'gr3_word':f'{wa:08x}','gr4_word':f'{wb:08x}'})
for name,m in modes.items():
 m['gr3_initialization_defaults']={'evidence_level':'静态确认','saturation':0 if name!='HighContrastBW' else None,'hue':0 if name!='HighContrastBW' else None,**m['sliders'],'sharpness':1 if name=='HighContrastBW' else 0,'source':'arm_gamma_gr3_defaults.json'}
 m['gr4_initialization_defaults']=None
 m['gr3_default_gain']=None;m['gr4_default_gain']=None
out={'schema_version':1,'status':'PARTIAL_PIPELINE_CLOSED_GAMMA_AND_GRIII_INITIALIZATION_DEFAULTS','evidence_labels':{'静态确认':'original firmware bytes, named property chains and deterministic arithmetic','推断':'controlled parameter states or semantic interpretations, no camera execution','未知':'not established; represented as null'},'raw_sources':rawsources,'modes':modes,'formula':formula,'cross_generation':{'all15basecurves_identical':g.tables('gr3')['curves']==g.tables('gr4')['curves'],'keys_identical':g.tables('gr3')['keys']==g.tables('gr4')['keys'],'smoothing_identical':g.tables('gr3')['smoothing']==g.tables('gr4')['smoothing'],'builder_bytes':0x764,'different_words':comparison},'effective_curves':records,'source_blocks':source,'gr3_initialization_default_field_chain':init,'math_verification':'arm_gamma_math_verification.json','unknowns':{'gr4_mode_initialization_default_sliders':None,'actual_reference_runtime_gains':None,'full_live_GammaTuning_pipeline_including_tonecontrol':None,'HiContrastBW_filter_toning_localprocessing_effectivecurve':None},'warnings':['8192 is observed on gamma-object initial neutral cache; it is not established as every shot gain.','11222 is a shared nuisance gain fitted by the parent forward-model evaluation; the firmware does not encode this as a mode default.','Same gamma curve for GRIII Standard and HighContrastBW does not establish the same final pixel function. Monochrome and local tone stages remain separate.','GRIV controlled curves use explicitly specified GRIII default sliders. GRIV factory default fields remain unknown.','No camera, SD or host firmware execution was performed; restricted A32 integer replay is synthetic arithmetic checking.']}
(ROOT/'gr3_gr4_effective_curves.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print({'curves':len(records),'source_blocks':len(source),'raw_sources':rawsources,'different_builder_words':len(comparison)})
