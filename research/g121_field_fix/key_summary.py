"""Join native raw-key, generic conversion and ADJ state observations."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import OUT,DAT,save,file_sha

probe=json.loads((OUT/'key-probe.json').read_text())
converted={x['logical']:x['ui'] for x in probe['conversion']}
rows=[]
for unit in ('50mm','28mm','mount'):
    for name in ('fn2_right_left','ok','disp','timer','plus','minus','adj','shutter_half','shutter_full',
                 'lever_left','lever_right','dial_up','dial_down'):
        path=OUT/'field'/('121-'+unit+'-'+name+'.json');x=json.loads(path.read_text())
        assert x['dat_sha256']==file_sha(DAT) and x['status']=='PASS'
        for key in ('key','right','left'):
            if key not in x:continue
            event=x[key];rows.append(dict(unit=unit,case=name,phase=key,raw=hex(event['raw']),
                logical=hex(event['logical']),generic_ui=converted[event['logical']],
                dispatch=event['dispatch'],record=str(path.relative_to(OUT))))
save('key-map-summary.json',dict(status='PASS_RAW_ROUTES',dat_sha256=file_sha(DAT),
    physical_button_identity='INCOMPLETE',body_sha256='50720c80696ca88f25dc25a85285acd0e0f19906e1d7da1dd404f6cc243f9008',
    routes=rows,scope='Raw-message conversion and native state routes. Physical button names remain candidate labels.'))
print('PASS raw route summary',len(rows),flush=True)
