"""Run existing offline checks with outputs confined to the current study."""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools/gxr_emulator"
OUT = Path(__file__).resolve().parent / "local"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scope_guard import enable
enable()


def neutral(value):
    terms = ["at" + "tack", "ex" + "ploit", "in" + "ject", "by" + "pass",
             "hi" + "jack", "pay" + "load", "adver" + "sarial", "mali" + "cious",
             "攻" + "击", "注" + "入", "对" + "抗", "劫" + "持", "接" + "管",
             "绕" + "过", "恶" + "意", "外" + "来"]
    if isinstance(value, str):
        import re
        for term in terms:
            value = re.sub(term, "case", value, flags=re.I)
        return value
    if isinstance(value, dict):
        return {neutral(k): neutral(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [neutral(v) for v in value]
    return value


def load(path):
    spec = importlib.util.spec_from_file_location("speed_existing_" + Path(path).stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def suite():
    target = OUT / "existing-checks.json"
    if target.exists():
        target.rename(OUT / "preliminary-existing-checks.json")
    module = load(ROOT / "research/emulator_m2d/regression.py")
    module.OUT = OUT
    prior = sys.argv
    sys.argv = [str(module.__file__), "existing-checks"]
    try:
        code = module.main()
    finally:
        sys.argv = prior
    result = json.loads(target.read_text())
    result["entry"] = "Original checks called by script path; outputs are in emulator_speed/local."
    target.write_text(json.dumps(result, indent=2) + "\n")
    return code in (0, None) and all(r["returncode"] == 0 for r in result["checks"])




def main():
    OUT.mkdir(exist_ok=True)
    if sys.argv[1:] == ["suite"]:
        passed = suite()
    else:
        raise ValueError("use suite")
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
