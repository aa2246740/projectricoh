#!/usr/bin/python3 -I -B
"""R4 record contract. Completeness never grants ER or H42 permission."""
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
import zlib
from functools import lru_cache

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'r5'))
from derived_contract import recalculate,schema_inventory

SCENES = ('KEY', 'GRID_OFF', 'GRID_ON', 'INFO_OFF', 'INFO_ON',
          'JPEG_L', 'RAW_L', 'RAW_169', 'BURST', 'PLAY', 'BW')
OSD_SCENES = SCENES[1:5]
U32, POS, ADDR, BYTE = ('int',0,0xffffffff), ('int',1,0xffffffff), ('int',1,0xffffffff), ('int',0,255)
TRUE, ZERO = ('literal',True), ('literal',0)

def O(**fields): return ('object',fields)
def A(item,minimum=0,maximum=4096): return ('array',item,minimum,maximum)
def E(*values): return ('enum',values)
def H(length): return ('hex',length)
def B(maximum): return ('blob',maximum)

class InvalidRecord(ValueError):
    def __init__(self,path,code):
        self.path,self.code=path,code
        super().__init__(path+': '+code)

def require(condition,path,code):
    if not condition: raise InvalidRecord(path,code)

def parse(spec,value,path):
    """All object members are mandatory. Missing data has no default value."""
    kind=spec[0]
    if kind=='object':
        require(type(value) is dict,path,'object_required')
        for key in spec[1]:
            require(key in value,path+'.'+key,'required_field_missing')
        require(set(value)==set(spec[1]),path,'unknown_field')
        return {k:parse(s,value[k],path+'.'+k) for k,s in spec[1].items()}
    if kind=='array':
        require(type(value) is list,path,'array_required')
        require(spec[2]<=len(value)<=spec[3],path,'array_length_invalid')
        return [parse(spec[1],v,f'{path}[{i}]') for i,v in enumerate(value)]
    if kind=='int':
        require(type(value) is int and spec[1]<=value<=spec[2],path,'integer_range_invalid')
    elif kind=='literal':
        require(type(value) is type(spec[1]) and value==spec[1],path,'literal_required')
    elif kind=='enum':
        require(any(type(value) is type(v) and value==v for v in spec[1]),path,'enum_invalid')
    elif kind=='hex':
        require(type(value) is str and re.fullmatch('[0-9a-f]{'+str(spec[1])+'}',value),
                path,'hex_identity_invalid')
    elif kind=='blob':
        require(type(value) is str and len(value)%2==0 and 0<len(value)<=spec[1]*2
                and re.fullmatch('[0-9a-f]+',value),path,'byte_source_invalid')
    else:
        raise RuntimeError('unknown schema rule '+kind)
    return value

UNIT=E('50mm','28mm','mount')
IDENTITY=dict(body=H(64),build=H(64),abi=H(32),dat=H(64))
CONTEXT=O(boot=POS,unit=UNIT,unit_epoch=POS,set=POS,scene_id=POS,config_version=POS)
COMMON=dict(scene=E(*SCENES),scene_id=POS,boot=POS,unit=UNIT,unit_epoch=POS,
            set=POS,config_version=POS,sequence=POS,complete=TRUE,valid=POS,
            lost=ZERO,overwritten=ZERO,state=U32,start_tick=U32,end_tick=U32)
RANGE=A(ADDR,2,2)
IMAGE=O(context=CONTEXT,sequence=POS,tick=U32,state=U32,width=POS,height=POS,stride=POS,
        k=ADDR,k_life=POS,base=ADDR,source=ADDR,quality=E('jpeg','raw_jpeg'),
        quality_id=POS,aspect_id=U32,format=E('yuv422'),range=RANGE)
KEY_SNAPSHOT=O(kind=E('close','Fn1','Fn2','half'),sequence=POS,context=CONTEXT,
               state=U32,tick=U32,raw_code=BYTE,cursor=BYTE,cache=BYTE,view=ADDR)
OSD_PIECE=O(sequence=POS,context=CONTEXT,start_tick=U32,end_tick=U32,
            buffer=ADDR,offset=U32,bytes=POS,result=U32)
LAYER=O(index=('int',0,4),context=CONTEXT,width=E(320,640),height=E(480),
        front=ADDR,back=ADDR,coordinate_count=('int',0,16),
        rectangles=A(A(U32,6,6),0,16),pieces=A(OSD_PIECE,1,128))
CATEGORY=O(id=('int',0,98),count=('int',0,18),stride=POS,base=ADDR,
           stride_source=E('native_rule','verified_adjacent'),stride_raw=POS,
           stride_address=ADDR,count_address=ADDR,matrix_address=ADDR,
           addresses=A(ADDR,0,18))
SLOT=dict(quality=E('jpeg','raw_jpeg'),quality_id=POS,ycc=E(1,2),native_rule=H(64),
          descriptor_count=POS,physical_count=POS,covered_mask=H(32),
          inactive_mask=H(32),inactive_nonzero_mask=H(32),
          raw_fields=O(arena_base=ADDR,arena_length=POS,p_address=ADDR,
                       p_ec=U32,p_f0=U32,p_f4=U32,p_f8=U32),
          pool=O(begin=ADDR,end=ADDR,tail=U32),category_ids=A(('int',0,98),1,99),
          categories=A(CATEGORY,1,99),resources=A(A(U32,2,2),1,99))
SHOT=O(sequence=POS,source_id=POS,context=CONTEXT,h09_context=CONTEXT,
       h40_context=CONTEXT,h41_context=CONTEXT,h09_key=A(POS,4,4),
       h40_key=A(POS,4,4),h41_key=A(POS,4,4),h09=U32,h40=U32,h41=U32,
       h40_source=ADDR,mapping_proof=H(64))
MEM=O(context=CONTEXT,sequence=POS,phase=E('before_playback','after_playback'),
      tick=U32,region=RANGE,sample_step=E(256),values=A(U32,16,16))
BW_PIECE=O(sequence=POS,context=CONTEXT,start_tick=U32,end_tick=U32,
           source=E('read','control','crc'),range=RANGE,bytes=POS,repeats=POS,
           result=U32,check_ok=TRUE)
QUALITY=O(quality_id=POS,category_ids=A(('int',0,98),1,99),resources=A(A(U32,2,2),1,99))
PROFILE_SCHEMA=O(version=E(4),kind=E('synthetic_fixture','sealed_native'),unit=UNIT,
                 identity=O(**IDENTITY),native_rule=H(64),mapping_proof=H(64),
                 descriptor_count=E(11),physical_count=E(99),
                 qualities=O(jpeg=QUALITY,raw_jpeg=QUALITY),image_sources=A(ADDR,1,32),
                 image_arena=RANGE,clock_source=E('native_tick_1ms'),bw_pieces=E(32),
                 osd_pieces=('int',1,128),fixed_overhead=POS,session_bytes=POS,
                 control_pattern=E('byte_index_mod256'),control_crc32=U32,
                 stride_array=ADDR,count_array=ADDR,matrix=ADDR,matrix_row_bytes=E(76))
TOP_SCHEMA=O(schema_version=E(4),classification=E('synthetic_record_fixture_only','device_capture'),
             profile_sha256=H(64),identity=O(**IDENTITY,boot=POS,unit=UNIT,unit_epoch=POS),
             frozen=TRUE,frozen_set=POS,first_sequence=POS,last_sequence=POS,
             allocation=O(base=ADDR,request=('int',1,107612),bss_begin=ADDR,bss_end=ADDR,
                          file_bytes=POS,bss_bytes=POS,fixed_overhead=POS,session_bytes=POS),
             records=A(O(),11,11))

SEGMENT=O(pattern=B(4096),repeats=POS)
SEGMENTS=A(SEGMENT,1,4096)
CAPTURE_SCHEMA=O(version=E(5),kind=E('synthetic_fixture','sealed_native'),record_sha256=H(64),
    observations=O(file_segments=SEGMENTS,bss_spans=A(RANGE,1,32),
        fixed_spans=A(RANGE,1,32),session_spans=A(RANGE,1,32),
        osd_reads=A(O(scene=E(*OSD_SCENES),layer=('int',0,4),sequence=POS,
                      source=ADDR,segments=SEGMENTS),20,2560),
        slot_scans=A(O(scene=E('JPEG_L','RAW_L'),pool_cursor=ADDR,
            rows=A(O(index=('int',0,98),count_raw=('int',0,18),stride_raw=U32,
                     base_raw=U32,matrix_words=A(U32,18,18)),99,99)),2,2),
        bw_reads=A(O(kind=E('read','control','crc'),sequence=POS,source=ADDR,
                     segments=SEGMENTS),96,96)))

def scene_schema(scene):
    fields=dict(COMMON)
    if scene=='KEY':
        fields.update(after_ready=TRUE,ready_tick=U32,events=A(E('Fn1','Fn2','half'),3,3),
                      snapshots=A(KEY_SNAPSHOT,4,4))
    elif scene in OSD_SCENES:
        others=dict(quality_id=POS,aspect_id=U32,display_width=E(640),display_height=E(480))
        others['info_frame' if scene.startswith('GRID') else 'grid']=E(0,1)
        fields.update(palette_known=TRUE,stable=TRUE,overflow=ZERO,buffer_normalized=TRUE,
                      difference_explained=TRUE,layers=A(LAYER,5,5),pair=E('grid','info'),
                      pair_id=POS,setting_value=E(0,1),other_settings=O(**others))
    elif scene in ('JPEG_L','RAW_L'): fields.update(SLOT,image=IMAGE)
    elif scene=='RAW_169': fields.update(image=IMAGE)
    elif scene=='BURST': fields.update(first_shot=POS,last_shot=POS,samples=A(SHOT,3,3))
    elif scene=='PLAY': fields.update(mem_before=MEM,mem_after=MEM)
    elif scene=='BW':
        fields.update(mode=E('read'),bytes_per_piece=E(262144),clock_source=E('native_tick_1ms'),
                      timebase_ms=E(1),control_range=RANGE)
        for kind in ('read','control','crc'):
            fields[kind+'_ticks']=A(POS,32,32)
            fields[kind+'_samples']=A(BW_PIECE,32,32)
    return O(**fields)

SCHEMA_INVENTORY=schema_inventory(sys.modules[__name__])

@dataclass(frozen=True)
class ReferenceProfile:
    digest: str
    serialized: bytes

    @property
    def data(self):
        return json.loads(self.serialized)

@dataclass(frozen=True)
class FrozenCapture:
    digest: str
    record_sha256: str
    serialized: bytes

    @property
    def data(self):return json.loads(self.serialized)

def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()

def load_profile(value,expected_sha256):
    require(type(expected_sha256) is str and re.fullmatch('[0-9a-f]{64}',expected_sha256),
            '$profile','independent_profile_hash_required')
    data=parse(PROFILE_SCHEMA,value,'$profile')
    require(hashlib.sha256(canonical(data)).hexdigest()==expected_sha256,'$profile','profile_hash_mismatch')
    require(data['image_arena'][0]<data['image_arena'][1],'$profile.image_arena','range_invalid')
    require(data['control_crc32']==zlib.crc32(bytes(range(256))*256)&0xffffffff,
            '$profile.control_crc32','derived_value_mismatch')
    for quality in data['qualities'].values():
        ids=quality['category_ids']
        require(len(ids)==len(set(ids)),'$profile.qualities','duplicate_category')
        require({d[0] for d in quality['resources']}==set(ids) and all(d[1]>0 for d in quality['resources']),
                '$profile.qualities','resource_map_incomplete')
    return ReferenceProfile(expected_sha256,canonical(data))

def load_capture(value,expected_sha256):
    require(type(expected_sha256) is str and re.fullmatch('[0-9a-f]{64}',expected_sha256),
            '$capture','independent_capture_hash_required')
    data=parse(CAPTURE_SCHEMA,value,'$capture')
    require(hashlib.sha256(canonical(data)).hexdigest()==expected_sha256,
            '$capture','capture_hash_mismatch')
    for key in ('bss_spans','fixed_spans','session_spans'):
        spans=data['observations'][key]
        require(all(start<end for start,end in spans),'$capture.'+key,'source_span_invalid')
        ordered=sorted(spans)
        require(all(a[1]<=b[0] for a,b in zip(ordered,ordered[1:])),
                '$capture.'+key,'source_spans_overlap')
    return FrozenCapture(expected_sha256,data['record_sha256'],canonical(data))

def delta(start,end): return (end-start)&0xffffffff

def tick(record,value,path):
    require(delta(record['start_tick'],value)<=delta(record['start_tick'],record['end_tick']),
            path,'tick_outside_scene')

def span(record,start,end,path,positive=False):
    tick(record,start,path);tick(record,end,path)
    require((1 if positive else 0)<=delta(start,end)<0x80000000,path,'time_interval_invalid')

def context(record,value,path):
    require(all(value[k]==record[k] for k in value),path,'scene_identity_mismatch')

def sequence(values,first,last,path):
    require(last>=first and len(values)==last-first+1 and values==list(range(first,last+1)),
            path,'sequence_not_contiguous')

def timing_interval(byte_count,ticks):
    if (type(byte_count) is not int or byte_count<=0 or type(ticks) is not list or not ticks
        or any(type(t) is not int or not 0<t<0x80000000 for t in ticks) or sum(ticks)<128):
        return None
    q,n=sum(ticks),len(ticks);lo,hi=max(0,q-n),q+n
    return dict(bytes=byte_count,samples=n,ticks=q,elapsed_ms=[lo,hi],
                bytes_per_second=[byte_count*1000/hi,byte_count*1000/lo if lo else None])

def _classify(raw,reference,capture):
    require(type(reference) is ReferenceProfile,'$profile','independent_profile_required')
    require(type(capture) is FrozenCapture,'$capture','independent_capture_required')
    try:record_digest=hashlib.sha256(canonical(raw)).hexdigest()
    except (ValueError,TypeError):raise InvalidRecord('$','json_value_invalid')
    require(record_digest==capture.record_sha256,'$capture.record_sha256','frozen_record_changed')
    profile=reference.data
    require(type(raw) is dict,'$','object_required')
    require('records' in raw,'$.records','required_field_missing')
    raw_records=raw['records']
    data=parse(TOP_SCHEMA,dict(raw,records=[{}]*11),'$')
    require(type(raw_records) is list and len(raw_records)==11,'$.records','scene_count_invalid')
    records=[]
    for index,value in enumerate(raw_records):
        path=f'$.records[{index}]'
        require(type(value) is dict and 'scene' in value,path+'.scene','required_field_missing')
        scene=parse(E(*SCENES),value['scene'],path+'.scene')
        records.append(parse(scene_schema(scene),value,path))
    data['records']=records
    require({r['scene'] for r in records}==set(SCENES),'$.records','missing_or_duplicate_scene')
    by={r['scene']:r for r in records};identity=data['identity']
    require(data['profile_sha256']==reference.digest,'$.profile_sha256','profile_identity_mismatch')
    require(all(identity[k]==profile['identity'][k] for k in IDENTITY),'$.identity','body_identity_mismatch')
    require(identity['unit']==profile['unit'],'$.identity.unit','unit_profile_mismatch')
    kind='synthetic_record_fixture_only' if profile['kind']=='synthetic_fixture' else 'device_capture'
    require(data['classification']==kind,'$.classification','capture_scope_mismatch')
    require(capture.data['kind']==profile['kind'],'$capture.kind','capture_scope_mismatch')
    sequence([r['sequence'] for r in records],data['first_sequence'],data['last_sequence'],'$.records.sequence')
    for scene in SCENES:
        r=by[scene];path='$.records.'+scene
        require(r['scene_id']==SCENES.index(scene)+1,path+'.scene_id','scene_kind_mismatch')
        require(all(r[k]==identity[k] for k in ('boot','unit','unit_epoch')) and r['set']==data['frozen_set'],
                path,'capture_identity_mismatch')
        require(0<delta(r['start_tick'],r['end_tick'])<0x80000000,path,'scene_time_invalid')
    a=data['allocation']
    require(0x20704800<=a['base']<a['base']+a['request']<=0x20744800 and a['base']%4==0,
            '$.allocation','parent_range_invalid')
    require(a['fixed_overhead']==profile['fixed_overhead'] and a['session_bytes']==profile['session_bytes']
            and a['request']==a['fixed_overhead']+((a['file_bytes']+a['bss_bytes']+3)//4)*4
            and a['bss_begin']==a['base']+a['session_bytes']+a['file_bytes']
            and a['bss_end']==a['bss_begin']+a['bss_bytes']<=a['base']+a['request'],
            '$.allocation','bss_layout_invalid')
    key=by['KEY'];snapshots=key['snapshots']
    require(key['state']==5 and key['events']==['Fn1','Fn2','half'] and key['valid']==4,
            '$.records.KEY','key_capture_incomplete')
    require([x['kind'] for x in snapshots]==['close','Fn1','Fn2','half'],
            '$.records.KEY.snapshots','key_snapshot_missing')
    sequence([x['sequence'] for x in snapshots],1,4,'$.records.KEY.snapshots')
    for x in snapshots:
        context(key,x['context'],'$.records.KEY.context');tick(key,x['tick'],'$.records.KEY.tick')
        require(x['state']==5 and delta(key['ready_tick'],x['tick'])<0x80000000,
                '$.records.KEY','key_before_ready_or_wrong_state')
    times=[delta(key['start_tick'],x['tick']) for x in snapshots]
    require(times==sorted(times),'$.records.KEY','key_time_order')
    for scene in OSD_SCENES:
        r=by[scene];path='$.records.'+scene
        require(r['state']==5 and r['valid']==1,path,'osd_snapshot_invalid')
        require(r['other_settings']['quality_id']==profile['qualities']['jpeg']['quality_id']
                and r['other_settings']['aspect_id']==0,path+'.other_settings','controlled_mode_unknown')
        require({x['index'] for x in r['layers']}==set(range(5)),path+'.layers','layer_missing')
        for layer in r['layers']:
            context(r,layer['context'],path+'.layers.context')
            require(layer['coordinate_count']==len(layer['rectangles']),
                    path+'.rectangles','coordinate_count_mismatch')
            for address in (layer['front'],layer['back']):
                require(0x20744800<=address and address+layer['width']*480<=0x208bc000,
                        path+'.layers','osd_buffer_range_invalid')
            pieces=layer['pieces']
            sequence([x['sequence'] for x in pieces],1,profile['osd_pieces'],path+'.pieces')
            require(sum(x['bytes'] for x in pieces)==layer['width']*480,path+'.pieces','osd_bytes_missing')
            next_offset=0
            previous_end=0
            for x in pieces:
                context(r,x['context'],path+'.pieces.context')
                span(r,x['start_tick'],x['end_tick'],path+'.pieces.tick')
                require(x['buffer']==layer['front'],path+'.pieces.buffer','buffer_identity_mismatch')
                require(x['offset']==next_offset,path+'.pieces.offset','osd_coverage_not_contiguous')
                require(delta(r['start_tick'],x['start_tick'])>=previous_end,
                        path+'.pieces.tick','piece_time_order_invalid')
                next_offset+=x['bytes']
                previous_end=delta(r['start_tick'],x['end_tick'])
            for x,y,w,h,color,flags in layer['rectangles']:
                require(x<layer['width'] and y<480 and 0<w<=layer['width']-x and 0<h<=480-y
                        and color<=255 and flags<=65535,path+'.rectangles','coordinate_invalid')
    for left,right,pair in (('GRID_OFF','GRID_ON','grid'),('INFO_OFF','INFO_ON','info')):
        a,b=by[left],by[right]
        require(a['pair']==b['pair']==pair and a['pair_id']==b['pair_id'] and a['setting_value']==0
                and b['setting_value']==1 and a['other_settings']==b['other_settings'],
                '$.records.'+left,'controlled_pair_invalid')
        require(delta(a['start_tick'],a['end_tick'])<=delta(a['start_tick'],b['start_tick'])<0x80000000,
                '$.records.'+left,'controlled_pair_time_order_invalid')
        left_layers=sorted(a['layers'],key=lambda x:x['index'])
        right_layers=sorted(b['layers'],key=lambda x:x['index'])
        require([(x['index'],x['width'],x['front'],x['back']) for x in left_layers]==
                [(x['index'],x['width'],x['front'],x['back']) for x in right_layers],
                '$.records.'+left,'controlled_buffer_mismatch')
        require([x['rectangles'] for x in left_layers] != [x['rectangles'] for x in right_layers],
                '$.records.'+left,'coordinate_difference_missing')
    for scene,quality in (('JPEG_L','jpeg'),('RAW_L','raw_jpeg')):
        r=by[scene];path='$.records.'+scene;rule=profile['qualities'][quality]
        require(r['quality']==quality and r['quality_id']==rule['quality_id']
                and r['native_rule']==profile['native_rule'],path,'quality_rule_mismatch')
        ids=rule['category_ids']
        require(r['category_ids']==ids and len(r['categories'])==len(ids)
                and {c['id'] for c in r['categories']}==set(ids),path,'reference_category_coverage_missing')
        require(r['resources']==rule['resources'],path+'.resources','resource_map_mismatch')
        mask=(1<<profile['physical_count'])-1;active=sum(1<<i for i in ids)
        require(r['descriptor_count']==profile['descriptor_count'] and r['physical_count']==99
                and int(r['covered_mask'],16)==mask and int(r['inactive_mask'],16)==(mask^active)
                and int(r['inactive_nonzero_mask'],16)==0,path,'physical_slot_coverage_missing')
        pool=r['pool'];words=r['raw_fields'];begin,end=pool['begin'],pool['end']
        require(profile['image_arena'][0]<=begin<end<=profile['image_arena'][1] and pool['tail']<end-begin
                and words['arena_base']==profile['image_arena'][0]
                and words['arena_length']==profile['image_arena'][1]-profile['image_arena'][0]
                and words['p_address']==0x2057ac98 and words['p_ec']==begin
                and words['p_f0']+1==end==words['p_f8']==profile['image_arena'][1]
                and words['p_f4']==words['p_f8']-0x40000,path+'.pool','pool_snapshot_invalid')
        for c in r['categories']:
            cid,count,stride=c['id'],c['count'],c['stride']
            require(stride%4==0 and c['stride_raw']==stride
                    and c['stride_address']==profile['stride_array']+4*cid
                    and c['count_address']==profile['count_array']+4*cid
                    and c['matrix_address']==profile['matrix']+profile['matrix_row_bytes']*cid,
                    path+'.categories','native_field_source_invalid')
            require(count>=2 or c['stride_source']=='native_rule',path+'.categories','single_slot_stride_unknown')
            require(c['addresses']==[c['base']+i*stride for i in range(count)]
                    and all(begin<=p and stride<=end-p for p in c['addresses']),
                    path+'.categories','slot_addresses_incomplete')
    for scene,height,quality,aspect in (('JPEG_L',2848,'jpeg',0),('RAW_L',2848,'raw_jpeg',0),
                                       ('RAW_169',2416,'raw_jpeg',2)):
        r=by[scene];image=r['image'];path='$.records.'+scene+'.image'
        context(r,image['context'],path+'.context');tick(r,image['tick'],path+'.tick')
        k,base=image['k'],image['base'];lo,hi=image['range']
        require(0x205757a4<=k<0x205757a4+18*588 and (k-0x205757a4)%588==0,path+'.k','k_slot_invalid')
        require((image['width'],image['height'],image['stride'])==(4288,height,8576)
                and image['quality']==quality and image['quality_id']==profile['qualities'][quality]['quality_id']
                and image['aspect_id']==aspect and image['source'] in profile['image_sources'],
                path,'image_source_or_mode_invalid')
        require(base%32==0 and profile['image_arena'][0]<=lo<=base<hi<=profile['image_arena'][1]
                and image['stride']*height<=hi-base,path+'.range','image_range_invalid')
    burst=by['BURST'];samples=burst['samples'];path='$.records.BURST'
    require(burst['valid']==3,path,'shot_count_invalid')
    sequence([x['sequence'] for x in samples],burst['first_shot'],burst['last_shot'],path+'.sequence')
    lifetimes=[];sources=[]
    for x in samples:
        for field in ('context','h09_context','h40_context','h41_context'):
            context(burst,x[field],path+'.'+field)
        keys=[x['h09_key'],x['h40_key'],x['h41_key']]
        require(keys[0]==keys[1]==keys[2] and keys[0][0]==identity['boot']
                and keys[0][1]==x['sequence'],path+'.keys','shot_identity_mismatch')
        k=keys[0][2]
        require(0x205757a4<=k<0x205757a4+18*588 and (k-0x205757a4)%588==0,path+'.keys','k_slot_invalid')
        require(x['mapping_proof']==profile['mapping_proof'] and x['h40_source'] in profile['image_sources'],
                path,'source_mapping_unknown')
        span(burst,x['h09'],x['h40'],path+'.h09_h40',True)
        span(burst,x['h40'],x['h41'],path+'.h40_h41',True)
        lifetimes.append(tuple(keys[0][2:]));sources.append(x['source_id'])
    require(len(set(lifetimes))==3 and len(set(sources))==3,path,'shot_source_or_lifecycle_reused')
    starts=[delta(burst['start_tick'],x['h09']) for x in samples]
    require(starts==sorted(starts),path,'shot_time_order_invalid')
    images=[by[scene]['image'] for scene in ('JPEG_L','RAW_L','RAW_169')]
    sequence([x['sequence'] for x in images]+[x['sequence'] for x in samples],
             images[0]['sequence'],burst['last_shot'],'$.records.photo_sequence')
    all_lifetimes=[(x['k'],x['k_life']) for x in images]+lifetimes
    previous={}
    for k,life in all_lifetimes:
        require(k not in previous or life>previous[k],'$.records.photo_lifecycle','k_lifecycle_reused')
        previous[k]=life
    play=by['PLAY'];before,after=play['mem_before'],play['mem_after']
    require(play['valid']==2 and before['sequence']==1 and after['sequence']==2
            and before['phase']=='before_playback' and after['phase']=='after_playback',
            '$.records.PLAY','playback_baseline_missing')
    for x in (before,after):
        context(play,x['context'],'$.records.PLAY.context');tick(play,x['tick'],'$.records.PLAY.tick')
        require(x['region']==[0x8733c000,0x87f7c000],'$.records.PLAY.region','mem_region_invalid')
    require(0<delta(before['tick'],after['tick'])<0x80000000,'$.records.PLAY','playback_time_invalid')
    bw=by['BW'];path='$.records.BW';intervals={};all_times=[]
    require(bw['valid']==3*profile['bw_pieces'] and bw['clock_source']==profile['clock_source'],
            path,'bw_sample_count_invalid')
    lo,hi=bw['control_range'];allocation=data['allocation']
    require(hi-lo==65536 and lo%4==0 and allocation['bss_begin']<=lo<hi<=allocation['bss_end'],
            path+'.control_range','control_outside_bss')
    for kind,byte_count,repeats in (('read',262144,1),('control',262144,4),('crc',65536,1)):
        pieces,ticks=bw[kind+'_samples'],bw[kind+'_ticks']
        sequence([x['sequence'] for x in pieces],1,profile['bw_pieces'],path+'.'+kind)
        measured=[]
        previous_end=0
        for x in pieces:
            context(bw,x['context'],path+'.'+kind+'.context')
            span(bw,x['start_tick'],x['end_tick'],path+'.'+kind+'.tick',True)
            measured.append(delta(x['start_tick'],x['end_tick']))
            require(delta(bw['start_tick'],x['start_tick'])>=previous_end,
                    path+'.'+kind,'piece_time_order_invalid')
            previous_end=delta(bw['start_tick'],x['end_tick'])
            require(x['source']==kind and x['bytes']==byte_count and x['repeats']==repeats,
                    path+'.'+kind,'bw_source_or_work_invalid')
            if kind=='crc':
                require(x['result']==profile['control_crc32'],path+'.crc.result','crc_result_invalid')
            start,end=x['range']
            require((kind=='read' and 0x8733c000<=start<end<=0x87f7c000 and end-start==262144)
                    or (kind!='read' and x['range']==bw['control_range']),
                    path+'.'+kind+'.range','bw_source_range_invalid')
            all_times.append((delta(bw['start_tick'],x['start_tick']),delta(bw['start_tick'],x['end_tick'])))
        interval=timing_interval(byte_count*len(pieces),ticks)
        require(ticks==measured and interval is not None,path+'.'+kind,'bw_time_invalid')
        intervals[kind]=interval
    all_times.sort()
    require(all(a[1]<=b[0] for a,b in zip(all_times,all_times[1:])),path,'bw_measurements_overlap')
    audit=recalculate(data,records,profile,capture.data['observations'],require)
    return dict(record_stage='records_complete_for_offline_review',records_complete=True,
                verdict='记录齐全，可交离线复核',reasons={},capacity='requires_native_capacity_replay',
                h43='coordinates_require_timing_review',time='to_encoder_return_only',
                read_interval=intervals['read'],control_interval=intervals['control'],crc_interval=intervals['crc'],
                er_ownership='not_established_by_diag',h42_time='requires_final_v4_measurement',
                user_budget_is_requirement_only=True,profile_sha256=reference.digest,
                recomputed_fields=len(audit),capture_sha256=capture.digest)

def incomplete(path,code):
    return dict(record_stage='undetermined',records_complete=False,verdict='不完整、不通过',
                reasons={'record':[dict(path=path,code=code)]},capacity='undetermined',h43='undetermined',
                time='undetermined',read_interval=None,control_interval=None,crc_interval=None,
                er_ownership='not_established_by_diag',h42_time='requires_final_v4_measurement',
                user_budget_is_requirement_only=True)

def classify(doc,profile=None,capture=None):
    try: return _classify(doc,profile,capture)
    except InvalidRecord as error: return incomplete(error.path,error.code)

def no_constant(value): raise InvalidRecord('$','nonfinite_json_number')

def unique_object(pairs):
    found={}
    for key,value in pairs:
        require(key not in found,'$.'+key,'duplicate_json_member')
        found[key]=value
    return found

def parse_json(text):return json.loads(text,parse_constant=no_constant,object_pairs_hook=unique_object)

def read_json(path):return parse_json(path.read_text())

@lru_cache(maxsize=32)
def profile_text(text,pin):return load_profile(parse_json(text),pin)

@lru_cache(maxsize=32)
def capture_text(text,pin):return load_capture(parse_json(text),pin)

def validate_text(text,profile,capture):
    """The public text boundary binds the exact frozen canonical JSON bytes."""
    try:
        require(type(capture) is FrozenCapture,'$capture','independent_capture_required')
        require(hashlib.sha256(text.encode()).hexdigest()==capture.record_sha256,
                '$capture.record_sha256','frozen_record_changed')
        return classify(parse_json(text),profile,capture)
    except (InvalidRecord,json.JSONDecodeError,UnicodeError) as error:
        return incomplete(error.path,error.code) if isinstance(error,InvalidRecord) else incomplete('$','json_or_file_invalid')

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('records',type=Path)
    parser.add_argument('--profile',required=True,type=Path)
    parser.add_argument('--profile-sha256',required=True)
    parser.add_argument('--capture',required=True,type=Path)
    parser.add_argument('--capture-sha256',required=True)
    args=parser.parse_args(argv)
    try:
        profile=profile_text(args.profile.read_text(),args.profile_sha256)
        capture=capture_text(args.capture.read_text(),args.capture_sha256)
        content=sys.stdin.read() if str(args.records)=='-' else args.records.read_text()
        result=validate_text(content,profile,capture)
    except (InvalidRecord,json.JSONDecodeError,OSError,UnicodeError) as error:
        result=incomplete(error.path,error.code) if isinstance(error,InvalidRecord) else incomplete('$','json_or_file_invalid')
    print(json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2))
    return 0 if result['records_complete'] else 2

if __name__=='__main__': raise SystemExit(main())
