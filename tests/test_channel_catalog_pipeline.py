import tempfile
import unittest
from pathlib import Path

from tools.validate_channel_catalog import probe_hls_source, probe_logo, validate_catalog


def verified_source():
    return {
        "id": "new_official_hls",
        "type": "DIRECT_HLS",
        "priority": 10,
        "enabled": True,
        "url": "https://media.example/live.m3u8",
        "headers": {},
        "evidence_url": "https://channel.example/live",
        "discovered_at": "2026-10-19",
        "last_verified_at": "2026-10-19",
        "validation_result": "manifest_and_media_segment_ok",
        "notes": "Official public free stream.",
    }


def channel(channel_id="new_channel", **overrides):
    value = {
        "id": channel_id,
        "name": "New Channel",
        "tvg_id": channel_id,
        "enabled": True,
        "logo": "https://channel.example/logo.png",
        "logo_evidence_url": "https://channel.example/",
        "discovered_at": "2026-10-19",
        "sources": [verified_source()],
    }
    value.update(overrides)
    return value


class ChannelCatalogPipelineTests(unittest.TestCase):
    def test_enabled_channel_without_logo_is_rejected(self):
        payload = {"channels": [channel("existing", logo="")]}

        report = validate_catalog(payload, root=Path("."))

        self.assertIn("existing: enabled channel requires a logo", report.errors)

    def test_new_channel_requires_remote_logo_and_publication_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "channels": [
                    channel(
                        logo="resources/data/logos/new_channel.png",
                        logo_evidence_url="",
                        discovered_at="",
                    )
                ]
            }
            Path(tmp, "resources/data/logos").mkdir(parents=True)
            Path(tmp, "resources/data/logos/new_channel.png").write_bytes(b"png")

            report = validate_catalog(payload, root=Path(tmp), base_payload={"channels": []})

        self.assertIn("new_channel: new channel logo must use HTTPS so installed addons can receive it", report.errors)
        self.assertIn("new_channel: new channel requires logo_evidence_url", report.errors)
        self.assertIn("new_channel: new channel requires discovered_at", report.errors)

    def test_new_channel_requires_name_and_tvg_id(self):
        payload = {"channels": [channel(name="", tvg_id="")]}

        report = validate_catalog(payload, root=Path("."), base_payload={"channels": []})

        self.assertIn("new_channel: new channel requires name", report.errors)
        self.assertIn("new_channel: new channel requires tvg_id", report.errors)

    def test_new_channel_requires_complete_source_verification_metadata(self):
        incomplete = verified_source()
        incomplete.pop("validation_result")
        incomplete.pop("discovered_at")
        payload = {"channels": [channel(sources=[incomplete])]}

        report = validate_catalog(payload, root=Path("."), base_payload={"channels": []})

        self.assertIn("new_channel/new_official_hls: requires discovered_at", report.errors)
        self.assertIn(
            "new_channel/new_official_hls: validation_result must be manifest_and_media_segment_ok",
            report.errors,
        )

    def test_complete_new_channel_metadata_passes(self):
        payload = {"channels": [channel()]}

        report = validate_catalog(payload, root=Path("."), base_payload={"channels": []})

        self.assertEqual(report.errors, [])
        self.assertEqual(report.new_channel_ids, ["new_channel"])

    def test_hls_probe_fetches_variant_and_complete_media_segment(self):
        responses = {
            "https://media.example/master.m3u8": b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=1000\nquality/index.m3u8\n",
            "https://media.example/quality/index.m3u8": b"#EXTM3U\n#EXTINF:6,\nsegment.ts\n",
            "https://media.example/quality/segment.ts": bytes([0x47]) + (b"x" * 187),
        }
        requested = []

        class Response:
            status = 200
            headers = {"Content-Type": "application/octet-stream"}

            def __init__(self, body):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self, size=-1):
                return self.body if size < 0 else self.body[:size]

        def open_url(request, timeout):
            requested.append(request.full_url)
            return Response(responses[request.full_url])

        ok, message = probe_hls_source("https://media.example/master.m3u8", timeout=1, http_open=open_url)

        self.assertTrue(ok, message)
        self.assertEqual(
            requested,
            [
                "https://media.example/master.m3u8",
                "https://media.example/quality/index.m3u8",
                "https://media.example/quality/segment.ts",
            ],
        )

    def test_logo_probe_requires_a_useful_png_size(self):
        class Response:
            status = 200
            headers = {"Content-Type": "image/png"}

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self, size=-1):
                return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + (512).to_bytes(4, "big") + (512).to_bytes(4, "big")

        ok, message = probe_logo(
            "https://channel.example/logo.png",
            timeout=1,
            http_open=lambda request, timeout: Response(),
        )

        self.assertTrue(ok, message)


if __name__ == "__main__":
    unittest.main()
