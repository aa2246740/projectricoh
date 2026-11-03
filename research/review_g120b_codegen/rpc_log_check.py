"""Reconstruct retained X/V/W addresses from the native execution records."""
from pathlib import Path
import collections
import csv
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_scope import SOURCE, OUT, save, file_sha, record_inputs


def logs(value, trail=''):
    if isinstance(value, dict):
        for key, child in value.items():
            if (isinstance(child, list) and child and isinstance(child[0], dict)
                    and 'cmd' in child[0] and 'value' in child[0]):
                yield trail+'/'+key, child
            elif isinstance(child, (dict, list)):
                yield from logs(child, trail+'/'+key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            if isinstance(child, (dict, list)):
                yield from logs(child, trail+'/'+str(index))


def main():
    maps = json.loads((OUT/'maps.json').read_text())['units']
    by_unit = {unit['unit']: unit for unit in maps}
    output, sources, summary_only = [], [], []
    counts = collections.Counter()
    for path in sorted((SOURCE/'native').rglob('*.json')):
        value = json.loads(path.read_text())
        unit = value.get('unit') if isinstance(value, dict) else None
        if unit not in by_unit:
            unit = next((name for name in by_unit if name in path.name), None)
        entries = list(logs(value))
        if not entries:
            continue
        sources.append(dict(path=str(path.relative_to(SOURCE)),sha256=file_sha(path),
            unit=unit,logs=len(entries),status=value.get('status'),
            dat_sha256=value.get('dat_sha256')))
        units = [by_unit[unit]] if unit else maps
        for trail, events in entries:
            if all('result' not in event and 'page' not in event for event in events):
                summary_only.append(dict(source=str(path.relative_to(SOURCE)),log=trail,
                    records=len(events),reason='This is a simulation summary without address state or replies; the full RPC sequence is not retained here.'))
                continue
            cursor, page = None, None
            for index, event in enumerate(events):
                cmd, argument = event['cmd'], event['value']
                result = event.get('device_result', event.get('result'))
                recorded = event.get('page')
                address, length, matched, strict = None, 0, [], []
                status = 'OK'
                if cmd == 23:
                    selected = argument
                    matched = [u['unit']+':T' for u in units if selected == u['t_page']]
                    matched += [u['unit']+':'+r['label'] for u in units for r in u['rows']
                                if selected == r['address'] >> 16]
                    strict = matched.copy()
                    if isinstance(result, int) and result >= 0:
                        page = selected
                elif cmd == 21:
                    effective = recorded if recorded is not None else page
                    if effective is not None:
                        address = (effective << 16) | (argument & 0xfffe)
                        length = 2
                        if isinstance(result, int) and result >= 0:
                            cursor = address
                    else:
                        status = 'MISSING_PAGE'
                elif cmd == 22:
                    effective = recorded if recorded is not None else page
                    if effective is not None and any(effective == u['t_page'] for u in units):
                        address = next((u['t_page'] << 16) | u['t_offset'] for u in units if effective == u['t_page'])
                    else:
                        address = cursor
                    length = 2
                    if address is None:
                        status = 'MISSING_CURSOR'
                    elif isinstance(result, int) and result >= 0:
                        cursor = address + 2
                else:
                    status = 'OTHER_COMMAND'
                if address is not None:
                    for u in units:
                        t = (u['t_page'] << 16) | u['t_offset']
                        if address == t:
                            matched.append(u['unit']+':T')
                            strict.append(u['unit']+':T')
                        for row in u['rows']:
                            label = u['unit']+':'+row['label']
                            if row['word_begin'] <= address and address+length <= row['word_end']:
                                matched.append(label)
                            if row['address'] <= address and address+length <= row['address']+row['length']:
                                strict.append(label)
                if status == 'OK' and not matched:
                    status = 'OUTSIDE_MAP'
                if status == 'OK' and not strict:
                    status = 'PRESERVED_EDGE_WORD'
                counts[status] += 1
                output.append(dict(source=str(path.relative_to(SOURCE)),log=trail,index=index,
                    unit=unit or 'unspecified',command={23:'X',21:'V',22:'W'}.get(cmd,str(cmd)),
                    value=hex(argument),result=result,address=hex(address) if address is not None else '',
                    bytes=length,matched=','.join(matched),strict=','.join(strict),status=status))
    with (OUT/'rpc-events.tsv').open('w') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(output[0]),delimiter='\t')
        writer.writeheader();writer.writerows(output)
    save('rpc-log-sources.json', sources)
    summary = dict(status='PASS_WITH_EDGE_WORDS' if not any(counts[k] for k in
            ('MISSING_PAGE','MISSING_CURSOR','OTHER_COMMAND','OUTSIDE_MAP')) else 'INCOMPLETE',
        source_files=len(sources),logs=sum(x['logs'] for x in sources)-len(summary_only),events=len(output),
        summary_only=summary_only,summary_records=sum(x['records'] for x in summary_only),
        counts=dict(counts),commands=dict(collections.Counter(row['command'] for row in output)),
        failures=[row for row in output if row['status'] not in ('OK','PRESERVED_EDGE_WORD')],
        edge_word_examples=[row for row in output if row['status']=='PRESERVED_EDGE_WORD'][:12],
        scope='Retained event arrays only; scalar RPC counters do not reconstruct omitted addresses.')
    save('rpc-log-check.json', summary)
    record_inputs('rpc-log-inputs.json')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('failures','edge_word_examples')},ensure_ascii=False))


if __name__=='__main__':
    main()
