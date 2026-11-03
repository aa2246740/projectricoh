"""Freeze training-selected, replayed records before rendering a fresh RAW holdout."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runtime_std as rt
import argparse
from report import collect


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tag',required=True);args=ap.parse_args()
    assert Path(args.tag).name==args.tag
    rows,_,_,_=collect(include_new7=False)
    assert len(rows)==105 and all(r['verified_record_replay'] for r in rows)
    out=rt.LOCAL/args.tag/'candidate_registry.json'
    assert not out.exists()
    rt.dump(out,dict(label='电脑预测',created_utc=rt.utc(),profiles=rows,
        completed_main_profiles=105,heldout_parameters_not_selected=True))
    print('Fresh holdout bank',str(out.relative_to(rt.HERE)))


if __name__=='__main__':main()
