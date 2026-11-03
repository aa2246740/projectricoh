"""Synthetic complete records and independent mutations for the R4 contract."""
import copy
import hashlib
import json

SCENES = ('KEY', 'GRID_OFF', 'GRID_ON', 'INFO_OFF', 'INFO_ON',
          'JPEG_L', 'RAW_L', 'RAW_169', 'BURST', 'PLAY', 'BW')


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def profile_data():
    return dict(version=4, kind='synthetic_fixture', unit='50mm',
                identity=dict(body='1'*64, build='2'*64, abi='3'*32, dat='4'*64),
                native_rule='5'*64, mapping_proof='6'*64,
                descriptor_count=11, physical_count=99,
                qualities={name: dict(quality_id=qid, category_ids=list(range(11)),
                                     resources=[[i, 1] for i in range(11)])
                           for name, qid in (('jpeg', 1), ('raw_jpeg', 2))},
                image_sources=[0x201558a8, 0x2015eaa4],
                image_arena=[0x808bc000, 0x87f7c000],
                clock_source='native_tick_1ms', bw_pieces=32, osd_pieces=2,
                fixed_overhead=7628, session_bytes=1228,
                control_pattern='byte_index_mod256', control_crc32=2971526817,
                stride_array=0x2057828c, count_array=0x2057841c,
                matrix=0x205785ac, matrix_row_bytes=76)


def complete_records(profile):
    identity = dict(profile['identity'], boot=7, unit='50mm', unit_epoch=3)
    records = []
    for index, scene in enumerate(SCENES, 1):
        records.append(dict(scene=scene, scene_id=index, boot=7, unit='50mm', unit_epoch=3,
                            set=11, config_version=index, sequence=index,
                            complete=True, valid=1, lost=0, overwritten=0,
                            state=5, start_tick=index*1000, end_tick=index*1000+900))
    by = {r['scene']: r for r in records}

    def context(record):
        return {k: record[k] for k in ('boot', 'unit', 'unit_epoch', 'set',
                                      'scene_id', 'config_version')}

    key = by['KEY']
    key.update(after_ready=True, ready_tick=995, events=['Fn1', 'Fn2', 'half'],
               snapshots=[dict(kind=kind, sequence=i+1, context=context(key), state=5,
                               tick=1010+i*20, raw_code=code, cursor=2, cache=2,
                               view=0x2022f71c)
                          for i, (kind, code) in enumerate(
                              (('close', 0x29), ('Fn1', 0x21), ('Fn2', 0x22), ('half', 0x29)))])
    key['valid'] = 4
    for scene in ('GRID_OFF', 'GRID_ON', 'INFO_OFF', 'INFO_ON'):
        record = by[scene]
        layers = []
        for index in range(5):
            base = 0x20744a80+index*307200
            layers.append(dict(index=index, context=context(record), width=640, height=480,
                               front=base, back=base, coordinate_count=0, rectangles=[],
                               pieces=[dict(sequence=i+1, context=context(record),
                                            start_tick=record['start_tick']+10+i*10,
                                            end_tick=record['start_tick']+15+i*10,
                                            buffer=base, offset=i*153600, bytes=153600, result=0)
                                       for i in range(2)]))
        if scene == 'GRID_ON':
            layers[2]['rectangles'] = [[0, 160, 640, 1, 0, 0], [213, 0, 1, 480, 0, 0]]
        if scene == 'INFO_ON':
            layers[2]['rectangles'] = [[0, 0, 640, 55, 0, 0], [0, 427, 640, 53, 0, 0]]
        layers[2]['coordinate_count']=len(layers[2]['rectangles'])
        other = dict(quality_id=1, aspect_id=0, display_width=640, display_height=480)
        other['info_frame' if scene.startswith('GRID') else 'grid'] = 0
        record.update(palette_known=True, stable=True, overflow=0, buffer_normalized=True,
                      difference_explained=True, layers=layers,
                      pair='grid' if scene.startswith('GRID') else 'info', pair_id=1,
                      setting_value=1 if scene.endswith('ON') else 0,
                      other_settings=other)
    for scene, quality in (('JPEG_L', 'jpeg'), ('RAW_L', 'raw_jpeg')):
        record = by[scene]
        record['state'] = 56
        categories = []
        for index in range(11):
            count = 1 if index == 1 else 2
            stride = 524288 if index == 1 else 262144+32*index
            categories.append(dict(id=index, count=count, stride=stride, base=0x84000000,
                                   stride_source='native_rule' if count==1 else 'verified_adjacent',
                                   stride_raw=stride, stride_address=0x2057828c+4*index,
                                   count_address=0x2057841c+4*index,
                                   matrix_address=0x205785ac+76*index,
                                   addresses=[0x84000000+i*stride for i in range(count)]))
        expected_mask=(1 << 99)-1
        active=sum(1 << i for i in range(11))
        record.update(quality=quality, quality_id=profile['qualities'][quality]['quality_id'],
                      ycc=1, native_rule=profile['native_rule'],
                      descriptor_count=11, physical_count=99,
                      covered_mask=f'{expected_mask:032x}',
                      inactive_mask=f'{expected_mask ^ active:032x}',
                      inactive_nonzero_mask='0'*32,
                      raw_fields=dict(arena_base=0x808bc000, arena_length=0x076c0000,
                                      p_address=0x2057ac98, p_ec=0x84000000,
                                      p_f0=0x87f7bfff, p_f4=0x87f3c000, p_f8=0x87f7c000),
                      pool=dict(begin=0x84000000, end=0x87f7c000, tail=1232),
                      category_ids=list(range(11)), categories=categories,
                      resources=copy.deepcopy(profile['qualities'][quality]['resources']))
    for index, (scene, height, quality, qid, aspect) in enumerate(
        (('JPEG_L', 2848, 'jpeg', 1, 0), ('RAW_L', 2848, 'raw_jpeg', 2, 0),
         ('RAW_169', 2416, 'raw_jpeg', 2, 2))):
        record = by[scene]
        record['image'] = dict(context=context(record), sequence=index+101,
                               tick=record['start_tick']+500, state=21,
                               width=4288, height=height, stride=8576,
                               k=0x205757a4+588*index, k_life=17+index,
                               base=0x81000000, source=0x201558a8, quality=quality,
                               quality_id=qid, aspect_id=aspect, format='yuv422',
                               range=[0x81000000, 0x81000000+8576*height])
    burst = by['BURST']
    samples = []
    for index in range(3):
        sequence=104+index
        key=[7, sequence, 0x205757a4+588*index, 20+index]
        samples.append(dict(sequence=sequence, source_id=1001+index,
                            context=context(burst), h09_context=context(burst),
                            h40_context=context(burst), h41_context=context(burst),
                            h09_key=key[:], h40_key=key[:], h41_key=key[:],
                            h09=9010+100*index, h40=9030+100*index, h41=9060+100*index,
                            h40_source=0x201558a8, mapping_proof=profile['mapping_proof']))
    burst.update(valid=3, first_shot=104, last_shot=106, samples=samples)
    play = by['PLAY']
    for name, sequence, tick in (('mem_before', 1, 10010), ('mem_after', 2, 10850)):
        play[name] = dict(context=context(play), sequence=sequence,
                          phase='before_playback' if sequence==1 else 'after_playback',
                          tick=tick, region=[0x8733c000, 0x87f7c000], sample_step=256,
                          values=[0]*16)
    play['valid'] = 2
    bw = by['BW']
    bw.update(state=56, valid=96, mode='read', bytes_per_piece=262144,
              clock_source=profile['clock_source'], timebase_ms=1,
              control_range=[0x20710000, 0x20720000])
    for name, start, dt, address, size, byte_count, repeat in (
        ('read',11010,6,0x8733c000,262144,262144,1),
        ('control',11240,6,0x20710000,65536,262144,4),
        ('crc',11470,5,0x20710000,65536,65536,1)):
        bw[name+'_ticks']=[dt]*32
        bw[name+'_samples']=[dict(sequence=i+1, context=context(bw),
                                  start_tick=start+i*(dt+1), end_tick=start+i*(dt+1)+dt,
                                  source=name, range=[address,address+size],
                                  bytes=byte_count, repeats=repeat,
                                  result=2971526817 if name=='crc' else 0, check_ok=True)
                             for i in range(32)]
    return dict(schema_version=4, classification='synthetic_record_fixture_only',
                profile_sha256=hashlib.sha256(encoded(profile)).hexdigest(), identity=identity,
                frozen=True, frozen_set=11, first_sequence=1, last_sequence=11,
                allocation=dict(base=0x20708000, request=105932, bss_begin=0x2070d4cc,
                                bss_end=0x207204cc, file_bytes=20480, bss_bytes=77824,
                                fixed_overhead=7628, session_bytes=1228), records=records)


def record(doc, scene):
    return next(r for r in doc['records'] if r['scene']==scene)


def interleaved_records(doc):
    result=copy.deepcopy(doc)
    for item,times in zip(record(result,'BURST')['samples'],
                          ((9010,9120,9180),(9110,9220,9280),(9210,9320,9380))):
        item.update(zip(('h09','h40','h41'),times))
    return result


def apply_review_variant(doc, name):
    if name=='osd_pair_settings_absent':
        for scene in ('GRID_OFF','GRID_ON','INFO_OFF','INFO_ON'):
            del record(doc,scene)['other_settings']
    elif name=='grid_off_coordinates_absent':
        del record(doc,'GRID_OFF')['layers'][2]['rectangles']
    elif name=='unrecorded_extra_category':
        r=record(doc,'RAW_L')
        r['category_ids'].remove(1)
        r['categories']=[c for c in r['categories'] if c['id']!=1]
    elif name=='img_without_source_range':
        record(doc,'RAW_169')['image'].update(base=0,source=None,quality=None,range=None)
    elif name=='bw_control_and_crc_missing':
        r=record(doc,'BW')
        for key in ('control_ticks','crc_ticks','control_samples','crc_samples'):
            del r[key]
    elif name=='burst_boot_identity_mismatch':
        for sample in record(doc,'BURST')['samples']:
            for key in ('h09_key','h40_key','h41_key'):
                sample[key][0]=999
    elif name=='missing_common_record_field':
        del record(doc,'RAW_L')['complete']
    else:
        raise ValueError(name)
    return doc
