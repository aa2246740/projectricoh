"""用目标编译器重测字段布局，复用现有读取方法。"""
from pathlib import Path
import importlib.util

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('g154_layout_method',ROOT/'research/v39_g153/layout_probe.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.HERE=HERE
module.TMP=Path('/Volumes/Workspace/Scratch/tmp/projectricoh/g154-impl-r1/layout')
module.PRODUCT=ROOT/'firmware/engine_v63_g154/candidate/containers/product'
if __name__=='__main__':module.main()
