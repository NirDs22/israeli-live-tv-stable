# Channel 12 Remote Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow verified official Channel 12 Mako paths to update through remote `channels.json` while keeping entitlement tokens ephemeral.

**Architecture:** Parse a narrowly scoped `mako_relative_path` field from source records, validate candidate metadata inside the Channel 12 resolver, and prepend accepted catalog paths to bundled defaults. Release version `0.1.17` carries the one-time resolver capability.

**Tech Stack:** Python 3 standard library, JSON catalog, `unittest`, Kodi addon XML.

**Spec:** `docs/superpowers/specs/2026-11-16-channel12-remote-path-design.md`

## Global Constraints

- Never store or publish temporary tokens, cookies, private endpoints, or guessed URLs.
- Accept only verified relative Mako paths with official HTTPS evidence and `manifest_and_media_segment_ok`.
- Preserve bundled and user/local fallback behavior.

## Review Focus

- Absolute or protocol-relative catalog paths must be ignored.
- Sensitive query keys must be ignored case-insensitively.
- Missing verification metadata must make a catalog path ineligible.
- Duplicate catalog and bundled paths must be attempted only once.
- Catalogs without the new field must retain existing behavior.

---

### Task 1: Parse catalog path metadata

**Files:**
- Modify: `resources/lib/models.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Produces: optional `Source.mako_relative_path`, `source_type`, `discovered_at`, and `validation_result` strings.

- [ ] Add a failing registry test asserting that all four metadata fields survive JSON parsing.
- [ ] Run `python3 -m unittest tests.test_registry` and confirm the new assertion fails.
- [ ] Add the optional fields to `Source` and `source_from_dict`.
- [ ] Re-run the registry tests and confirm they pass.

### Task 2: Resolve safe remote paths first

**Files:**
- Modify: `resources/lib/channels/keshet12.py`
- Test: `tests/test_keshet12.py`

**Interfaces:**
- Consumes: parsed `Source.mako_relative_path` and its evidence metadata.
- Produces: `reviewed_catalog_paths(channel: Channel) -> tuple[tuple[str, str], ...]` and a de-duplicated dynamic resolution plan.

- [ ] Add failing tests for catalog precedence, invalid absolute/tokenized path rejection, duplicate removal, and old-catalog fallback.
- [ ] Run the focused tests and confirm they fail for the expected missing behavior.
- [ ] Implement strict catalog path validation and compose catalog paths before `KESHET12_RELATIVE_PATHS`.
- [ ] Re-run `tests.test_keshet12` and confirm all cases pass.

### Task 3: Publish current path metadata and release version

**Files:**
- Modify: `resources/data/channels.json`
- Modify: `addon.xml`
- Test: `tests/test_release_metadata.py`

**Interfaces:**
- Consumes: `mako_relative_path` catalog contract.
- Produces: remotely fetchable current official path metadata and addon version `0.1.17`.

- [ ] Add the verified current relative path and complete evidence metadata to the Keshet 12 official source.
- [ ] Confirm the release-version test fails on `0.1.16`, then bump `addon.xml` to `0.1.17`.
- [ ] Run the full unit suite, catalog validator, exact health checker, and inspect the Channel 12 report.
- [ ] Package a clean addon ZIP matching the prior release structure and verify its contents.
