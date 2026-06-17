from __future__ import annotations


def iptv_simple_manual_instructions(m3u_path: str) -> str:
    return (
        "IPTV Simple automatic repair is not implemented in V1. "
        "Open Kodi settings, enable PVR IPTV Simple Client, set the M3U playlist path to: "
        f"{m3u_path}"
    )
