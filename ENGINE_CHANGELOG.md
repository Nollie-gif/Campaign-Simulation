# Campaign-Simulation — Engine Changelog

Append-only engineering history: why something changed, what it touched,
compatibility/recovery notes, and verification evidence. Not runtime
authority — current behavior is defined by the code, tests, and
`README.md`. Record engineering/workflow changes only; gameplay-facing
wording belongs in `CHANGELOG.md`.

**Historical scope:** entries begin 2026-08-21. Earlier engineering history
was not reconstructed retroactively — the Git log is authoritative for
anything before that date.

---

## 2026-08-21 — Change-ledger self-defense hardening

**Category:** CI hardening / adversarial review follow-up
**Compatibility:** Additive only; no runtime behavior changed.

### Why

An adversarial review of the change-ledger mechanism (added earlier the
same day) found two real, demonstrated gaps rather than theoretical ones:

1. A pull request could edit `tools/validate_change_ledger.py` itself to
   neuter its own rule (e.g. emptying `LEDGER_DOMAINS`), and because CI
   ran the script *as committed on that branch*, the weakened copy graded
   its own diff as clean. Reproduced in an isolated worktree.
2. Renaming `src/campaign_simulation/` (a plausible, ordinary refactor)
   silently stopped the check from protecting anything under the new
   name — the pattern `src/campaign_simulation/*` matched zero files and
   the check reported "passed" on a real, undocumented code change.
   Reproduced in the same worktree.

A third, smaller issue: this file's sibling `CHANGELOG.md` entry for
`tools/public_safety_scan.py` claimed it was "run in CI" when the PR that
adds it (#17) is intentionally still open/unmerged — a durable record
asserting something not yet true.

### Change

- CI now overwrites the pull request's own copy of
  `tools/validate_change_ledger.py` with the copy committed on
  `origin/main` before executing it (workflow step "Use ledger checker
  from main"). A PR can still improve the checker — the change just isn't
  the one grading itself.
- **This alone was insufficient, found by re-testing rather than trusting
  the design.** The overwritten *executing* copy correctly requires
  CHANGELOG.md/ENGINE_CHANGELOG.md when `tools/*` changes — but a PR can
  legitimately *exempt* that requirement with a trailer, and the
  exemption mechanism has no idea it's exempting a change to the checker
  itself. The neutered file still merges; it becomes the trusted copy for
  every subsequent PR. Closing this needed a second, independent check —
  `check_committed_ledger_script_is_sane()` — that reads the PR's *own*
  committed version of `tools/validate_change_ledger.py` via `git show
  HEAD:...` (never the overwritten working copy, never executed — parsed
  with `ast` only) and independently counts `LEDGER_DOMAINS` entries
  against this trusted script's own `MINIMUM_DOMAIN_COUNT`. Not waivable
  by any trailer.
- Added `check_pattern_coverage()`: fails if any domain glob pattern
  currently matches zero tracked files, which is exactly the signature a
  silent rename/move leaves behind.
- Broadened `src/campaign_simulation/*` to `src/*` (in `fnmatch` semantics
  `*` already crosses `/`, so this survives a rename of the inner package
  directory; it does not survive `src/` itself being renamed or moved —
  no static pattern can, without becoming so broad it stops meaning
  anything).
- Corrected the `CHANGELOG.md` entry for `tools/public_safety_scan.py` to
  state its actual (not-yet-merged) status, and added an explicit
  "enforced from this date forward" boundary note to both `CHANGELOG.md`
  and this file.

### Compatibility / recovery

- No existing check's pass/fail outcome changes for any already-correct
  PR; only the demonstrated bypasses are closed.
- If `origin/main` doesn't yet have `tools/validate_change_ledger.py` (a
  bootstrap PR introducing it for the first time), the workflow step is a
  no-op and CI falls back to the PR's own copy — there is nothing trusted
  to fetch yet.
- This still cannot stop a determined, already-trusted committer from
  weakening `main`'s copy across two separately-merged PRs (raise
  `MINIMUM_DOMAIN_COUNT`'s effective floor in one PR to something trivial,
  then exploit it in the next). That boundary is branch protection and
  human review, not this script — and it was never going to be able to
  protect against its own maintainer.

### Verification

- The self-neutering attack was built and actually run against each
  successive defense, not assumed fixed: the trusted-copy-only fix was
  shown to still pass (documented above as the reason the second check
  exists); a first version of the AST-based check false-failed on *any*
  edit to `LEDGER_DOMAINS`, including legitimate ones, because it didn't
  recognize Python's annotated-assignment syntax (`ast.AnnAssign` vs
  `ast.Assign`) — caught by testing a deliberately legitimate 4-domain
  addition alongside the attacks, not by inspection. Final matrix, all in
  an isolated worktree: literal `LEDGER_DOMAINS = []` (fails, correct
  count reported), a `[] and [...]` expression trick (fails, reported as
  unparseable — accurately suspicious), and a genuine new domain addition
  (passes, no false positive).
- Rename attack re-tested: fails loudly via `check_pattern_coverage()`
  instead of silently passing.
- Full adversarial test matrix (sensitive change / exemption / trivial
  change / narrow-domain change) re-run and still behaves as before.

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
