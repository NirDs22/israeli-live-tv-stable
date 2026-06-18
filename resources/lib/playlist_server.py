from __future__ import annotations

import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable


DEFAULT_PLAYLIST_HOST = "127.0.0.1"
DEFAULT_PLAYLIST_PORT = 41555
PLAYLIST_PATH = "/playlist.m3u"


class PlaylistServer:
    def __init__(
        self,
        playlist_path: Path,
        *,
        host: str = DEFAULT_PLAYLIST_HOST,
        port: int = DEFAULT_PLAYLIST_PORT,
        refresh: Callable[[], None] | None = None,
    ) -> None:
        self.playlist_path = playlist_path
        self.host = host
        self.port = port
        self.refresh = refresh
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return playlist_url(self.actual_port, self.host)

    @property
    def actual_port(self) -> int:
        if self._httpd:
            return int(self._httpd.server_address[1])
        return self.port

    @property
    def running(self) -> bool:
        return bool(self._httpd and self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.running:
            return

        playlist_path = self.playlist_path
        refresh = self.refresh

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib handler method name.
                if self.path.split("?", 1)[0] != PLAYLIST_PATH:
                    self.send_error(404)
                    return
                if refresh:
                    try:
                        refresh()
                    except Exception:
                        pass
                if not playlist_path.exists():
                    self.send_response(503)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"Playlist is not generated yet.\n")
                    return
                data = playlist_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format: str, *args: object) -> None:
                return

        self._httpd = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="IsraeliLiveTVPlaylistServer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
        self._httpd = None
        self._thread = None


def playlist_url(port: int = DEFAULT_PLAYLIST_PORT, host: str = DEFAULT_PLAYLIST_HOST) -> str:
    return f"http://{host}:{port}{PLAYLIST_PATH}"


def playlist_server_status(port: int = DEFAULT_PLAYLIST_PORT, host: str = DEFAULT_PLAYLIST_HOST, timeout: float = 0.5) -> tuple[bool, str]:
    request = urllib.request.Request(playlist_url(port, host), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            sample = response.read(32)
            if getattr(response, "status", 200) == 200 and sample.startswith(b"#EXTM3U"):
                return True, "running"
            return False, "responded but playlist was not valid"
    except urllib.error.HTTPError as exc:
        return False, f"not ready: HTTP {exc.code}"
    except Exception as exc:
        return False, f"not running: {exc}"
