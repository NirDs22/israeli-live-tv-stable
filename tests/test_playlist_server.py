import tempfile
import unittest
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from resources.lib.playlist_server import PLAYLIST_PATH, PlaylistServer, playlist_server_status


@contextmanager
def started_server(testcase, playlist):
    server = PlaylistServer(playlist, port=0)
    try:
        try:
            server.start()
        except PermissionError as exc:
            testcase.skipTest(f"localhost bind is blocked in this environment: {exc}")
        yield server
    finally:
        server.stop()


class PlaylistServerTests(unittest.TestCase):
    def test_playlist_server_serves_m3u_from_localhost(self):
        with tempfile.TemporaryDirectory() as tmp:
            playlist = Path(tmp) / "playlist.m3u"
            playlist.write_text("#EXTM3U\n#EXTINF:-1,Test\nhttps://example.com/live.m3u8\n", encoding="utf-8")
            with started_server(self, playlist) as server:
                self.assertEqual(server.host, "127.0.0.1")
                self.assertTrue(server.running)
                with urllib.request.urlopen(server.url, timeout=2) as response:
                    body = response.read().decode("utf-8")
                self.assertTrue(body.startswith("#EXTM3U"))

    def test_playlist_server_status_reports_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            playlist = Path(tmp) / "playlist.m3u"
            playlist.write_text("#EXTM3U\n", encoding="utf-8")
            with started_server(self, playlist) as server:
                ok, status = playlist_server_status(server.actual_port, timeout=2)
                self.assertTrue(ok)
                self.assertEqual(status, "running")

    def test_playlist_server_returns_404_for_other_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            playlist = Path(tmp) / "playlist.m3u"
            playlist.write_text("#EXTM3U\n", encoding="utf-8")
            with started_server(self, playlist) as server:
                with self.assertRaises(Exception):
                    urllib.request.urlopen(server.url.replace(PLAYLIST_PATH, "/nope"), timeout=2)


if __name__ == "__main__":
    unittest.main()
