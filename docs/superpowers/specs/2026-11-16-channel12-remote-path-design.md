# Channel 12 Remote Path Design

## Intent

Make Channel 12 recover from official Mako path changes through the existing online `channels.json` update mechanism. The installed addon must still create temporary entitlement tickets at playback time and must never store or publish those tickets.

## Goals

- Let a verified official Mako relative path travel in `channels.json` and take precedence over bundled defaults.
- Reject catalog paths that are absolute, tokenized, unverified, or not backed by an official HTTPS evidence page.
- Keep bundled reviewed paths as backward-compatible fallbacks.
- Publish addon version `0.1.17` so installed copies gain this capability once; later reviewed path changes can arrive through the remote catalog.

## Non-goals and anti-goals

- Do not publish temporary manifest URLs, cookies, headers, device identifiers, or DRM workarounds.
- Do not make arbitrary catalog URLs executable as entitlement paths.
- Do not remove the existing static legal fallback or local/user fallbacks.

## Constraints

- Catalog path metadata must include an ID, relative path, official evidence URL, verification date, source type, and `manifest_and_media_segment_ok` validation result.
- A catalog path must start with one `/`, contain no host or fragment, and contain no sensitive query keys such as token, signature, ticket, auth, expiry, or device identifiers.
- The official path currently verified is `/stream/hls/live/20000821/k12rh-dvr/index.m3u8?b-in-range=0-800` from the public Mako/+12 live page.

## Approaches

1. Hard-code the new path only. Smallest patch, but every future upstream path change requires another addon release.
2. Store a direct final HLS URL in `channels.json`. Rejected because Mako returns temporary entitlement URLs and publishing them would be unstable and unsafe.
3. Store only a reviewed relative Mako path in `channels.json`, validate it locally, then request the temporary entitlement at playback. Selected because it makes future safe updates remote while preserving the existing security boundary.

## Implementation shape

`Source` gains optional catalog metadata for a Mako relative path. The Keshet 12 resolver builds a de-duplicated path plan from valid enabled catalog sources followed by bundled defaults. Invalid catalog entries are ignored rather than executed. Tests pin catalog precedence, unsafe-path rejection, fallback compatibility, and release version metadata.
