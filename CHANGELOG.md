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

## 2026-09-02

- **(engineering)** A second exact-head-bound review found 6 more gaps,
  each reproduced before fixing — most materially, a tracked file whose
  name contains non-ASCII characters was silently never scanned at all
  (Git quotes such names, and the resulting path didn't resolve). Also:
  the scan job could be weakened by the very PR it was grading; unquoted
  `KEY=value` secrets were missed; DOCX hyperlink targets and PDF XMP
  author metadata were never inspected; and GitHub's legacy no-reply
  address format was wrongly rejected. See `ENGINE_CHANGELOG.md`.
- **(engineering)** A fresh, exact-head-bound independent review of PR #17
  found 5 more real gaps, each reproduced before fixing: unpinned actions
  in the scheduled secret-scan workflow; a direct push to `main` could
  bypass the new commit-identity check entirely; a PDF's `/Author` could
  be hex-encoded instead of a plain string and pass silently; an
  email/secret split across adjacent Word runs by formatting wasn't
  joined before scanning; and an ordinary Word field (e.g. a page-number
  field) could be misidentified as a tracked change. See
  `ENGINE_CHANGELOG.md`.
- **(engineering)** Fixed a public-safety scanner self-scan false positive
  caught by real CI on PR #17 after the fix below was pushed: removing the
  old suffix allowlist meant the scanner started flagging its own
  regression test's deliberate secret-shaped/email-shaped fixtures. See
  `ENGINE_CHANGELOG.md`.
- **(engineering)** PR #17's `tools/public_safety_scan.py` was brought
  forward onto current `main` (merge, not rebase — the branch's 3 existing
  commits and their review threads were preserved) and its 5 confirmed
  review defects were fixed as two coherent classes: coverage gaps (a
  hard-coded text-suffix allowlist skipped `.env`/`.sh`/extensionless
  files; PDF artifacts were never inspected; DOCX body text was never
  scanned for secrets/emails) and DOCX parsing fidelity (core-property
  regexes missed attributed XML elements; tracked-changes detection only
  looked at `word/document.xml`, missing headers/footers/footnotes). A
  6th alleged defect (GitHub's synthetic PR merge-ref committer) was
  investigated against real GitHub PR data and found already fixed by an
  earlier commit already in the PR — no change made for it. See
  `ENGINE_CHANGELOG.md` for the full findings disposition and evidence.

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
- **(engineering)** Added Flight Control, a local commit guardrail
  (`scripts/preflight_commit.py`, `scripts/install_preflight_hook.py`,
  `.githooks/pre-commit`), extracted and adapted from the mechanism proven
  in Mission10-Simulation-Sequel and The-Test. Run
  `python scripts/install_preflight_hook.py` once per clone, then
  `python scripts/preflight_commit.py` before each commit — see
  `AGENT_HANDOFF.md` for the full guardrail and how it relates to the
  separate, DM-facing Experiment Safety installation.
- **(engineering)** Hardened `tools/validate_change_ledger.py` against 4
  real gaps found by two rounds of automated pre-merge review of the
  Flight Control PR: a revert-vs-committed-history edge case, a
  staged-vs-HEAD self-check blind spot, an exemption-trailer
  chicken-and-egg deadlock in local preflight, and — found in the second
  round, after the first fix for that deadlock was pushed — a real CI
  bypass that first fix had introduced (an environment variable read by
  the same file CI trusts). All four are fixed and merged; only the
  fourth ever affected CI, and never reached `main`. See
  `ENGINE_CHANGELOG.md`.
