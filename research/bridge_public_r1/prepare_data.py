"""Parse untrusted public tables as data, including Python literals via AST only."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c
from common import np
import ast
import gzip
import re
import shlex


def literal_table(label, name):
    p = c.DOWNLOADS / label / 'tables.txt'
    tree = ast.parse(p.read_text())
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            assert isinstance(node.value, ast.Dict)
            return ast.literal_eval(node.value)
    raise ValueError(name)


def interp(table, wavelength):
    keys = np.array(sorted(table),float)
    values = np.array([table[k] for k in keys])
    if values.ndim == 1: return np.interp(wavelength, keys, values)
    return np.array([np.interp(wavelength, keys, values[:,k]) for k in range(values.shape[1])]).T


def daylight(t, tables=None):
    if tables is None: tables = c.arrays(c.LOCAL/'public_data.npz')
    x = (-4.607e9/t**3 + 2.9678e6/t**2 + .09911e3/t + .244063) if t<=7000 else (-2.0064e9/t**3+1.9018e6/t**2+.24748e3/t+.237040)
    y = -3*x*x+2.87*x-.275
    den = .0241+.2562*x-.7341*y
    m1 = (-1.3515-1.7703*x+5.9114*y)/den
    m2 = (.03-31.4424*x+30.0717*y)/den
    return tables['daylight_basis'] @ np.array([1,m1,m2])


def main():
    wave=np.arange(400,721,10)
    cmfs = literal_table('cie-cmfs-tables','DATA_CMFS_STANDARD_OBSERVER')['CIE 1931 2 Degree Standard Observer']
    ill = literal_table('cie-illuminant-tables','DATA_ILLUMINANTS_CIE')
    basis = literal_table('cie-daylight-basis','DATA_BASIS_FUNCTIONS_CIE_ILLUMINANT_D_SERIES')
    observer=interp(cmfs,wave)
    illuminants={k:interp(ill[k],wave) for k in ('D50','D55','D65','D75','A')}
    rows=(c.DOWNLOADS/'camspec-data/camspec_database.txt').read_text().splitlines()
    assert len(rows)==112
    names=[]; ss=[]
    for i in range(0,len(rows),4):
        names.append(rows[i]);s=np.array([[float(v) for v in row.split()] for row in rows[i+1:i+4]])
        assert s.shape==(3,33) and (s>=0).all(); ss.append(s)
    ss=np.array(ss)
    lines=(c.DOWNLOADS/'cc-average30/spectra.txt').read_text().splitlines()
    start=lines.index('BEGIN_DATA')+1; end=lines.index('END_DATA')
    cc=np.zeros((24,len(wave)))
    for row in lines[start:end]:
        words=shlex.split(row); name=words[1]
        index=(int(name[1:])-1)*6+ord(name[0])-ord('A')
        cc[index]=np.interp(wave,np.arange(380,731,10),np.array(words[2:],float))
    assert cc[18,16]>.85 and cc[23,16]<.06, 'CGATS ordering must follow patch names, not sample IDs'
    modern_lines=(c.DOWNLOADS/'cc-modern-dcamprof/reference.cie').read_text().splitlines()
    modern_start=modern_lines.index('BEGIN_DATA')+1;modern_end=modern_lines.index('END_DATA')
    cc_modern=np.zeros_like(cc)
    for line in modern_lines[modern_start:modern_end]:
        words=shlex.split(line)
        if not words:continue
        label=words[0];index=(ord(label[0])-ord('A'))*6+int(label[1:])-1
        cc_modern[index]=np.interp(wave,np.arange(380,731,10),np.array(words[7:],float)/100)
    assert cc_modern[18,16]>.85 and cc_modern[23,16]<.06
    data=gzip.decompress((c.DOWNLOADS/'munsell-data/reflectances.asc.gz').read_bytes()).decode('ascii')
    values=np.fromstring(data,sep=' ')
    assert values.size%421==0
    mun=values.reshape(-1,421)
    alternate=values.reshape(421,-1).T
    assert np.median(abs(np.diff(mun,axis=1))) < np.median(abs(np.diff(alternate,axis=1))) / 5
    munsell=np.array([np.interp(wave,np.arange(380,801),r) for r in mun])
    text=gzip.decompress((c.DOWNLOADS/'natural-data/reflectances.asc.gz').read_bytes()).decode('latin1')
    labels=[]; natural=[]; current=[]
    for line in text.splitlines():
        if not line.strip(): continue
        if re.fullmatch(r'[\s\d]+',line): current.extend(float(v) for v in line.split())
        else:
            if current:
                assert len(current)==61
                natural.append(current); current=[]
            labels.append(line.strip())
    if current: natural.append(current)
    natural=np.asarray(natural,float)
    assert natural.shape==(219,61) and len(labels)==219
    clipped=int(np.sum(natural>4096)); natural=np.clip(natural/4096,0,1)
    # The natural set ends at 700 nm. Constant tail is explicit and sensitivity-tested later.
    natural=np.array([np.interp(wave,np.arange(400,701,5),r) for r in natural])
    assert np.isfinite(munsell).all() and np.min(munsell)>=0 and np.max(munsell)<=1.01
    basis_array=np.column_stack([interp(basis[k],wave) for k in ('S0','S1','S2')])
    np.savez_compressed(c.LOCAL/'public_data.npz',wave=wave,observer=observer,
                       camera_names=names,camera_sensitivities=ss,cc=cc,cc_modern=cc_modern,munsell=munsell,
                       natural=natural,natural_labels=labels,daylight_basis=basis_array,**illuminants)
    c.dump('public_data.json',dict(wavelength_nm=wave,step_nm=10,cc_count=24,
          cc_formulation='BabelColor Avg30, before November 2014; each sample is a chart average, not this chart',
          modern_cc='DCamProf cc24_ref-new.cie; provenance and spectral derivation must be checked; not assumed measured on DPReview chart',
          cameras=names,munsell_count=len(munsell),munsell_order_check=True,natural_count=len(natural),
          natural_publisher_count=218,natural_actual_file_count=219,
          natural_saturated_measurements=clipped,natural_tail='700-720 nm constant extrapolation; separate 400-700 sensitivity run',
          observer='CIE 1931 2 degree, Colour redistribution; original CIE CSV endpoints returned HTTP 404',
          source_python_files_executed=False,SSF_measured_wavelength_range='400-720 nm'))
    print('public data:',len(ss),'cameras;',len(munsell),'Munsell;',len(natural),'natural; CC order verified')


if __name__=='__main__': main()
