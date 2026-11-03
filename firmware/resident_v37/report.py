"""Generate the current v3.3 report after final delivery gates pass."""
import importlib.util
from pathlib import Path

def main():
    spec=importlib.util.spec_from_file_location("final_report",Path(__file__).with_name("finalize_v33.py"))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.reports()

if __name__=="__main__":main()
