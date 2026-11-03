"""Observe the retained UI helper on the frozen candidate."""
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'research/review_g126'))
import ui_test_support
session=ui_test_support.Session(unit='50mm',tag='field-probe')
state=session.state()
print(json.dumps({'name':'ui_field_probe','returncode':0,'row_count':len(state['labels']),'screen':state['screen']}))
