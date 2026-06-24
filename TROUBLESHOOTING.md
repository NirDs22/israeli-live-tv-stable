# Troubleshooting

## Channel Unavailable

The channel has no configured playable source. Add a legal source to `user_sources.json` or configure a local TVHeadend mapping.

## Channel 12 / Keshet 12

Channel 12 has an isolated dynamic public entitlement resolver. It requests a short-lived free playback ticket immediately before playback and never stores that ticket. Open `Diagnostics -> Channel 12 Diagnostics` to test only Channel 12, clear only its cache, or see the `channel12_override.json` path.

If you add an override, use only a legal user-provided source. Bad override JSON is ignored and will not affect other channels.

The dynamic flow depends on Mako's public web-player endpoint and reviewed relative stream paths, so Mako can change or reject it without notice. The addon tries alternate reviewed paths and configured fallbacks. Errors, diagnostics, cache, generated M3U files, and health reports do not contain temporary tickets.

## inputstream.adaptive Missing

Some DASH/HLS sources may require `inputstream.adaptive`. Install and enable it from Kodi's add-on repository. Diagnostics shows whether it is detected.

## User Source Invalid

Bad JSON is ignored so the addon can keep running. Open Diagnostics and check `Config validation errors`.

Common mistakes:

- `channels` is missing.
- A channel entry is not a list.
- A source is missing `id` or `type`.
- `headers` is not an object.

## TVHeadend Not Configured

If TVHeadend is preferred but no mapping exists, playback will explain:

`Local TVHeadend is not configured. Add a mapping in tvheadend_mapping.json or disable TVHeadend preference.`

Add a valid mapping or disable the TVHeadend preference.

## M3U Empty

The M3U includes only playable configured/legal sources. Info-only pages, disabled sources, and missing URLs are excluded.

Add a legal user source or TVHeadend mapping, then regenerate M3U from Diagnostics.

## Kodi TV Menu Is Empty

Run `Setup / Repair Kodi TV` again from the addon. It should repair IPTV Simple automatically without you browsing for the hidden M3U file.

Also check:

- PVR IPTV Simple Client is installed and enabled.
- Kodi PVR is enabled.
- The generated M3U is not empty.
- Restart Kodi after changing IPTV Simple settings.

## IPTV Simple Not Installed

Install it from Kodi:

`Add-ons -> My add-ons -> PVR clients -> PVR IPTV Simple Client`

Then run `Setup / Repair Kodi TV` again.

## Kodi Freezes Or UI Is Slow

V1 does not perform network calls while opening the main menu or channel list. If Kodi is slow:

- Disable broken user sources.
- Lower timeout settings.
- Clear cache from Diagnostics.
- Check Kodi logs for platform-level playback problems.

## Logs

Kodi logs are platform dependent. On Android TV they are usually inside Kodi's app data directory. Enable Kodi debug logging and addon debug logging before reproducing the issue.
