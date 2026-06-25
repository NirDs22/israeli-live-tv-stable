import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from resources.lib.utils import read_json, write_json
from tools import check_channels


def source(source_id, priority=10, url=None):
    return {
        "id": source_id,
        "type": "DIRECT_HLS",
        "priority": priority,
        "enabled": True,
        "url": url or f"https://example.com/{source_id}.m3u8",
        "headers": {},
        "mime_type": "application/vnd.apple.mpegurl",
        "requires_inputstream_adaptive": False,
        "evidence_url": "https://example.com/live",
        "notes": "Test source",
    }


class ChannelHealthToolTests(unittest.TestCase):
    def args(self, tmp, **overrides):
        base = Path(tmp)
        values = {
            "channels": str(base / "channels.json"),
            "candidates": str(base / "channel_candidates.json"),
            "report_json": str(base / "report.json"),
            "report_markdown": str(base / "report.md"),
            "timeout": 1,
            "apply_fallbacks": False,
            "apply_candidates": False,
            "dry_run": False,
            "fail_on_broken": False,
        }
        values.update(overrides)
        return Namespace(**values)

    def write_channels(self, tmp, sources):
        write_json(
            Path(tmp) / "channels.json",
            {"channels": [{"id": "kan11", "name": "Kan 11", "enabled": True, "sources": sources}]},
        )

    def write_candidates(self, tmp, candidates):
        write_json(Path(tmp) / "channel_candidates.json", {"channels": {"kan11": candidates}, "rejected": []})

    def test_broken_primary_with_working_fallback_promotes_fallback_and_still_needs_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_channels(tmp, [source("primary", 10), source("fallback", 30)])
            self.write_candidates(tmp, [])

            def fake_check(item, timeout):
                return (False, "http_404") if item["id"] == "primary" else (True, "ok")

            with patch("tools.check_channels.check_url", side_effect=fake_check):
                code = check_channels.run(self.args(tmp, apply_fallbacks=True))

            self.assertEqual(code, 0)
            payload = read_json(Path(tmp) / "channels.json")
            sources = {item["id"]: item for item in payload["channels"][0]["sources"]}
            self.assertEqual(sources["fallback"]["priority"], 10)
            self.assertEqual(sources["primary"]["priority"], 30)

            report = read_json(Path(tmp) / "report.json")
            summary = report["channels"][0]
            self.assertTrue(summary["fallback_promoted"])
            self.assertTrue(summary["replacement_search_needed"])

    def test_keshet12_checks_entitlement_flow_and_uses_runtime_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_json(
                Path(tmp) / "channels.json",
                {"channels": [{"id": "keshet12", "name": "Keshet 12", "enabled": True, "sources": [source("primary", 10), source("fallback", 30)]}]},
            )
            write_json(Path(tmp) / "channel_candidates.json", {"channels": {"keshet12": []}, "rejected": []})

            calls = []

            def fake_entitlement_check(relative_path, timeout):
                calls.append(relative_path)
                return (False, "keshet12_not_found") if len(calls) == 1 else (True, "ok")

            with patch("tools.check_channels.check_public_entitlement_path", side_effect=fake_entitlement_check):
                check_channels.run(self.args(tmp, apply_fallbacks=True, apply_candidates=True))

            report = read_json(Path(tmp) / "report.json")
            keshet12 = report["keshet12"]
            self.assertTrue(keshet12["checked"])
            self.assertTrue(keshet12["replacement_search_needed"])
            self.assertTrue(keshet12["repair_attempted"])
            self.assertFalse(keshet12["fallback_promoted"])
            self.assertEqual(keshet12["resolver_mode"], "dynamic_public_entitlement")
            self.assertIn("runtime resolver", keshet12["repair_actions"][0])
            self.assertGreaterEqual(len(calls), 2)

            payload = read_json(Path(tmp) / "channels.json")
            self.assertEqual(payload["channels"][0]["sources"][0]["priority"], 10)

    def test_keshet12_checker_does_not_store_tokenized_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_json(
                Path(tmp) / "channels.json",
                {"channels": [{"id": "keshet12", "name": "Keshet 12", "enabled": True, "sources": []}]},
            )
            write_json(Path(tmp) / "channel_candidates.json", {"channels": {"keshet12": []}, "rejected": []})
            with patch("tools.check_channels.check_public_entitlement_path", return_value=(True, "ok")):
                check_channels.run(self.args(tmp))

            report_text = (Path(tmp) / "report.json").read_text(encoding="utf-8")
            self.assertNotIn("mako-streaming.akamaized.net", report_text)
            self.assertNotIn("ticket=", report_text)
            self.assertIn("/direct/hls/live/", report_text)

    def test_missing_keshet12_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_channels(tmp, [source("primary", 10)])
            self.write_candidates(tmp, [])
            with patch("tools.check_channels.check_url", return_value=(True, "ok")):
                check_channels.run(self.args(tmp, apply_fallbacks=True, apply_candidates=True))

            report = read_json(Path(tmp) / "report.json")
            self.assertFalse(report["keshet12"]["checked"])
            self.assertTrue(report["keshet12"]["replacement_search_needed"])

    def test_retired_channels_are_ignored_by_automation(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_json(
                Path(tmp) / "channels.json",
                {
                    "channels": [
                        {"id": "keshet12", "name": "Keshet 12", "enabled": True, "sources": []},
                        {"id": "makan33", "name": "Makan 33", "enabled": True, "sources": [source("makan")]},
                        {"id": "ynet_live", "name": "Ynet Live", "enabled": True, "sources": [source("ynet")]},
                    ]
                },
            )
            write_json(Path(tmp) / "channel_candidates.json", {"channels": {}, "rejected": []})
            with patch("tools.check_channels.check_public_entitlement_path", return_value=(True, "ok")), patch(
                "tools.check_channels.check_url"
            ) as static_check:
                check_channels.run(self.args(tmp))

            static_check.assert_not_called()
            report = read_json(Path(tmp) / "report.json")
            channel_ids = {channel["channel_id"] for channel in report["channels"]}
            source_channel_ids = {source_item["channel_id"] for source_item in report["sources"]}
            self.assertNotIn("makan33", channel_ids)
            self.assertNotIn("ynet_live", channel_ids)
            self.assertNotIn("makan33", source_channel_ids)
            self.assertNotIn("ynet_live", source_channel_ids)

    def test_broken_fallback_triggers_replacement_search_even_when_primary_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_channels(tmp, [source("primary", 10), source("fallback", 30)])
            self.write_candidates(tmp, [])

            def fake_check(item, timeout):
                return (False, "http_404") if item["id"] == "fallback" else (True, "ok")

            with patch("tools.check_channels.check_url", side_effect=fake_check):
                check_channels.run(self.args(tmp))

            report = read_json(Path(tmp) / "report.json")
            summary = report["channels"][0]
            self.assertTrue(summary["primary_ok"])
            self.assertEqual(summary["working_source_count"], 1)
            self.assertTrue(summary["replacement_search_needed"])

    def test_candidate_without_evidence_is_rejected(self):
        candidate = source("candidate", 80)
        candidate.pop("evidence_url")
        valid, message = check_channels.validate_candidate(candidate)
        self.assertFalse(valid)
        self.assertIn("evidence_url", message)

    def test_valid_candidate_is_added_as_lower_priority_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_channels(tmp, [source("primary", 10)])
            self.write_candidates(tmp, [source("candidate", 20, "https://example.com/candidate.m3u8")])

            def fake_check(item, timeout):
                return (False, "http_404") if item["id"] == "primary" else (True, "ok")

            with patch("tools.check_channels.check_url", side_effect=fake_check):
                check_channels.run(self.args(tmp, apply_candidates=True))

            payload = read_json(Path(tmp) / "channels.json")
            sources = {item["id"]: item for item in payload["channels"][0]["sources"]}
            self.assertIn("candidate", sources)
            self.assertEqual(sources["candidate"]["priority"], 70)
            self.assertFalse(sources["candidate"]["is_user_configured"])

            report = read_json(Path(tmp) / "report.json")
            self.assertEqual(report["candidates"][0]["status"], "added_as_fallback")

    def test_all_sources_broken_is_reported_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write_channels(tmp, [source("primary", 10), source("fallback", 30)])
            self.write_candidates(tmp, [])

            with patch("tools.check_channels.check_url", return_value=(False, "dns_error")):
                check_channels.run(self.args(tmp))

            report = read_json(Path(tmp) / "report.json")
            summary = report["channels"][0]
            self.assertTrue(summary["all_sources_broken"])
            self.assertEqual(summary["broken_source_count"], 2)


if __name__ == "__main__":
    unittest.main()
