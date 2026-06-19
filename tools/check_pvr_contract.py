#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise SystemExit(message)


def main() -> int:
    pvr = (ROOT / "resources" / "lib" / "pvr.py").read_text(encoding="utf-8")
    router = (ROOT / "resources" / "lib" / "router.py").read_text(encoding="utf-8")
    diagnostics = (ROOT / "resources" / "lib" / "diagnostics.py").read_text(encoding="utf-8")
    tests = (ROOT / "tests" / "test_pvr.py").read_text(encoding="utf-8")

    require(pvr, "configure_iptv_simple(path_text)", "PVR setup must configure stable local M3U file first.")
    require(pvr, "verify_iptv_simple_local_file", "PVR setup must verify official IPTV Simple settings.")
    require(pvr, "repair_iptv_simple_instance_settings", "PVR setup must include instance settings repair fallback.")
    require(pvr, "validate_generated_m3u", "PVR setup must validate generated M3U before reporting success.")
    require(pvr, "_copy_file(settings_path, backup_path)", "Instance settings repair must backup XML before editing.")
    require(pvr, "_xbmcvfs_module", "Instance settings repair must include Kodi xbmcvfs fallback for Android permission errors.")
    require(pvr, "restart_iptv_simple_client", "Instance repair must restart IPTV Simple after XML repair.")
    require(pvr, "Kodi TV was repaired", "PVR setup success message must use repair wording.")
    if "Fallback local URL setup" in pvr:
        raise SystemExit("PVR setup must not use local URL fallback as a success path.")
    require(router, "set_pvr_setup_status", "Setup flow must record PVR setup status for diagnostics.")
    require(diagnostics, "IPTV Simple setup mode:", "Diagnostics must show IPTV Simple setup mode.")
    require(tests, "test_instance_repair_backs_up_and_updates_known_settings", "PVR tests must cover XML backup and repair.")
    require(tests, "test_setup_success_requires_instance_repair_even_when_public_settings_verify", "PVR tests must require instance repair for success.")
    require(tests, "test_setup_rejects_empty_generated_playlist", "PVR tests must reject empty generated playlists.")

    print("PVR setup contract OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
