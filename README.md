# Israeli Live TV Stable

Israeli Live TV Stable is a lightweight Kodi video addon for live TV only.

The goal is boring stability: open the addon, browse live channels, play a configured legal source, and get a clear explanation when playback is unavailable.

## What It Does

- Shows a fast Live Channels list.
- Loads bundled channel metadata from local JSON.
- Supports user-provided legal direct HLS/DASH sources.
- Supports optional user-owned local TVHeadend mappings.
- Resolves sources with fallback and last-known-good cache.
- Plays through Kodi resolved URL APIs.
- Generates a simple M3U file containing only playable configured/legal sources.
- Can set up Kodi's native TV menu through PVR IPTV Simple Client.
- Provides Diagnostics for config paths, cache state, source failures, and addon status.

## What It Does Not Do

- No VOD in V1.
- No radio in V1.
- No scraping-first design.
- No pirated IPTV lists.
- No paid channels.
- No DRM bypass, authentication bypass, token generation, fake headers, fake cookies, fake device IDs, Cloudflare bypass, geo-blocking bypass, or protected API access.
- No Fishenzon source code or assets are copied.

Fishenzon was used only as reference material for Kodi packaging patterns, data-shape pitfalls, and instability lessons.

## Source Resolution

The resolver tries sources in this order:

1. Last known working source, if still valid.
2. Local TVHeadend, if enabled and preferred.
3. User-configured direct source.
4. User M3U source.
5. Local TVHeadend, if available but not preferred.
6. Bundled verified legal direct source.
7. Official web-page info-only fallback.
8. Disabled or unavailable source.

Bundled Israeli channels are intentionally conservative. If a channel has no independently verified legal direct source, it appears as unavailable and explains how to add a user source or TVHeadend mapping.

## User Sources

On first run the addon creates:

`userdata/addon_data/plugin.video.israeli.live.tv.stable/user_sources.json`

Example:

```json
{
  "channels": {
    "kan11": [
      {
        "id": "kan11_user_hls_1",
        "type": "DIRECT_HLS",
        "priority": 10,
        "enabled": true,
        "url": "https://example.com/user-provided.m3u8",
        "headers": {},
        "mime_type": "application/vnd.apple.mpegurl",
        "requires_inputstream_adaptive": false,
        "notes": "User-provided legal source"
      }
    ]
  }
}
```

Only add sources you are legally allowed to use.

## TVHeadend

TVHeadend is optional. Enable it in addon settings, then edit:

`userdata/addon_data/plugin.video.israeli.live.tv.stable/tvheadend_mapping.json`

Example:

```json
{
  "channels": {
    "kan11": {
      "enabled": true,
      "url": "http://192.168.1.10:9981/stream/channelid/123"
    }
  }
}
```

If `Prefer TVHeadend` is enabled, mapped TVHeadend sources are tried before user direct sources.

## M3U

Use Diagnostics > Regenerate M3U. The addon also exposes the playlist through a local-only URL for IPTV Simple Client.

The M3U excludes disabled sources, info-only pages, missing URLs, and unavailable placeholders.

## Daily Link Maintenance

This repo includes a daily GitHub Actions health check and a Codex maintenance automation plan. The checker tests bundled HLS/DASH links, promotes working fallbacks when a primary breaks, and searches for replacement candidates whenever any source breaks so the addon does not slowly run out of links.

See [MAINTENANCE.md](MAINTENANCE.md) for the rules and commands.

## Kodi TV Menu

Use `Setup Kodi TV` from the addon main menu. The addon will generate the M3U playlist, serve it at a local-only URL, try to configure PVR IPTV Simple Client with that URL, try to enable Kodi's PVR manager, and show manual instructions if Kodi blocks automatic setup.

After setup, open Kodi `TV -> Channels`.

If automatic setup fails, manually configure PVR IPTV Simple Client with the local playlist URL shown in Diagnostics. The generated M3U file path is still shown as a fallback/debug detail.

## Diagnostics

Diagnostics shows:

- Kodi, Python, platform, and addon version.
- Addon userdata path.
- User source and TVHeadend mapping paths.
- Local playlist URL and local playlist server status.
- inputstream.adaptive and IPTV Simple detection.
- Cache status.
- Last known good source and failures.
- Loaded channel and user source counts.
- Config validation errors.

## Development

Run pure Python tests outside Kodi:

```bash
python3 -m unittest discover -s tests
```

The development sample channel uses a public test HLS stream and is not an Israeli broadcaster.
