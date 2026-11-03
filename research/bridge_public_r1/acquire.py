"""Public reference acquisition list. GET only; each object has its own directory."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch import fetch

SOURCES = [
 ('camspec-data','https://www.gujinwei.org/research/camspec/camspec_database.txt','camspec_database.txt'),
 ('camspec-equipment','https://www.gujinwei.org/research/camspec/camlist%26equipment.txt','equipment.txt'),
 ('camspec-paper','https://www.gujinwei.org/research/camspec/camspec.pdf','paper.pdf'),
 ('cc-average30','https://babelcolor.com/index_htm_files/CC_Avg30_spectrum_CGATS.txt','spectra.txt'),
 ('cc-before2014','https://babelcolor.com/index_htm_files/ColorChecker24_Before_Nov2014.txt','reference.txt'),
 ('cc-after2014','https://babelcolor.com/index_htm_files/ColorChecker24_After_Nov2014.txt','reference.txt'),
 ('cie1931','https://files.cie.co.at/CIE_xyz_1931_2deg.csv','observer.csv'),
 ('cie-d65','https://files.cie.co.at/CIE_std_illum_D65.csv','d65.csv'),
 ('cie-d50','https://files.cie.co.at/CIE_std_illum_D50.csv','d50.csv'),
 ('cie-daylight-basis','https://raw.githubusercontent.com/colour-science/colour/develop/colour/colorimetry/datasets/illuminants/sds_d_illuminant_series.py','tables.txt'),
 ('munsell-matt-page','https://sites.uef.fi/spectral/munsell-colors-matt-spectrofotometer-measured/','index.html'),
 ('natural-page','https://sites.uef.fi/spectral/natural-colors/','index.html'),
 ('forest-page','https://sites.uef.fi/spectral/forest-colors/','index.html'),
 ('ricoh-gxr-spec','https://www.ricoh-imaging.co.jp/english/products/gxr/specs.html','index.html'),
 ('ricoh-griv-spec','https://www.ricoh-imaging.co.jp/english/products/gr-4/spec/','index.html'),
 ('ricoh-griv-sensor','https://us.ricoh-imaging.com/product/gr-iv/','index.html'),
]

if __name__ == '__main__':
    for label,url,name in SOURCES: fetch(label,url,name)
