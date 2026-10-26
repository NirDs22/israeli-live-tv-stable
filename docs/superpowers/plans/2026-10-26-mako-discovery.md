# Mako Path Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the missing `--discover-mako-paths` maintenance workflow with safe official-page extraction and complete HLS validation.

**Architecture:** Keep entitlement and HLS media validation in `resources/lib/channels/keshet12.py`; keep page discovery, CLI wiring, and reporting in `tools/check_channels.py`. Unknown verified paths are reported for reviewed follow-up rather than automatically persisted.

**Tech Stack:** Python standard library, `unittest`, existing health-report dataclasses.

**Spec:** `docs/superpowers/specs/2026-10-26-mako-discovery-design.md`

## Global Constraints

- Never persist or log a tokenized URL.
- Only inspect official Mako/+12 HTTPS pages and the official Mako streaming host.
- Validate a master/media playlist and one complete media segment.

## Review Focus

- Tokenized URLs must be rejected before reporting.
- Escaped JSON URLs must normalize correctly.
- Relative child playlist URLs must retain the ephemeral entitlement query in memory only.
- A source-page failure must appear in the report without crashing the full health run.
- The flag must remain optional and preserve existing behavior when absent.

---

### Task 1: Complete entitlement HLS validation

**Files:**
- Modify: `resources/lib/channels/keshet12.py`
- Test: `tests/test_keshet12.py`

**Interfaces:**
- Produces: `check_public_entitlement_media_path(relative_path, timeout, http_open=None) -> tuple[bool, str]`

- [x] Write a failing test covering ticket, master playlist, media playlist, and complete segment reads without exposing the ticket.
- [x] Run the focused test and confirm the missing interface fails.
- [x] Implement the minimal validator and safe child-URL resolution.
- [x] Run the focused test and the Keshet 12 test module.

### Task 2: Official Mako discovery flag and report

**Files:**
- Modify: `tools/check_channels.py`
- Test: `tests/test_channel_health_tool.py`
- Modify: `MAINTENANCE.md`

**Interfaces:**
- Consumes: `check_public_entitlement_media_path(...)`
- Produces: `discover_mako_paths(timeout, http_open=...) -> list[MakoPathFinding]`

- [x] Write failing tests for CLI parsing, safe extraction, token rejection, validation, and report output.
- [x] Run focused tests and confirm failures are caused by the missing feature.
- [x] Implement official-page discovery, validation, CLI wiring, and JSON/Markdown reporting.
- [x] Document the command and safety boundary.
- [ ] Run focused tests, full tests, the exact live checker command, and the catalog validator.
- [ ] Commit and push PR #7.

### Task 3: Integrate and verify publication

**Files:** No source changes expected.

- [ ] Review the complete PR diffs and verification evidence.
- [ ] Merge PR #6, then refresh and merge PR #7 with the user's authorization.
- [ ] Verify the exact public raw `channels.json` used by Kodi contains Channel 16 and its remote logo.
- [ ] Verify the public main branch contains the Mako discovery flag and current source priorities.
