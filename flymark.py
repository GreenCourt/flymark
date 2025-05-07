#!/usr/bin/env python3
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess
from datetime import datetime, UTC
import argparse
from shutil import which
import urllib.parse
import traceback
import json
from pathlib import Path
from threading import Thread, Lock

lock = Lock()
markdown: bytes = b"No content."
directory: str = ""
last_modified: datetime = datetime.now(UTC)
content_type = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
}


def pandoc() -> bytes:
    try:
        with lock:
            return subprocess.run(
                [
                    "pandoc",
                    "-s",
                    "-f",
                    "gfm",
                    "-t",
                    "html",
                    "--katex",
                    "-H",
                    Path(__file__).parent.joinpath("include.html"),
                ],
                input=markdown,
                capture_output=True,
                check=True,
                timeout=5,
            ).stdout
    except subprocess.CalledProcessError as e:
        return b"<pre>" + e.stderr + b"</pre>"
    except Exception:
        return ("<pre>" + traceback.format_exc() + "</pre>").encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _parse_path(self) -> tuple[str, Path]:
        u = urllib.parse.urlparse(self.path)
        with lock:
            local_path = Path(
                directory,
                urllib.parse.unquote(u.path[1:] if u.path[0] == "/" else u.path),
            )
        return u.path, local_path

    def do_HEAD(self):
        url_path, local_path = self._parse_path()
        fmt = "%a, %d %b %Y %H:%M:%S GMT"

        if url_path == "/":
            with lock:
                lm = last_modified.strftime(fmt)
        elif local_path.suffix in content_type and local_path.is_file():
            lm = datetime.fromtimestamp(local_path.stat().st_mtime).strftime(fmt)
        else:
            self.send_response(403)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Last-Modified", lm)
        self.end_headers()

    def do_GET(self):
        url_path, local_path = self._parse_path()

        if url_path == "/":
            body = pandoc()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if local_path.suffix not in content_type or not local_path.is_file():
            self.send_response(403)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type[local_path.suffix])
        self.end_headers()
        with open(local_path, "rb") as f:
            while b := f.read(4096):
                self.wfile.write(b)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    if which("pandoc") is None:
        print("pandoc not found.", file=sys.stderr)
        sys.exit(1)

    with HTTPServer((args.bind, args.port), Handler) as s:
        print(f"listening at {s.server_address[0]}:{s.server_address[1]}")
        Thread(target=s.serve_forever, daemon=True).start()

        for line in sys.stdin:
            js = json.loads(line)
            with lock:
                last_modified = datetime.now(UTC)
                markdown = js["markdown"].encode("utf-8")
                directory = js["directory"]
