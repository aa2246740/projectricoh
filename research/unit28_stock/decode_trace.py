"""Decode /ATA1/GXRTRACE.BIN written by the diag gen 146 DAT (layout: diag.c TraceRec, trace146.py).
(The gen 145 decoder is decode_trace145.py.)

Usage: /usr/bin/python3 -I -B research/unit28_stock/decode_trace.py GXRTRACE.BIN [--nonce HEX32]
       /usr/bin/python3 -I -B research/unit28_stock/decode_trace.py --new OUT.BIN   (blank 8,704 B file
                                                                                     with a fresh nonce)

All eight records (four unit slots x two halves) and both unit names of each record are read. A record
is used only when it is valid: magic, the file's nonce, its own position (slot, half), CRC32, commit word,
session and seq >= 1, the name matching its slot, and internal consistency (stages vs menus, init kind
without menus, counters). The two halves of a slot are also checked against each other. Every slot then
gets a verdict:
  evidence      a valid record with at least one menu entry: the entries can be read
  undetermined  no valid record, only an init record, or only rejected/stale records; the reason and the
                next observation are printed
--nonce: the nonce printed by --new when the file was prepared; a header with another nonce means the
file is not the one prepared for this test (stale), and nothing in it is used.
"""
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import trace146 as L  # noqa: E402

STAGES = ((1, 'init'), (2, 'menu'), (4, 'publish'), (8, 'refuse'), (16, 'ingress-fail'))
OUTCOMES = {'K': 'published (page S)', 'X': 'refused: body/DAT mask', 'D': 'refused: native seed',
            'O': 'rendered, then not owned (no page S)', 'I': 'entry refused at ingress (nothing measured)'}
for _d in '123456':
    OUTCOMES[_d] = 'refused: render step ' + _d


def text(raw):
    return raw.split(b'\0', 1)[0].decode('ascii', 'replace')


def words(raw, at, count):
    return struct.unpack_from('>%dI' % count, raw, at)


def menu(w):
    ingress = (w[1] >> 8) & 255
    out = {'entry': w[0], 'outcome': chr(w[1] & 255) if w[1] & 255 else '',
           'meaning': OUTCOMES.get(chr(w[1] & 255), 'unknown'), 'ingress': ingress,
           'overlay_on': (w[1] >> 16) & 255, 'ov_fail': (w[1] >> 24) & 255,
           'activity': w[3], 'native_state': hex(w[4]), 'part': w[5] & 255, 'count': (w[5] >> 8) & 255,
           'kind': w[5] >> 24, 'seed_table': hex(w[9]), 'root_state': w[10] & 255, 'root_flags': hex(w[10] >> 8),
           'check_failure': w[11], 'entry_serial': w[12], 'view_array': hex(w[17]),
           'ui_restore0': hex(w[18]), 'ui_restore6': hex(w[19]), 'w2037f3bc': hex(w[20]),
           'tag0_tag1': hex(w[21]), 'names_screen': hex(w[22]), 'rows_screen': w[23]}
    if ingress:
        out.update({'body_mask': '%02x' % (w[2] & 255), 'dat_mask': '%02x' % ((w[2] >> 8) & 255),
                    'refused': (w[2] >> 16) & 255, 'top_tag': (w[5] >> 16) & 255, 'top_state': hex(w[6]),
                    'names_native': hex(w[7]), 'rows_native': w[8], 'rpc_ready': w[13] & 255,
                    'link': (w[13] >> 8) & 255, 'rpc_limit': (w[13] >> 16) & 255,
                    'T': '%04x' % (w[14] & 0xffff), 'have_T': (w[14] >> 16) & 255, 'T_error': w[14] >> 24,
                    'rows_matched': w[15] & 255, 'row_mismatch': hex((w[15] >> 8) & 0xffff),
                    'row_error': w[15] >> 24, 'largest_free': w[16]})
    else:
        out.update({'not_measured': 'masks, unit reads, heap: the entry did not run',
                    'names_now': hex(w[7]), 'rows_now': w[8]})
    return out


def record(data, index, nonce):
    raw = data[L.HEAD + L.REC * index:L.HEAD + L.REC * (index + 1)]
    slot, half = index >> 1, index & 1
    out = {'position': index, 'slot': slot, 'half': 'AB'[half]}
    if not any(raw):
        out['state'] = 'blank'
        return out
    magic = words(raw, 0, 1)[0]
    session, seq, where = words(raw, L.O_SESSION, 3)
    reasons = []
    if magic != L.MAGIC:
        reasons.append('magic')
    if raw[L.O_NONCE:L.O_NONCE + 16] != nonce:
        reasons.append('nonce (record of another prepared file)')
    if where & 0xff0000ff != (1 << 24 | slot) or (where >> 8) & 255 != half:
        reasons.append('position field %08x' % where)
    if words(raw, L.O_CRC, 1)[0] != L.crc(raw):
        reasons.append('crc (partial or damaged write)')
    if words(raw, L.O_COMMIT, 1)[0] != L.COMMIT ^ session ^ seq:
        reasons.append('commit word')
    if not session or not seq:
        reasons.append('session/seq zero')
    kind = (where >> 16) & 255
    stages, menus = words(raw, L.O_STAGES, 2)
    counts = dict(zip(L.COUNTS, words(raw, L.O_COUNT, 16)))
    names = text(raw[L.O_UNIT_RAW:L.O_UNIT_RAW + 8]), text(raw[L.O_UNIT_SESSION:L.O_UNIT_SESSION + 8])
    if kind not in (1, 2):
        reasons.append('kind %d' % kind)
    if kind == 1 and menus:
        reasons.append('init record with menus')
    if bool(menus) != bool(stages & 2) or not stages & 1:
        reasons.append('stages %x vs menus %d' % (stages, menus))
    if counts['written'] >= seq or counts['syncs'] < seq:
        reasons.append('counters vs seq')
    expected = L.UNITS[slot] if slot < 3 else None
    if expected and names[1] != expected or not expected and names[1] in L.UNITS:
        reasons.append('session name %r in slot %d' % (names[1], slot))
    out.update({'session': session, 'seq': seq, 'kind': {1: 'init', 2: 'menu'}.get(kind, kind),
                'unit_raw': names[0], 'unit_session': names[1],
                'version_raw': '%08x' % words(raw, L.O_VERSION_RAW, 1)[0],
                'version_session': '%08x' % words(raw, L.O_VERSION_SESSION, 1)[0],
                'stages': [n for b, n in STAGES if stages & b], 'menus': menus, 'counters': counts})
    if reasons:
        out['state'] = 'rejected'
        out['reasons'] = reasons
        return out
    init = words(raw, L.O_INIT, 16)
    out['init'] = {'entry_serial': init[0], 'root_state': init[1], 'root_flags': hex(init[2]),
                   'check_failure': init[3], 'rpc_ready': init[4], 'link_word': init[5], 'rpc_limit': init[6],
                   'ready_word': init[7], 'largest_free': init[8], 'free_bytes': init[9], 'heap_bad': init[10],
                   'block': hex(init[11]), 'block_bytes': init[12], 'generation': init[13],
                   'names': hex(init[14]), 'rows': init[15] & 255, 'kind': (init[15] >> 8) & 255,
                   'activity': init[15] >> 16}
    if init[13] != 146:
        out['state'] = 'rejected'
        out['reasons'] = ['generation %d' % init[13]]
        return out
    last, first = words(raw, L.O_HOOK_TASK, 4), words(raw, L.O_HOOK_FIRST, 4)
    out['hook_tasks'] = {h: {'count': last[i] >> 16, 'last_task': last[i] & 0xffff, 'first_task': first[i]}
                         for i, h in enumerate(L.HOOKS) if last[i] >> 16}
    entries = [menu(words(raw, L.O_MENU + 96 * i, L.WORDS)) for i in range(min(menus, L.MENUS))]
    if menus > L.MENUS:
        entries[-1]['note'] = 'latest entry; entries %d..%d are not kept' % (L.MENUS, menus - 1)
    out['entries'] = entries
    out['state'] = 'valid'
    return out


def pair(a, b):
    """Two valid halves of one slot: the newer must not have fewer menus or smaller counters when they
    come from the same session."""
    older, newer = sorted((a, b), key=lambda r: (r['session'], r['seq']))
    if older['session'] == newer['session'] and older['seq'] == newer['seq']:
        return 'two halves with the same session and seq'
    if older['session'] == newer['session'] and (
            newer['menus'] < older['menus'] or
            any(newer['counters'][k] < older['counters'][k] for k in L.COUNTS if k != 'last_failed_seq')):
        return 'newer half of the same session has fewer menus or smaller counters'
    return None


def verdict(slot, records, top):
    valid = [r for r in records if r['state'] == 'valid']
    rejected = [r for r in records if r['state'] == 'rejected']
    name = L.SLOT_NAMES[slot]
    if len(valid) == 2:
        problem = pair(*valid)
        if problem:
            for r in valid:
                r['state'], r['reasons'] = 'rejected', ['inconsistent pair: ' + problem]
            rejected, valid = rejected + valid, []
    if not valid:
        why = 'no valid record' + (' (rejected: %s)' % '; '.join(
            '%s: %s' % ('AB'[r['position'] & 1], ', '.join(r['reasons'])) for r in rejected) if rejected else '')
        return {'slot': name, 'verdict': 'undetermined', 'reason': why,
                'cannot_say': 'whether the DAT ran on this unit, reached init or a menu, or failed to write',
                'next': 'same boot: check the other slots and both names of every record (slot 3 = other '
                        'session name); then repeat the unit with the camera on, one ADJ, and check that a '
                        'record with a new session appears'}
    latest = max(valid, key=lambda r: (r['session'], r['seq']))
    previous = [r for r in valid if r is not latest]
    out = {'slot': name, 'latest': {k: latest[k] for k in ('half', 'session', 'seq', 'kind', 'menus',
                                                             'unit_raw', 'unit_session', 'stages')},
           'previous_complete': {k: previous[0][k] for k in ('half', 'session', 'seq', 'kind', 'menus')}
           if previous else None,
           'rejected_halves': [dict(half=r['half'], reasons=r['reasons']) for r in rejected],
           'counters': latest['counters'], 'hook_tasks': latest.get('hook_tasks', {}),
           'newest_session_in_file': top,
           'fresh': latest['session'] == top}
    failures = {k: v for k, v in latest['counters'].items()
                if k not in ('syncs', 'written', 'last_failed_seq') and v}
    if not latest['menus']:
        out.update(verdict='undetermined', reason='init record only (no menu entry recorded)',
                   cannot_say='whether menus ran: a retire before the first menu, a menu whose record was '
                              'not written (busy, I/O) and no ADJ press all leave this',
                   next='same session, press ADJ once more and check whether this half pair gains a menu '
                        'record; counters busy_menu/open/write/read in that record say why earlier ones '
                        'were missing')
    else:
        out.update(verdict='evidence', entries=latest['entries'],
                   reason='%d menu entr%s recorded in session %d' % (latest['menus'],
                                                                     'y' if latest['menus'] == 1 else 'ies',
                                                                     latest['session']))
        if any(e['outcome'] == 'I' for e in latest['entries']):
            out['note_I'] = 'an I entry was refused before the DAT measured anything; its masks are not data'
    if failures:
        out['failures_before_this_record'] = failures
    if not out['fresh']:
        out['stale_note'] = ('a later session (%d) exists in the file: this slot was not written in the '
                             'latest session that wrote anything' % top)
    return out


def decode(data, nonce=None):
    out = {'bytes': len(data), 'header': data[:8].decode('ascii', 'replace')}
    if len(data) != L.FILE or data[:8] != L.HEADER_MAGIC:
        out['file'] = 'not a gen 146 trace file (length or header): nothing in it is used'
        return out
    file_nonce = data[16:32]
    out['nonce'] = file_nonce.hex()
    if nonce is not None and file_nonce != nonce:
        out['file'] = 'nonce differs from the prepared file: stale file, nothing in it is used'
        return out
    records = [record(data, i, file_nonce) for i in range(8)]
    valid = [r for r in records if r['state'] == 'valid']
    top = max((r['session'] for r in valid), default=0)
    out['records'] = records
    out['slots'] = [verdict(s, records[2 * s:2 * s + 2], top) for s in range(4)]
    sessions = {}
    for r in records:
        if r['state'] == 'valid':
            sessions.setdefault(r['session'], set()).add(L.SLOT_NAMES[r['slot']])
    out['sessions'] = {str(k): sorted(v) for k, v in sorted(sessions.items())}
    return out


def main():
    if sys.argv[1] == '--new':
        data = L.blank()
        Path(sys.argv[2]).write_bytes(data)
        print('nonce', data[16:32].hex())
        return
    data = Path(sys.argv[1]).read_bytes()
    nonce = bytes.fromhex(sys.argv[sys.argv.index('--nonce') + 1]) if '--nonce' in sys.argv else None
    print(json.dumps(decode(data, nonce), indent=1))


if __name__ == '__main__':
    main()
