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

## 2026-08-21 — Change-ledger checker hardening (PR #21 pre-merge review)

**Why:** PR #21 (Flight Control Extraction, entry below) was CI-green but
blocked from merge by the branch ruleset's `required_review_thread_resolution`
rule: an automated reviewer (`chatgpt-codex-connector`) had left 5 unresolved
P2 threads on `tools/validate_change_ledger.py` and `scripts/preflight_commit.py`.
Per explicit instruction, these were investigated and judged on their merits
rather than dismissed to unblock the merge, and `--admin` was not used.

**Findings and disposition:**
1. **Fixed.** `changed_paths()` compared a union of "paths touched in
   committed history" and "paths touched in the staged diff" — an
   already-committed ledger update could paper over a later staged revert of
   that same update alongside a new, unrelated sensitive change. Replaced
   with a diff of the merge-base against the *prospective* tree
   (`git write-tree`, no commit created), which correctly nets out reverts.
   Identical behavior in CI (nothing is ever staged beyond HEAD there, so the
   prospective tree equals HEAD's tree).
2. **Fixed.** `check_committed_ledger_script_is_sane()` read
   `HEAD:tools/validate_change_ledger.py` — a self-weakening of this file
   that was staged but not yet committed (while the working tree happened to
   show safe content) was invisible until after it actually landed. Now
   reads the index (`git show :path`), which is exactly what `git commit`
   (without `-a`) is about to commit. Identical to `HEAD:path` in CI, where
   the index always equals HEAD.
3. **Fixed (usability, not a security gap).** The `Ledger-Exempt:` trailer
   is read from committed commit messages, but preflight runs *before*
   `git commit` — a genuine first-time exemption could never produce
   COMMIT-READY through the primary local path, since the commit carrying
   the trailer doesn't exist yet. Added `scripts/preflight_commit.py
   --pending-exempt "FILE REASON"`, which sets
   `CAMPAIGN_SIMULATION_PENDING_LEDGER_EXEMPT` for that local run only. CI
   never sets this variable and still requires the real committed trailer
   regardless of what local preflight predicted.
4. **Documented, not changed.** Two findings (self-referential trust: a
   locally-modified `preflight_commit.py`/`validate_change_ledger.py` run
   directly, not from a trusted copy, could lie to itself) describe a true
   and irreducible property of any local-only gate — there is no local root
   of trust that can stop someone from lying to their own working tree. This
   was already the documented design (the real, non-bypassable boundary is
   CI's trusted-copy-from-`origin/main` execution plus the
   non-exemptable self-check above). Strengthened `preflight_commit.py`'s
   module docstring to state this explicitly rather than leaving it implicit.

**Verification:** all three fixes were adversarially reproduced by hand
before being accepted as fixed (staged a revert-while-sensitive-change
scenario and confirmed the old union logic would have wrongly passed it
while the new logic correctly fails it; staged a self-weakening with disk
reverted to safe content and confirmed the old `HEAD`-read would have missed
it while the new index-read catches it; confirmed the pending-exempt
variable is absent by default and never confused with a real trailer). All
four scenarios are now permanent regression coverage in the new
`tests/test_validate_change_ledger.py` (uses a disposable temp-directory git
repo per test via `unittest.mock.patch.object(vcl, "ROOT", ...)`, not the
real repository). Full suite: 135 tests, `OK (skipped=4)`.

**Compatibility:** no change to what CI enforces or to any already-recorded
`Ledger-Exempt:` trailer's meaning.

---

## 2026-08-21 — Flight Control Extraction

**Category:** Repository continuity / local engineering guardrail
**Compatibility:** Additive only; no runtime/API behavior changed.

### Why

The Protected Main Rule (`INSTALLATION_GUIDE.md`) and the branch ruleset
enforce the *server-side* half of the guarded engineering path (PR
required, CI required, no bypass). Nothing enforced the *local* half — a
fresh branch, exact staged scope, passing checks — before a commit was
even made; that depended entirely on an agent remembering to do it, the
same class of gap the change-ledger mechanism closed for durable records.
Mission10-Simulation-Sequel and The-Test had already built, used in
production, and adversarially hardened exactly this mechanism (Flight
Control); porting it here closes the same gap without re-inventing it.

### Change

- Added `scripts/preflight_commit.py`, `scripts/install_preflight_hook.py`,
  `.githooks/pre-commit` (content-pinned via SHA-256, LF-pinned via
  `.gitattributes`), and the full adversarial test suite
  (`tests/test_preflight_commit.py`, `tests/test_install_preflight_hook.py`
  — 74 tests total, all passing on this platform).
- **Not a blind copy** — three deliberate adaptations, not cosmetic
  renames:
  - `ALLOWED_BRANCH_PREFIX` ("agent/" only) generalized to
    `ALLOWED_BRANCH_PREFIXES`, matching this repository's own
    already-documented `INSTALLATION_GUIDE.md` convention
    (`feature/`, `fix/`, `hardening/`, `test/`, `docs/`, `agent/`) instead
    of forcing every future branch onto a foreign single-prefix rule.
  - `PROTECTED_BRANCHES` narrowed to `{main, master}` — no
    `runtime-published`/`runtime-save-staging`-style branches exist here.
  - `run_required_checks()` restructured: the three pure-file-content
    checks (unit tests, blank-template validation, artifact-manifest
    validation) run inside the isolated, `.git`-less materialized
    snapshot exactly as Mission10's version does; `tools/validate_change_ledger.py`
    runs separately against the real repository root, because it
    inherently needs live Git history (`merge-base`/`diff`/`log` against
    `origin/main`) that a git-less snapshot cannot provide — a
    distinction Mission10's single-validator design never had to make.
- **A real bug found only by actually running the ported checks against
  real content, not by inspection:** the materialized snapshot had no
  `PYTHONPATH`, so a child process's own subprocess (e.g.
  `test_concurrent_identifiers_integration.py`, which shells out to a
  fresh `python -c "from campaign_simulation..."`) resolved
  `campaign_simulation` via whatever editable install happened to exist
  in the outer environment instead of the snapshot's own materialized
  `src/` — silently validating the live working tree rather than the
  actually-staged content, which defeats the entire point of
  materializing a snapshot. Fixed by prepending `{snapshot}/src` to the
  child environment's `PYTHONPATH`. Mission10 has no equivalent
  subprocess-spawning test, so this gap did not exist to find there.
- Forbidden-token self-purity test
  (`test_guardrail_has_no_product_mutation_commands`) adapted to this
  repository's actual mutation surface (`commit_checkpoint(`,
  `commit_manifest(`, `validate_gated_checkpoint(`) instead of Mission10's
  Supabase/WDR-specific function names, which do not exist here.
- Extended `tools/validate_change_ledger.py`'s domains: `scripts/*` added
  to the `CHANGELOG.md`/`ENGINE_CHANGELOG.md` sensitive-path set (this
  repository's first real use of a `scripts/` directory), and
  `scripts/preflight_commit.py`, `scripts/install_preflight_hook.py`,
  `.githooks/*` added to the `AGENT_HANDOFF.md` domain — matching the
  narrower, more precise pattern already used for The-Test and Mission10
  after the Council review.
- Resolved the classification ambiguity between Flight Control (this
  repository's own engineering) and the pre-existing Experiment Safety
  installation (`docs/safety-installation/`, which protects a *DM's own,
  separate* campaign runtime): added an explicit "which repository does
  this change target" cross-reference to `AGENT_HANDOFF.md`,
  `docs/safety-installation/README.md`, and `LOTS_SAFE_BUILD_PROMPT.md`,
  without weakening either system or merging their scopes.

### Compatibility / recovery

- No existing test, template, schema, or public API changed.
- Flight Control is local-only and additive: a clone without the hook
  installed still works exactly as before (CI remains the independent
  backstop regardless of local guardrail state).

### Verification

- All 74 ported tests pass on this platform (Windows).
- Live, non-mocked adversarial tests in an isolated worktree: a
  branch-name outside `ALLOWED_BRANCH_PREFIXES` is rejected
  (`NON-FEATURE-BRANCH`); staged content tampered with after a successful
  `COMMIT-READY` is rejected at the real `git commit` boundary
  (`PREFLIGHT-MARKER-MISMATCH`) by the actually-installed hook, not a
  mock. Direct-commit-on-`main` and stale-branch rejection are covered by
  the ported unit/integration suite (`test_protected_branch_is_rejected`,
  `test_stale_branch_fails_closed`,
  `test_git_replace_ref_does_not_fake_freshness_against_origin_main` — the
  last against a real, disposable Git repository, not a mock) rather than
  re-proven live here, since `main` does not carry Flight Control until
  this change merges into it; full live re-verification against the
  merged, real `main` is planned as part of fresh-clone verification.

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
