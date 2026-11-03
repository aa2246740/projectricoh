"""Additional public reference URLs resolved from the original publishers' pages."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch import fetch

SOURCES = [
 ('kodak-tree-master','https://api.github.com/repos/gingerbeardman/Kodak-Q60-IT8-Reference-Files/git/trees/master?recursive=1','tree.json'),
 ('munsell-readme','https://cs.uef.fi/pub/color/spectra/mspec/README.txt','readme.txt'),
 ('munsell-data','https://cs.uef.fi/pub/color/spectra/mspec/munsell380_800_1.asc.gz','reflectances.asc.gz'),
 ('natural-readme','https://cs.uef.fi/pub/color/spectra/natural/README.txt','readme.txt'),
 ('natural-data','https://cs.uef.fi/pub/color/spectra/natural/natural400_700_5.asc.gz','reflectances.asc.gz'),
 ('cie-cmfs-tables','https://raw.githubusercontent.com/colour-science/colour/develop/colour/colorimetry/datasets/cmfs.py','tables.txt'),
 ('cie-illuminant-tables','https://raw.githubusercontent.com/colour-science/colour/develop/colour/colorimetry/datasets/illuminants/sds.py','tables.txt'),
 ('ricoh-griv-filter','https://www.ricoh-imaging.co.jp/english/products/gr-4/feature/','index.html'),
 ('sony-imx571-spec','https://www.sony-semicon.com/files/62/pdf/p-13_IMX571BQR_Flyer.pdf','spec.pdf'),
 ('matrix-sensitivity-paper','https://arxiv.org/pdf/2304.11549','paper.pdf'),
]

if __name__ == '__main__':
    for label,url,name in SOURCES: fetch(label,url,name)
