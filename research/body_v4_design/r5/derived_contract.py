"""Recompute record claims from entries and independently frozen observations."""
import hashlib
import json
import zlib
from functools import lru_cache

SUCCESS_UNITS = {
    'KEY': ('snapshots',),
    'GRID_OFF': ('layers_snapshot',), 'GRID_ON': ('layers_snapshot',),
    'INFO_OFF': ('layers_snapshot',), 'INFO_ON': ('layers_snapshot',),
    'JPEG_L': ('image',), 'RAW_L': ('image',), 'RAW_169': ('image',),
    'BURST': ('samples',), 'PLAY': ('mem_before', 'mem_after'),
    'BW': ('read_samples', 'control_samples', 'crc_samples'),
}
REQUIRED_UNITS = dict(KEY=4,GRID_OFF=1,GRID_ON=1,INFO_OFF=1,INFO_ON=1,
                      JPEG_L=1,RAW_L=1,RAW_169=1,BURST=3,PLAY=2,BW=96)

# Every field name must have an explicit origin. A new schema member cannot
# silently become a raw observation, including a newly added count or checksum.
DERIVED_NAMES = frozenset('valid first_sequence last_sequence first_shot last_shot '
    'coordinate_count count descriptor_count physical_count covered_mask inactive_mask '
    'inactive_nonzero_mask arena_length begin end tail file_bytes bss_bytes fixed_overhead '
    'session_bytes request bss_begin bss_end stride_address count_address matrix_address '
    'offset bytes bytes_per_piece read_ticks control_ticks crc_ticks result check_ok '
    'profile_sha256 stride frozen complete lost overwritten overflow events after_ready'.split())
RAW_NAMES = frozenset('body build abi dat boot unit unit_epoch frozen_set base '
    'state start_tick end_tick ready_tick tick raw_code cursor cache view front back '
    'width height rectangles stride_raw stride_source addresses source quality_id '
    'aspect_id k k_life format range source_id h09 h40 h41 h40_source region values '
    'p_address p_ec p_f0 p_f4 p_f8 arena_base ycc config_version pair_id setting_value '
    'grid info_frame palette_known stable buffer_normalized difference_explained '
    'control_range'.split())
BOUND_NAMES = frozenset('schema_version classification '
    'kind index pair quality native_rule category_ids resources '
    'sequence scene scene_id set context identity allocation records snapshots layers '
    'pieces categories raw_fields pool image samples h09_context h40_context h41_context '
    'h09_key h40_key h41_key mapping_proof mem_before mem_after phase sample_step '
    'id mode clock_source timebase_ms repeats other_settings read_samples '
    'control_samples crc_samples display_width display_height buffer'.split())


def schema_inventory(gate):
    assert set(SUCCESS_UNITS) == set(gate.SCENES)
    assert set(REQUIRED_UNITS) == set(gate.SCENES)
    groups = (DERIVED_NAMES, RAW_NAMES, BOUND_NAMES)
    assert not any(a & b for i, a in enumerate(groups) for b in groups[i+1:])
    rows = []
    def walk(spec, path):
        kind = spec[0]
        if kind == 'object':
            for key, child in spec[1].items():
                roles = [name for name, names in zip(('derived', 'observed', 'bound'), groups) if key in names]
                assert len(roles) == 1, ('field_origin_not_declared', path, key)
                if '.categories[' in path and key in ('base','addresses','stride_raw'):roles=['derived']
                rows.append(dict(path=path+'.'+key, origin=roles[0], type=child[0]))
                walk(child, path+'.'+key)
        elif kind == 'array': walk(spec[1], path+'[*]')
    walk(gate.TOP_SCHEMA, '$')
    for scene in gate.SCENES: walk(gate.scene_schema(scene), '$.records['+scene+']')
    return rows


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()


def source_bytes(segments, require, path):
    total = 0
    key = []
    for item in segments:
        pattern = bytes.fromhex(item['pattern'])
        size = len(pattern)*item['repeats']
        require(size <= 262144 and total+size <= 262144, path, 'source_work_too_large')
        total += size
        key.append((item['pattern'], item['repeats']))
    return expanded(tuple(key))


@lru_cache(maxsize=128)
def expanded(key):
    return b''.join(bytes.fromhex(pattern)*count for pattern,count in key)


def xor_words(data, require, path):
    require(len(data) % 4 == 0, path, 'unaligned_source_bytes')
    return xor_value(data)


@lru_cache(maxsize=128)
def xor_value(data):
    # XOR of equally positioned bytes gives the same uint32 result as the
    # specified little-endian word loop; zero/nonzero and comparisons are exact.
    out = bytearray(4)
    for i in range(4):
        value = 0
        for byte in data[i::4]: value ^= byte
        out[i] = value
    return int.from_bytes(out, 'little')


def recalculate(data, records, profile, observations, require):
    """No claimed count is an operand for another count or sequence range."""
    audit = []
    locations = {}
    expected_paths = set()
    def locate(value, path):
        if type(value) is dict:
            locations[id(value)] = path
            for key, item in value.items():
                if key in DERIVED_NAMES or ('.categories[' in path and key in ('base','addresses','stride_raw')):
                    expected_paths.add(path+'.'+key)
                locate(item,path+'.'+key)
        elif type(value) is list:
            for i,item in enumerate(value):locate(item,path+'['+str(i)+']')
    locate(data,'$')
    def eq(actual, expected, path, formula, sources):
        require(type(actual) is type(expected) and actual == expected, path, 'derived_value_mismatch')
        audit.append(dict(path=path, formula=formula, sources=sources, recomputed=expected))
    def claim(obj, key, expected, path, formula, sources):
        eq(obj[key], expected, locations[id(obj)]+'.'+key, formula, sources)
    def span_bytes(spans): return sum(end-start for start, end in spans)
    by = {r['scene']: r for r in records}
    claim(data, 'profile_sha256', hashlib.sha256(canonical_bytes(profile)).hexdigest(), '$',
          'SHA256(canonical independent reference)', ['$profile'])
    claim(data, 'first_sequence', records[0]['sequence'], '$', 'first saved record sequence', ['records[0].sequence'])
    claim(data, 'last_sequence', records[-1]['sequence'], '$', 'last saved record sequence', ['records[-1].sequence'])
    completed=[]
    for record in records:
        scene = record['scene']; path = '$.records['+scene+']'
        count = 0
        for field in SUCCESS_UNITS[scene]:
            if field == 'layers_snapshot': count += 1  # one complete five-layer capture
            elif type(record[field]) is list: count += len(record[field])
            else: count += 1
        claim(record, 'valid', count, path, 'number of saved success units', list(SUCCESS_UNITS[scene]))
        needed=REQUIRED_UNITS[scene]
        if scene=='KEY':keys=[(x['kind'],x['sequence']) for x in record['snapshots']]
        elif scene in gate_osd_scenes():keys=[scene]
        elif scene in ('JPEG_L','RAW_L','RAW_169'):
            x=record['image'];keys=[(x['sequence'],x['k'],x['k_life'])]
        elif scene=='BURST':keys=[tuple(x['h09_key']) for x in record['samples']]
        elif scene=='PLAY':keys=[(record[k]['phase'],record[k]['sequence']) for k in ('mem_before','mem_after')]
        else:keys=[(kind,x['sequence']) for kind in ('read','control','crc') for x in record[kind+'_samples']]
        missing=max(0,needed-count);duplicates=count-len(set(keys))
        completed.append(count==needed and missing==duplicates==0)
        for key,value in (('lost',missing),('overwritten',duplicates),('complete',count==needed and missing==duplicates==0)):
            claim(record,key,value,path,'required success units minus saved units; duplicate saved identities',list(SUCCESS_UNITS[scene]))
        if scene in gate_osd_scenes():
            claim(record,'overflow',sum(max(0,len(layer['rectangles'])-16) for layer in record['layers']),
                  path,'candidate count beyond fixed per-layer capacity',['layers.rectangles'])
    claim(data,'frozen',all(completed),'$',
          'all required scenes validated against one independently frozen capture',['records','$capture'])
    key=by['KEY']
    claim(key,'events',[x['kind'] for x in key['snapshots'][1:]],'$.records[KEY]',
          'saved post-close event kinds',['snapshots'])
    claim(key,'after_ready',all(((x['tick']-key['ready_tick'])&0xffffffff)<0x80000000 for x in key['snapshots']),
          '$.records[KEY]','every saved event follows READY',['snapshots.tick','ready_tick'])
    a = data['allocation']; aux = observations
    file_size = len(source_bytes(aux['file_segments'], require, '$capture.file_segments'))
    bss_size = span_bytes(aux['bss_spans'])
    fixed = span_bytes(aux['fixed_spans']); session = span_bytes(aux['session_spans'])
    for key, value in (('file_bytes', file_size), ('bss_bytes', bss_size),
                       ('fixed_overhead', fixed), ('session_bytes', session),
                       ('request', fixed+((file_size+bss_size+3)//4)*4),
                       ('bss_begin', a['base']+session+file_size),
                       ('bss_end', a['base']+session+file_size+bss_size)):
        claim(a, key, value, '$.allocation', 'source byte length / span sum / aligned layout',
              ['$capture.file_segments', '$capture.bss_spans', '$capture.fixed_spans', '$capture.session_spans'])
    reads = {(r['scene'], r['layer'], r['sequence']): r for r in aux['osd_reads']}
    require(len(reads) == len(aux['osd_reads']), '$capture.osd_reads', 'duplicate_source_entry')
    used = set()
    for scene in gate_osd_scenes():
        record = by[scene]; path = '$.records['+scene+']'
        for layer in record['layers']:
            lp = path+'.layers['+str(layer['index'])+']'
            claim(layer, 'coordinate_count', len(layer['rectangles']), lp, 'len(rectangles)', ['rectangles'])
            offset = 0
            for i, piece in enumerate(layer['pieces'], 1):
                key = (scene, layer['index'], i)
                require(key in reads, lp, 'raw_read_missing')
                raw = reads[key]; used.add(key)
                content = source_bytes(raw['segments'], require, '$capture.osd_reads')
                require(raw['source'] == piece['buffer'], lp, 'raw_source_identity_mismatch')
                pp = lp+'.pieces['+str(i)+']'
                claim(piece, 'offset', offset, pp, 'sum(previous raw read lengths)', ['$capture.osd_reads'])
                claim(piece, 'bytes', len(content), pp, 'len(expanded raw bytes)', ['$capture.osd_reads'])
                claim(piece, 'result', xor_words(content, require, pp), pp, 'XOR32(raw words)', ['$capture.osd_reads'])
                offset += len(content)
            eq(offset, layer['width']*layer['height'], lp, 'full layer raw byte coverage', ['pieces', 'width', 'height'])
    require(used == set(reads), '$capture.osd_reads', 'extra_source_entry')
    rows_by = {item['scene']: item for item in aux['slot_scans']}
    require(set(rows_by) == {'JPEG_L', 'RAW_L'} and len(aux['slot_scans']) == 2,
            '$capture.slot_scans', 'slot_scan_missing')
    for scene in ('JPEG_L', 'RAW_L'):
        record = by[scene]; path = '$.records['+scene+']'; scan = rows_by[scene]
        rows = scan['rows']; indices = [row['index'] for row in rows]
        require(indices == list(range(99)), '$capture.slot_scans', 'physical_scan_not_contiguous')
        active_ids = profile['qualities'][record['quality']]['category_ids']
        active = set(active_ids); mask = sum(1 << row['index'] for row in rows)
        inactive = 0; unexpected = 0
        for raw in rows:
            if raw['index'] not in active:
                inactive |= 1 << raw['index']
                if raw['count_raw'] or raw['stride_raw'] or raw['base_raw'] or any(raw['matrix_words']):
                    unexpected |= 1 << raw['index']
        for key, value in (('physical_count', len(rows)), ('descriptor_count', len(active_ids)),
                           ('covered_mask', f'{mask:032x}'), ('inactive_mask', f'{inactive:032x}'),
                           ('inactive_nonzero_mask', f'{unexpected:032x}')):
            claim(record, key, value, path, 'rebuild from complete indexed physical scan and reference', ['$capture.slot_scans', '$profile.qualities'])
        words = record['raw_fields']; pool = record['pool']
        claim(words, 'arena_length', profile['image_arena'][1]-profile['image_arena'][0], path+'.raw_fields',
              'arena end minus start', ['$profile.image_arena'])
        for key, value in (('begin', words['p_ec']), ('end', words['p_f0']+1),
                           ('tail', words['p_f0']+1-scan['pool_cursor'])):
            claim(pool, key, value, path+'.pool', 'raw P endpoints and raw allocation cursor difference',
                  ['raw_fields.p_ec', 'raw_fields.p_f0', '$capture.slot_scans.pool_cursor'])
        for category in record['categories']:
            raw = rows[category['id']]; matrix = raw['matrix_words']
            addresses = [v for v in matrix if v]
            require(matrix == addresses+[0]*(18-len(addresses)), path, 'slot_matrix_has_gap')
            eq(raw['count_raw'], len(addresses), path, 'count register versus nonzero matrix entries', ['$capture.slot_scans'])
            cp = path+'.categories['+str(category['id'])+']'
            for key, value in (('count', len(addresses)), ('base', raw['base_raw']),
                               ('stride', raw['stride_raw']), ('stride_raw', raw['stride_raw']),
                               ('addresses', addresses),
                               ('stride_address', profile['stride_array']+4*category['id']),
                               ('count_address', profile['count_array']+4*category['id']),
                               ('matrix_address', profile['matrix']+76*category['id'])):
                claim(category, key, value, cp, 'matrix entries / raw register / indexed source address', ['$capture.slot_scans', '$profile'])
    burst = by['BURST']; samples = burst['samples']
    for scene in ('JPEG_L','RAW_L','RAW_169'):
        image=by[scene]['image']
        claim(image,'stride',image['width']*2,'$.records['+scene+'].image',
              'YUV422 width times two bytes',['width','format'])
    claim(burst, 'first_shot', samples[0]['sequence'], '$.records[BURST]', 'first saved shot sequence', ['samples[0].sequence'])
    claim(burst, 'last_shot', samples[-1]['sequence'], '$.records[BURST]', 'last saved shot sequence', ['samples[-1].sequence'])
    bw = by['BW']; raw_bw = {(r['kind'], r['sequence']): r for r in aux['bw_reads']}
    require(len(raw_bw) == len(aux['bw_reads']), '$capture.bw_reads', 'duplicate_source_entry')
    used = set()
    for kind, repeats in (('read', 1), ('control', 4), ('crc', 1)):
        pieces = bw[kind+'_samples']
        times = [(p['end_tick']-p['start_tick']) & 0xffffffff for p in pieces]
        claim(bw, kind+'_ticks', times, '$.records[BW]', 'uint32(end minus start) for every saved piece', [kind+'_samples'])
        for i, piece in enumerate(pieces, 1):
            key = (kind, i); pp = '$.records[BW].'+kind+'['+str(i)+']'
            require(key in raw_bw, pp, 'raw_read_missing')
            used.add(key); raw = raw_bw[key]
            content = source_bytes(raw['segments'], require, '$capture.bw_reads')
            expected = zlib.crc32(content) & 0xffffffff if kind == 'crc' else xor_words(content, require, pp)
            eq(raw['source'], piece['range'][0], pp, 'raw source address identity', ['$capture.bw_reads'])
            eq(piece['range'][1]-piece['range'][0], len(content), pp, 'raw source byte length', ['$capture.bw_reads'])
            for field, value in (('result', expected), ('bytes', len(content)*repeats), ('check_ok', True)):
                claim(piece, field, value, pp, 'raw byte checksum / fixed work / verified comparison', ['$capture.bw_reads'])
    require(used == set(raw_bw), '$capture.bw_reads', 'extra_source_entry')
    claim(bw, 'bytes_per_piece', len(source_bytes(raw_bw[('read', 1)]['segments'], require, '$capture.bw_reads')),
          '$.records[BW]', 'first fixed ER read byte length; all pieces checked independently', ['$capture.bw_reads'])
    checked={row['path'] for row in audit}
    missing=expected_paths-checked
    if missing: raise RuntimeError('derived contract missing rules: '+repr(sorted(missing)))
    return audit


def gate_osd_scenes(): return ('GRID_OFF', 'GRID_ON', 'INFO_OFF', 'INFO_ON')
