# Israeli Live TV Stable

Israeli Live TV Stable is a lightweight Kodi video addon for live TV only.

The goal is boring stability: open the addon, browse live channels, play a configured legal source, and get a clear explanation when playback is unavailable.

## What It Does

- Shows a fast Live Channels list.
- Includes bundled high-resolution local icons for every channel.
- Loads bundled channel metadata from local JSON.
- Supports user-provided legal direct HLS/DASH sources.
- Supports optional user-owned local TVHeadend mappings.
- Resolves sources with fallback and last-known-good cache.
- Plays through Kodi resolved URL APIs.
- Generates a simple M3U file containing only playable configured/legal sources.
- Can set up Kodi's native TV menu through PVR IPTV Simple Client.
- Includes an in-addon `Installation Steps` screen for first-time setup help.
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

### Keshet 12 Dynamic Playback

Keshet 12 uses an isolated dynamic public entitlement request immediately before addon playback. The resolver sends one of several reviewed relative Channel 12 paths to Mako's public/free web-player entitlement endpoint using ordinary browser headers. It accepts only a successful free response, builds a temporary `mako-streaming.akamaized.net` manifest URL, validates the HLS manifest, and passes it directly to Kodi.

No login, paid access, DRM bypass, device impersonation, private secret, or hard-coded ticket is used. Temporary tickets and tokenized manifest URLs are never written to `channels.json`, M3U files, logs, diagnostics, cache, or health reports. If the public flow changes, the resolver tries another reviewed path, then configured legal fallbacks, user sources, and TVHeadend. A total failure affects Channel 12 only.

Because tickets are short-lived and intentionally not serialized, the generated M3U uses a stable `plugin://` Channel 12 entry instead of a tokenized stream URL. IPTV Simple invokes the addon when Channel 12 is selected, allowing the addon to request a fresh ticket at playback time without storing it in the playlist.

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

Use Diagnostics > Regenerate M3U. `Setup / Repair Kodi TV` configures IPTV Simple Client automatically, so you should not need to browse for this hidden file yourself.

The M3U excludes disabled sources, info-only pages, missing URLs, and unavailable placeholders.

## Daily Link Maintenance

This repo includes a daily GitHub Actions health check and a Codex maintenance automation plan. The checker tests bundled HLS/DASH links, promotes working fallbacks when a primary breaks, tests reviewed replacement candidates whenever any source breaks, and scans configured public channel directories for watched new-channel targets such as Channel 16. Keshet 12 is checked through its public entitlement flow rather than by treating a static tokenless manifest as the final source.

See [MAINTENANCE.md](MAINTENANCE.md) for the rules and commands.

## Kodi TV Menu

For first-time setup, open `Installation Steps` from the addon main menu. It shows the full install flow inside Kodi, including ZIP install, Kodi TV repair, restart guidance, and fallback checks.

Use `Setup / Repair Kodi TV` from the addon main menu. The addon will generate the M3U playlist, verify it has channel entries, configure PVR IPTV Simple Client with the generated local file, force-sync IPTV Simple instance settings, and request a PVR reload.

After setup, open Kodi `TV -> Channels`.

If automatic setup fails, run `Setup / Repair Kodi TV` again after restarting Kodi. Diagnostics shows the generated file path, playlist entry count, instance settings path, backup path, and last repair result.

## Diagnostics

Diagnostics shows:

- Kodi, Python, platform, and addon version.
- Addon userdata path.
- User source and TVHeadend mapping paths.
- IPTV Simple setup mode, instance settings path, backup path, and generated M3U entry count.
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
