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

Use Diagnostics > Regenerate M3U. The generated file path appears in Diagnostics.

The M3U excludes disabled sources, info-only pages, missing URLs, and unavailable placeholders.

## Diagnostics

Diagnostics shows:

- Kodi, Python, platform, and addon version.
- Addon userdata path.
- User source and TVHeadend mapping paths.
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
