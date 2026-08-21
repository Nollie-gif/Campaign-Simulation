# Campaign-Simulation — Engine Changelog

Append-only engineering history: why something changed, what it touched,
compatibility/recovery notes, and verification evidence. Not runtime
authority — current behavior is defined by the code, tests, and
`README.md`. Record engineering/workflow changes only; gameplay-facing
wording belongs in `CHANGELOG.md`.

---

## 2026-08-21 — Change ledger + public-safety CI gate

**Category:** Repository continuity / CI hardening
**Compatibility:** Additive only; no runtime/API behavior changed.

### Why

A prior audit found the repository's public-safety policy
(`artifacts/README.md`) and Protected Main workflow
(`INSTALLATION_GUIDE.md`) were both documentation-only — a future change
could violate either and nothing would catch it before merge. Separately,
the repository had no durable record of *why* an engineering decision was
made, only the Git log, which doesn't distinguish a meaningful architectural
change from routine maintenance.

### Change

- Added `AGENT_HANDOFF.md` as the cold-start/authority/routing entrypoint,
  `CHANGELOG.md` for concise human-facing history, and this file for
  engineering rationale — mirroring the pattern already used successfully
  in Mission10-Simulation-Sequel, adapted to this repository's own identity
  (no campaign-state concept; routing table reflects this repo's actual
  file layout).
- Added `tools/validate_change_ledger.py`, run in CI: if a pull request's
  diff (against `origin/main`) touches an engineering-sensitive path
  (`src/campaign_simulation/**`, `schemas/**`, `.github/workflows/**`,
  `tools/**`) it must also touch `CHANGELOG.md` and `ENGINE_CHANGELOG.md`,
  or the branch's commits must carry a `Ledger-Exempt:` trailer naming that
  file and a reason. A separate, narrower rule requires `AGENT_HANDOFF.md`
  itself to be touched (or exempted) when `.github/copilot-instructions.md`
  or `INSTALLATION_GUIDE.md` changes, since those define the cold-start/
  authority behavior the handoff file routes to.
- Added `tools/public_safety_scan.py` (new `public-safety` CI job): flags
  secret-shaped strings, non-noreply commit author/committer emails on the
  branch, and — for artifact DOCX files — reviewer comments, tracked
  changes, embedded media, or an unreviewed `docProps` creator value.
- Added `.github/workflows/secret-scan.yml`, a scheduled full-history
  gitleaks scan, since PR-diff scanning alone cannot catch what is already
  reachable in Git history.

### Compatibility / recovery

- No existing test, template, or public API changed.
- The ledger check only *requires a touch*, not particular prose — it
  cannot force a specific quality bar, by design (see `AGENT_HANDOFF.md`,
  "Do not auto-generate meaningless changelog prose").
- If the check produces a false positive on a genuinely trivial change, the
  `Ledger-Exempt:` trailer is the documented escape hatch; it is visible in
  Git history, not a silent bypass.

### Verification

- `python -m unittest discover -s tests -v` — unaffected, all existing
  tests still pass.
- `tools/validate_change_ledger.py` — adversarially tested against an
  injected sensitive-path change with no ledger update (fails as expected),
  the same change with a `Ledger-Exempt:` trailer (passes), and a clean
  change with a proper ledger update (passes). See PR description for the
  exact commands run.
