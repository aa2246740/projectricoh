"""Copy emitting tools before running them; preserve source and routing diffs."""
import difflib
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_common import HERE, ROOT, save

diffs = []
def route(src, dest, replacements):
    before = src.read_text()
    after = before
    for a, b in replacements:
        assert a in after, (str(src), a)
        after = after.replace(a, b)
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(after)
    diffs.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                 fromfile=str(src.relative_to(ROOT)), tofile=str(dest.relative_to(ROOT))))

resident_source = ROOT / "firmware/resident_v36/resident"
route(resident_source / "build.py", HERE / "resident_builder.py", [
    ('HERE=Path(__file__).resolve().parent', f'HERE=Path({str(resident_source)!r})'),
    ("LOCAL=HERE.parent/'local/resident'", f'LOCAL=Path({str(HERE / "resident")!r})')])
route(resident_source / "make_fixture.py", HERE / "make_fixture.py", [
    ('HERE=Path(__file__).resolve().parent', f'HERE=Path({str(resident_source)!r})'),
    ("LOCAL=HERE.parent/'local/resident'", f'LOCAL=Path({str(HERE / "resident")!r})')])
route(ROOT / "research/review_v35_body/rebuild_resident.py", HERE / "rebuild_resident.py", [
    ('ROOT/"firmware/resident_v35/resident/build.py"', 'HERE/"resident_builder.py"'),
    ('firmware/resident_v35', 'firmware/resident_v36'),
    ('9cc5359e073a3b65a223ca3af41055fd10e52b5e701db1fe08426023aea731ba', 'b779cc756a740506415ca5df8eb5c8f08e1b04ea9d8c4c614f7ae971e92b94f7'),
    ('0x20054634', '0x20054638'),
    ('b.HERE/"make_fixture.py"', 'HERE/"make_fixture.py"')])

image_source = ROOT / "firmware/image_v36"
local = HERE / "image"
local.mkdir(exist_ok=True)
code = HERE / "isolated_image_tools"
code.mkdir(exist_ok=True)
for name in ("build.py", "verify.py", "audit.py"):
    if name != "audit.py":
        replacements = [
            ('HERE = Path(__file__).resolve().parent', f'HERE = Path({str(image_source)!r})'),
            ('LOCAL = HERE / "local"', f'LOCAL = Path({str(local)!r})'),
            ('    ignored = subprocess.check_output(["git", "check-ignore", "-v", str(output / "check")], cwd=ROOT, text=True)\n',
             '    ignored = "firmware/image_v36/.gitignore:1:/local/ review-only output redirection"\n')]
        if name == "verify.py":
            replacements += [
                ('str(HERE / "audit.py")', f'str(Path({str(code / "audit.py")!r}))'),
                ('str(HERE / "build.py")', f'str(Path({str(code / "build.py")!r}))')]
    else:
        replacements = [
            ('TASK = Path(__file__).resolve().parent', f'TASK = Path({str(image_source)!r})'),
            ('PRIVATE = TASK / "local"', f'PRIVATE = Path({str(local)!r})')]
    route(image_source / name, code / name, replacements)
(HERE / "build-routing.diff").write_text("".join(diffs))
save("build-routing.json", dict(source=str(image_source), output=str(local), source_logic_unchanged=True))
print("Prepared resident and image tool copies")
