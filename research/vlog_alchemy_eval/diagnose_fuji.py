"""Compare declared F-Gamut C mathematics with the published DCTL coefficients."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from support import setup,DATA,dump
setup()
import re
import numpy as np
from measure import rgb_matrix,FGC,official_cubes,fg_input
from data import scenes,synthetic,xyz_to_encoded,encode,rgb_out,de,stats,Cube

def main():
    text=(DATA/'DCTL/ACES_to_FLog2C_Inverse.dctl').read_text()
    group=re.search(r'inv_matrix_coef\[9\]\s*=\s*\{([^}]+)',text).group(1)
    inv=np.array([float(x.strip().rstrip('f')) for x in group.split(',') if x.strip()]).reshape(3,3)
    b=np.array([[.8951,.2664,-.1614],[-.7502,1.7135,.0367],[.0389,-.0685,1.0296]])
    w=lambda xy:np.array([xy[0]/xy[1],1,(1-sum(xy))/xy[1]])
    adapt=np.linalg.inv(b)@np.diag((b@w((.32168,.33767)))/(b@w((.3127,.329))))@b
    ap0=rgb_matrix(((.7347,.2653),(0,1),(0,-.077)),(.32168,.33767))
    official_xyz_to_fg=np.linalg.inv(rgb_matrix(FGC))
    dctl_xyz_to_fg=inv@np.linalg.inv(ap0)@adapt
    no_adapt_xyz_to_fg=inv@np.linalg.inv(ap0)
    ss=scenes()
    sets=synthetic()
    sets['photos']=np.vstack([a['xyz'][a['valid']] for a,_ in ss])
    official=official_cubes()
    rows=[]
    for name in ('PROVIA','CLASSIC-CHROME','CLASSIC-Neg.','ETERNA','ACROS'):
        token='CLASSIC-Neg' if name=='CLASSIC-Neg.' else name
        cube=Cube.read(DATA/'Luts/Fujifilm'/('FLog2C_to_'+token+'_VLog.cube'))
        direct=official['flog2c',name][0]
        row={'style':name,'splits':{}}
        for split,xyz in sets.items():
            transformed=xyz@dctl_xyz_to_fg.T
            encoded=encode(transformed,'flog2')
            a=cube.apply(xyz_to_encoded(xyz,'vlog'))
            d=direct.apply(encoded)
            no_adapt=direct.apply(encode(xyz@no_adapt_xyz_to_fg.T,'flog2'))
            compensated=cube.apply(xyz_to_encoded(xyz@adapt.T,'vlog'))
            normative=direct.apply(fg_input(xyz,'flog2c'))
            row['splits'][split]={'alchemy_vs_dctl_official':stats(de(rgb_out(a),rgb_out(d))),
                                  'dctl_vs_normative_official':stats(de(rgb_out(d),rgb_out(normative))),
                                  'alchemy_vs_no_white_adaptation_hypothesis':stats(de(rgb_out(a),rgb_out(no_adapt))),
                                  'white_adapted_input_vs_normative_official':stats(de(rgb_out(compensated),rgb_out(normative)))}
        rows.append(row)
    dump('fuji_transform_checks.json',{'coefficient_max_difference':float(np.max(abs(dctl_xyz_to_fg-official_xyz_to_fg))),
         'basis':'D65 XYZ to F-Gamut C; official primaries versus DCTL through Bradford D60 ACES AP0',
         'styles':rows})
    print('DCTL coefficient difference',float(np.max(abs(dctl_xyz_to_fg-official_xyz_to_fg))),flush=True)
    for r in rows: print(r['style'],r['splits']['photos'],flush=True)

if __name__=='__main__':
    main()
