"""Retained generation 118/119 runners with review-owned outputs."""
from pathlib import Path
import sys
import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_scope import ROOT, SOURCE, OUT, load, save, sha, file_sha

scope=types.ModuleType('scope')
scope.ROOT,scope.OUT=ROOT,SOURCE/'previous_delta'
scope.load,scope.save,scope.sha,scope.file_sha=load,save,sha,file_sha
sys.modules['scope']=scope
sys.path.insert(0,str(scope.OUT))
import service_targets as services
services.d.ex.pb.CACHE=OUT/'previous_decode'
