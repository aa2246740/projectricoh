"""原型用的本机静态服务器（只听 127.0.0.1）。

  /proto/...   本目录（页面和着色器）
  /data/...    scratch 里的烘焙数据（代理图、配方表、LUT 表；本机私有，不进仓库）
  /dng/<名字>  原始 DNG 字节（只读，给显卡去马赛克用）
  POST /upload/<名字>  把浏览器读回的像素存到 scratch/readback/

用法：studio/.venv/bin/python serve.py <gpudata 目录> <readback 目录> [端口]
"""

from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DATA = Path(sys.argv[1]).resolve()
READBACK = Path(sys.argv[2]).resolve()
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 49712
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".json": "application/json", ".wgsl": "text/plain; charset=utf-8", ".png": "image/png"}


def inside(root: Path, rel: str) -> Path | None:
    p = (root / rel).resolve()
    return p if p.is_file() and (p == root or root in p.parents) else None


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 安静
        pass

    def send_file(self, p: Path | None) -> None:
        if p is None:
            self.send_error(404)
            return
        body = p.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", TYPES.get(p.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/proto/index.html")
            self.end_headers()
        elif path.startswith("/proto/"):
            self.send_file(inside(HERE, path[len("/proto/") :]))
        elif path.startswith("/data/"):
            self.send_file(inside(DATA, path[len("/data/") :]))
        elif path.startswith("/dng/"):
            name = path[len("/dng/") :]
            meta = inside(DATA, f"{name}/meta.json")
            if meta is None:
                self.send_error(404)
                return
            self.send_file((REPO / json.loads(meta.read_text())["raw"]["file"]).resolve())
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        m = re.fullmatch(r"/upload/([A-Za-z0-9_.\-]+)", self.path)
        if not m:
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(n)
        READBACK.mkdir(parents=True, exist_ok=True)
        (READBACK / m.group(1)).write_bytes(body)
        self.send_response(204)
        self.end_headers()


class Server(ThreadingHTTPServer):
    request_queue_size = 128  # 浏览器会同时开很多连接；默认 5 会被拒
    daemon_threads = True


if __name__ == "__main__":
    srv = Server(("127.0.0.1", PORT), H)
    print(f"http://127.0.0.1:{PORT}/proto/index.html", flush=True)
    srv.serve_forever()
