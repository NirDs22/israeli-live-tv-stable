import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from resources.lib.pvr import (
    configure_iptv_simple_url,
    enable_pvr_manager,
    iptv_simple_manual_instructions,
    repair_iptv_simple_instance_settings,
    setup_kodi_tv,
    validate_generated_m3u,
)


class PVRTests(unittest.TestCase):
    def test_manual_instructions_include_m3u_path(self):
        text = iptv_simple_manual_instructions("/tmp/live.m3u")
        self.assertIn("/tmp/live.m3u", text)
        self.assertIn("PVR IPTV Simple Client", text)
        self.assertIn("TV -> Channels", text)

    def test_setup_handles_missing_iptv_simple_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            playlist = Path(tmp) / "live.m3u"
            playlist.write_text("#EXTM3U\n#EXTINF:-1,Test\nhttps://example.com/live.m3u8\n", encoding="utf-8")
            with patch("resources.lib.pvr.iptv_simple_status", return_value=(False, "not detected")):
                result = setup_kodi_tv(playlist, 12)
            self.assertFalse(result.ok)
            self.assertIn("not installed", result.message)
            self.assertIn(str(playlist), result.manual_instructions)

    def test_setup_success_requires_instance_repair_even_when_public_settings_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            playlist = Path(tmp) / "live.m3u"
            playlist.write_text("#EXTM3U\n#EXTINF:-1,Test\nhttps://example.com/live.m3u8\n", encoding="utf-8")
            repair_result = type("Result", (), {"ok": True, "mode": "instance repair", "message": "repaired", "path": "/tmp/instance.xml", "backup_path": "/tmp/instance.xml.bak"})()
            with patch("resources.lib.pvr.iptv_simple_status", return_value=(True, "installed")), patch(
                "resources.lib.pvr.enable_iptv_simple", return_value=(True, "enabled")
            ), patch("resources.lib.pvr.enable_pvr_manager", return_value=(True, "pvr enabled")), patch(
                "resources.lib.pvr.configure_iptv_simple", return_value=(True, "configured")
            ), patch("resources.lib.pvr.verify_iptv_simple_local_file", return_value=(True, "verified")), patch(
                "resources.lib.pvr.repair_iptv_simple_instance_settings", return_value=repair_result
            ) as repair, patch("resources.lib.pvr.restart_iptv_simple_client", return_value=(True, "restarted")), patch(
                "resources.lib.pvr.reload_pvr", return_value=(True, "reloaded")
            ):
                result = setup_kodi_tv(playlist, 12)
        self.assertTrue(result.ok)
        self.assertIn("Kodi TV was repaired", result.message)
        self.assertEqual(result.manual_instructions, "")
        self.assertEqual(result.setup_mode, "instance repair")
        self.assertEqual(result.playlist_entry_count, 1)
        repair.assert_called_once()

    def test_pvr_manager_invalid_params_is_friendly_optional_warning(self):
        with patch("resources.lib.pvr._json_rpc", return_value={"error": {"code": -32602, "message": "Invalid params."}}):
            ok, message = enable_pvr_manager()
        self.assertFalse(ok)
        self.assertIn("did not allow automatic PVR manager enabling", message)
        self.assertNotIn("-32602", message)

    def test_setup_succeeds_when_optional_pvr_manager_enable_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            playlist = Path(tmp) / "live.m3u"
            playlist.write_text("#EXTM3U\n#EXTINF:-1,Test\nhttps://example.com/live.m3u8\n", encoding="utf-8")
            repair_result = type("Result", (), {"ok": True, "mode": "instance repair", "message": "repaired", "path": "", "backup_path": ""})()
            with patch("resources.lib.pvr.iptv_simple_status", return_value=(True, "installed")), patch(
                "resources.lib.pvr.enable_iptv_simple", return_value=(True, "enabled")
            ), patch(
                "resources.lib.pvr.enable_pvr_manager",
                return_value=(False, "Kodi did not allow automatic PVR manager enabling. If TV is missing, enable PVR in Kodi settings."),
            ), patch("resources.lib.pvr.configure_iptv_simple", return_value=(True, "configured")), patch(
                "resources.lib.pvr.verify_iptv_simple_local_file", return_value=(True, "verified")
            ), patch("resources.lib.pvr.repair_iptv_simple_instance_settings", return_value=repair_result), patch(
                "resources.lib.pvr.restart_iptv_simple_client", return_value=(True, "restarted")
            ), patch(
                "resources.lib.pvr.reload_pvr", return_value=(True, "reloaded")
            ):
                result = setup_kodi_tv(playlist, 13)
        self.assertTrue(result.ok)
        self.assertIn("Kodi TV was repaired", result.message)
        self.assertIn("Optional step skipped", result.technical_details)
        self.assertNotIn("Invalid params", result.technical_details)

    def test_url_setup_uses_iptv_simple_remote_playlist_settings(self):
        settings = {}

        class FakeAddon:
            def __init__(self, id=None):
                self.id = id

            def setSetting(self, key, value):
                settings[key] = value

        with patch.dict("sys.modules", {"xbmcaddon": type("FakeModule", (), {"Addon": FakeAddon})}):
            ok, message = configure_iptv_simple_url("http://127.0.0.1:41555/playlist.m3u")
        self.assertTrue(ok)
        self.assertEqual(settings["m3uPathType"], "1")
        self.assertEqual(settings["m3uUrl"], "http://127.0.0.1:41555/playlist.m3u")
        self.assertIn("local playlist URL", message)

    def test_setup_ignores_url_as_success_path_and_requires_instance_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            playlist = Path(tmp) / "live.m3u"
            playlist.write_text("#EXTM3U\n#EXTINF:-1,Test\nhttps://example.com/live.m3u8\n", encoding="utf-8")
            repair_result = type("Result", (), {"ok": True, "mode": "instance repair", "message": "repaired", "path": "", "backup_path": ""})()
            with patch("resources.lib.pvr.iptv_simple_status", return_value=(True, "installed")), patch(
                "resources.lib.pvr.enable_iptv_simple", return_value=(True, "enabled")
            ), patch("resources.lib.pvr.enable_pvr_manager", return_value=(True, "pvr enabled")), patch(
                "resources.lib.pvr.configure_iptv_simple_url", return_value=(True, "configured url")
            ) as configure_url, patch("resources.lib.pvr.configure_iptv_simple", return_value=(True, "configured file")) as configure_file, patch(
                "resources.lib.pvr.verify_iptv_simple_local_file", return_value=(True, "verified")
            ), patch("resources.lib.pvr.repair_iptv_simple_instance_settings", return_value=repair_result), patch(
                "resources.lib.pvr.restart_iptv_simple_client", return_value=(True, "restarted")
            ), patch(
                "resources.lib.pvr.reload_pvr", return_value=(True, "reloaded")
            ):
                result = setup_kodi_tv(playlist, 13, "http://127.0.0.1:41555/playlist.m3u")
        self.assertTrue(result.ok)
        configure_file.assert_called_once()
        configure_url.assert_not_called()
        self.assertNotIn("Fallback local URL setup", result.technical_details)

    def test_setup_fails_when_instance_repair_fails_even_if_url_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            playlist = Path(tmp) / "live.m3u"
            playlist.write_text("#EXTM3U\n#EXTINF:-1,Test\nhttps://example.com/live.m3u8\n", encoding="utf-8")
            repair_result = type("Result", (), {"ok": False, "mode": "manual fallback", "message": "repair failed", "path": "", "backup_path": ""})()
            with patch("resources.lib.pvr.iptv_simple_status", return_value=(True, "installed")), patch(
                "resources.lib.pvr.enable_iptv_simple", return_value=(True, "enabled")
            ), patch("resources.lib.pvr.enable_pvr_manager", return_value=(True, "pvr enabled")), patch(
                "resources.lib.pvr.configure_iptv_simple_url", return_value=(True, "configured url")
            ) as configure_url, patch("resources.lib.pvr.configure_iptv_simple", return_value=(True, "configured file")), patch(
                "resources.lib.pvr.verify_iptv_simple_local_file", return_value=(True, "verified")
            ), patch("resources.lib.pvr.repair_iptv_simple_instance_settings", return_value=repair_result), patch(
                "resources.lib.pvr.reload_pvr", return_value=(True, "reloaded")
            ):
                result = setup_kodi_tv(playlist, 13, "http://127.0.0.1:41555/playlist.m3u")
        self.assertFalse(result.ok)
        self.assertIn("could not be completed", result.message)
        configure_url.assert_not_called()

    def test_setup_uses_instance_repair_when_official_settings_do_not_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            playlist = Path(tmp) / "live.m3u"
            playlist.write_text("#EXTM3U\n#EXTINF:-1,Test\nhttps://example.com/live.m3u8\n", encoding="utf-8")
            repair_result = type("Result", (), {"ok": True, "mode": "instance repair", "message": "repaired", "path": "", "backup_path": ""})()
            with patch("resources.lib.pvr.iptv_simple_status", return_value=(True, "installed")), patch(
                "resources.lib.pvr.enable_iptv_simple", return_value=(True, "enabled")
            ), patch("resources.lib.pvr.enable_pvr_manager", return_value=(True, "pvr enabled")), patch(
                "resources.lib.pvr.configure_iptv_simple", return_value=(True, "configured")
            ), patch("resources.lib.pvr.verify_iptv_simple_local_file", return_value=(False, "not applied")), patch(
                "resources.lib.pvr.repair_iptv_simple_instance_settings", return_value=repair_result
            ), patch(
                "resources.lib.pvr.restart_iptv_simple_client", return_value=(True, "restarted")
            ), patch("resources.lib.pvr.reload_pvr", return_value=(True, "reloaded")):
                result = setup_kodi_tv(playlist, 13)
        self.assertFalse(result.ok)
        self.assertEqual(result.setup_mode, "instance repair")
        self.assertIn("repaired", result.technical_details)
        self.assertIn("restarted", result.technical_details)
        self.assertIn("could not be completed", result.message)

    def test_setup_rejects_empty_generated_playlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            playlist = Path(tmp) / "live.m3u"
            playlist.write_text("#EXTM3U\n", encoding="utf-8")
            result = setup_kodi_tv(playlist, 0)
        self.assertFalse(result.ok)
        self.assertIn("playlist is not valid", result.message)
        self.assertEqual(result.playlist_entry_count, 0)

    def test_validate_generated_m3u_counts_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            playlist = Path(tmp) / "live.m3u"
            playlist.write_text("#EXTM3U\n#EXTINF:-1,A\nurl-a\n#EXTINF:-1,B\nurl-b\n", encoding="utf-8")
            ok, count, message = validate_generated_m3u(playlist)
        self.assertTrue(ok)
        self.assertEqual(count, 2)
        self.assertIn("2 channels", message)

    def test_instance_repair_backs_up_and_updates_known_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp)
            settings = profile / "instance-settings-1.xml"
            settings.write_text(
                '<settings version="2"><setting id="m3uPathType" value="1" /><setting id="m3uPath">old</setting><setting id="startNum" value="9" /><setting id="untouched" value="keep" /></settings>',
                encoding="utf-8",
            )
            result = repair_iptv_simple_instance_settings("/tmp/live.m3u", profile)
            self.assertTrue(result.ok)
            self.assertEqual(result.mode, "instance repair")
            self.assertTrue(Path(result.backup_path).exists())
            text = settings.read_text(encoding="utf-8")
            self.assertIn('id="m3uPathType" value="0"', text)
            self.assertIn("/tmp/live.m3u", text)
            self.assertIn('id="untouched" value="keep"', text)

    def test_instance_repair_rejects_unknown_xml_shape_without_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp)
            settings = profile / "instance-settings-1.xml"
            settings.write_text("<notsettings><item /></notsettings>", encoding="utf-8")
            result = repair_iptv_simple_instance_settings("/tmp/live.m3u", profile)
            self.assertFalse(result.ok)
            self.assertEqual(result.mode, "manual fallback")
            self.assertFalse((profile / "instance-settings-1.xml.bak").exists())

    def test_instance_repair_handles_missing_profile_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"
            result = repair_iptv_simple_instance_settings("/tmp/live.m3u", missing)
            self.assertFalse(result.ok)
            self.assertEqual(result.mode, "manual fallback")
            self.assertIn("does not exist", result.message)


if __name__ == "__main__":
    unittest.main()
