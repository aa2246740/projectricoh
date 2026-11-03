"""Postcheck for ownership_settings: take the retained model's own next native open (as g129/g131 did), then open slot 4."""
from pathlib import Path
import json
import sys
HERE = Path(__file__).resolve().parent

def run(context, arguments, out, sessions):
    unit = arguments[arguments.index('--unit') + 1]
    ux = sys.modules['review_native_ux']
    m, fr = ux.m, ux.fr
    h, p, w = sessions[-1]
    layout = json.loads((out / 'local/layout/layout.json').read_text())
    pending = p.symbol_pc('g') + layout['recheck'] + 1
    before = ux.snap(h, p)
    log = [dict(tag='before-reopen', native_activity=before['native_activity'], native_overlay=before['native_overlay'],
                mode=before['mode'], pending=h.u(pending, 1))]
    m.reopen(h, p, w)
    after = ux.snap(h, p)
    settings = h.u(0x200c0dac)
    log.append(dict(tag='after-reopen', rows=after['rows'], mode=h.u(settings + 0x36e, 1), wb=[h.u(settings + 0x6dd, 1), h.u(settings + 0x6de, 1)],
                    matches=bool(ux.matches(h, p, 4)), pending=h.u(pending, 1)))
    adapter = json.loads((HERE / 'adapter-layout.json').read_text())
    n = p.symbol_pc('n')
    ui = n + adapter['ui']
    def get(name):
        return h.u(ui + adapter['ui.' + name], 1)
    log.append(dict(tag='ui-before-disp', screen=get('screen'), cur=get('cur'), count=get('count')))
    result = p.engine(3, [])
    log.append(dict(tag='ui-after-disp', ok=bool(result.get('ok')), screen=get('screen'), cur=get('cur'), count=get('count')))
    (out / ('reopen-open-' + unit + '.json')).write_text(json.dumps(log, indent=1) + '\n')
