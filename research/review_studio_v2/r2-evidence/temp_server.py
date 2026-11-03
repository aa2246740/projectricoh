"""Serve only the disposable acceptance library on a fresh loopback port."""
from __future__ import annotations
import json
import os
from pathlib import Path
import socket
import sys
import uvicorn

HERE = Path(__file__).resolve().parent
STUDIO = Path('/Volumes/Workspace/Projects/T3-Runtime/projects/projectricoh/studio')
SCRATCH = Path("/Volumes/Workspace/Scratch/tmp/projectricoh/review-studio-v2-r2")
sys.path.insert(0, str(STUDIO / "src"))
from gxr_studio import audit
from gxr_studio.app import create_app
from gxr_studio.config import Settings

audit.forbid_volumes()
for path in (Path.home() / "Pictures/GXR Studio", Path.home() / "Pictures/GXR 导出",
             Path.home() / "Library/Application Support/GXR Studio"):
    audit.protect(path)
    audit.forbid_reads(path)
os.environ.pop("GXR_STUDIO_SENTRY_DSN", None)
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(("127.0.0.1", 0))
port = sock.getsockname()[1]
settings = Settings(library_dir=SCRATCH / "library", home_dir=SCRATCH / "app-home",
                    export_dir=SCRATCH / "exports", volumes_roots=(), web_dir=STUDIO / "web",
                    port=port, token="independent-review-browser", min_free_bytes=0)
ready = {"port": port, "pid": os.getpid(), "url": f"http://127.0.0.1:{port}/?token={settings.token}"}
(SCRATCH / "server-ready.json").write_text(json.dumps(ready))
print(json.dumps(ready), flush=True)
uvicorn.Server(uvicorn.Config(create_app(settings), log_level="warning")).run(sockets=[sock])
