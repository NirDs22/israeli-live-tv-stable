# Mako Path Discovery Design

## Intent

Make the scheduled maintenance command executable and useful: `--discover-mako-paths` must inspect current official Mako/+12 pages, reject unsafe URLs, validate legal public HLS through the existing ephemeral entitlement flow, and record findings without persisting tickets.

## Constraints

- Official Mako/+12 pages only; no app reverse engineering or bypasses.
- Accept only HTTPS `mako-streaming.akamaized.net` HLS paths with stable non-secret query parameters.
- Validate master/media playlists and one complete media segment.
- Never print or persist entitlement tickets.
- Discovery reports unknown verified paths for review; it does not silently rewrite Python source.

## Approaches

1. Accept the flag as a no-op. Rejected because it hides incomplete maintenance.
2. Scrape broad web search results. Rejected because provenance and safety are weaker.
3. Inspect a small official-page allowlist and validate extracted paths through the existing public entitlement resolver. Selected because it is auditable, legal, and fits the current architecture.

## Output

The JSON and Markdown health reports gain a dedicated Mako path section with the official evidence page, redacted relative path, validation status, and whether the path is already reviewed.
