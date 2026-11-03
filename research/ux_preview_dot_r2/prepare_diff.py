"""Retarget the established common-body B runner from 117/118 to 118/119."""
from pathlib import Path
import re

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
t=(ROOT/'research/review_g118/differential.py').read_text()
t=re.sub(r'117|118',lambda m:{'117':'118','118':'119'}[m[0]],t)
t=t.replace('research/review_g118_codegen','research/review_g117_codegen')
t=t.replace("((118,'engine_v38_b36'),(119,'engine_v39_ux'))","((118,'engine_v39_ux'),(119,'engine_v40_ux'))")
t=t.replace("ex.pb.CACHE=OUT/'diff-decode'","ex.pb.CACHE=OUT/'diff-decode'/sys.argv[1]")
a=t.index('        aa=self.a.e.symbols;bb=self.b.e.symbols');b=t.index('\n    def projection',a)
t=t[:a]+'''        aa=self.a.e.symbols;bb=self.b.e.symbols
        self.ns={r.g:r.n for r in self.rs}
        pairs={}
        for path in (OUT/'codegen').glob('*.json'):
            row=json.loads(path.read_text())
            if not row.get('local_A'):continue
            for d in row.get('data_checks',[]):
                x,y=d.get('old'),d.get('new')
                if x and y and x['type']==y['type']==1 and x['name'] not in ('n','g'):
                    key=x['base'];value=(x,y)
                    if key in pairs:assert pairs[key][1]['base']==y['base']
                    pairs[key]=value
        for n,s in aa.items():
            if s['type']==1 and s['size'] and n not in ('g','n') and n in bb and s['size']==bb[n]['size']:
                pairs.setdefault(s['address'],(s,bb[n]))
        for a,b in sorted(pairs.values(),key=lambda pair:pair[0].get('base',pair[0].get('address'))):
            def sym(x):return dict(address=x.get('base',x.get('address')),size=x['size'])
            self.objects.append(dict(name=a['name'],old=sym(a),new=sym(b)))
        self.fn={r.g:{BASE+s['address']:'function:'+cg.canon(r.g,n) for n,s in r.e.functions.items()} for r in self.rs}

    def pointer(self,r,v):
        if not BASE<=v<BASE+0x30000:return v
        g=self.g[r.g];z=r.e.symbols['g']['size']
        if g<=v<g+z:return 0x50000000+v-g
        if r.n<=v<r.n+r.e.symbols['n']['size']:
            off=v-r.n
            if off>=3712:return 'C-new-n:'+str(off)
            return 0x52000000+off
        for i,obj in enumerate(self.objects):
            s=obj['old' if r.g==118 else 'new'];a=BASE+s['address']
            if a<=v<a+s['size']:return 0x51000000+0x10000*i+v-a
        return self.fn[r.g].get(v,v)
'''+t[b:]
t=t.replace("if isinstance(logical,str) and logical.startswith('C-new-g:'):\n                assert not any(data),(r.g,logical,data.hex(),hex(pc))","if isinstance(logical,str) and logical.startswith('C-new-n:'):")
t=t.replace("r.write(r.n,bytes(3712))","r.write(r.n,bytes(r.e.symbols['n']['size']))")
# Engine's existing fields have the same offsets in gen118 and gen119.
for before,after in ((2464,2523),(2465,2524),(2466,2525),(2467,2526),(2468,2527),(803,862),(805,864),(807,866)):
    t=t.replace('at('+str(before)+')','at('+str(after)+')')
t=t.replace('off=243 if r.g==118 else 302','off=302')
t=t.replace("names=('pn_ui_render.constprop.0','panel_render.constprop.0')","names=('panel_render.constprop.0','panel_render.constprop.0')")
# Both prior versions already clear the panel on H01. Remove the older C cut.
a=t.index('    # C-only projection: the old function clears panel.open/input_enabled');b=t.index('\ndef prepare_menu',a)
t=t[:a]+t[b:]
t=t.replace("if name=='ig_menu':summary['C_projection']='At old PC '+hex(p.menu_cutpoint)+': clear panel.open/input_enabled; pending preview branch is C and not projected; seed old committed/current as new confirmed_valid/confirmed. Remaining machine body executes unchanged.'","if name=='ig_menu':summary['C_projection']='The new failed latch is zero in the common domain; its notice branch is C and runs on native persistent tests.'")
t=t.replace("p.hook('cursor_cache',cursor)","p.hook('cursor_cache',cursor)\n    p.hook('view_owned',lambda b,r:1)")
t=t.replace("for name in ('ingress','a4_move','ui_finish'):p.hook(name)","for name in ('ingress','a4_move','ui_finish','eng_view_lost'):p.hook(name)\n    p.hook('view_owned',lambda b,r:1)")
t=t.replace("p.hook('core_call',lease)","p.hook('core_call',lease)")
t=t.replace("if r.g==119:\n            r.write(p.g[r.g]+235", "if True:\n            r.write(p.g[r.g]+235")
(OUT/'differential.py').write_text(t)
print('Prepared common-body B runner')
