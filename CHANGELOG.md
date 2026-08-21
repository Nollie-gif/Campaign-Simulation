# Changelog

Concise, human-facing record of meaningful changes to Campaign-Simulation.
Deeper engineering rationale for entries marked **(engineering)** lives in
[`ENGINE_CHANGELOG.md`](ENGINE_CHANGELOG.md). This file does not replace the
Git history; it exists so a human or agent can scan what changed without
reading every commit.

**Historical scope:** enforced and maintained from 2026-08-21 forward.
Earlier repository history was not reconstructed into retroactive entries
here — treat anything before this date as "see Git history," not "see
CHANGELOG."

## 2026-08-21

- **(engineering)** Added `AGENT_HANDOFF.md`, this file, and
  `ENGINE_CHANGELOG.md` as the repository's continuity layer, with
  `tools/validate_change_ledger.py` enforcing in CI that a change to an
  engineering-sensitive path also updates the matching ledger (or carries an
  explicit `Ledger-Exempt:` trailer).
- **(engineering)** `tools/public_safety_scan.py` was written to catch
  secrets, non-noreply commit identities, and leftover DOCX author metadata
  before merge; it is not active on `main` yet — see PR #17, which is
  intentionally left open/unmerged as a separate, unrelated finding.
- **(engineering)** Completed the artifact SHA-256 manifest for artifacts
  06–09 and added `tools/validate_artifact_manifest.py` to keep it complete
  going forward.
- **(engineering)** Pinned `actions/checkout` and `actions/setup-python` in
  CI to commit SHAs instead of mutable version tags.
- Removed a real personal email address that had been present throughout
  the public Git history since the repository's early commits.
