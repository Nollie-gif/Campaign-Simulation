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

## 2026-09-02 — PR #17 recovery: forward-port + confirmed-defect fixes (Gate 10)

**Category:** CI hardening / public-safety scanner correctness
**Compatibility:** Additive/corrective only; no runtime/API behavior changed.

### Why

PR #17 (`tools/public_safety_scan.py` + `public-safety` CI job) had been
open since 2026-08-21, unmergeable (`CONFLICTING` against current `main`,
which had since gained SHA-pinned Actions and the change-ledger CI job),
with 6 unresolved `chatgpt-codex-connector` review threads. Per live Asana
Gate 10 (Campaign-Simulation — Control Room, GID 1217845405841717), the
goal was to finish this PR without rewriting history or merging an
incomplete security control, resolving findings as reproduced fact rather
than by blind single-example patching.

### Change

- Merged current `main` (`890f298`) into
  `hardening/public-safety-ci-gate` (merge commit, not rebase — preserves
  the branch's original 3 commits and every review thread's anchor SHA).
  The only real conflict was `.github/workflows/tests.yml`: resolved by
  keeping both the `public-safety` job (this branch) and the
  `change-ledger` job (`main`), and re-pinning `public-safety`'s
  `actions/checkout`/`actions/setup-python` to the same commit SHAs `main`
  already uses instead of the branch's original floating `@v4`/`@v5` tags.
- Fixed 5 of 6 open review findings in `tools/public_safety_scan.py`,
  each reproduced against a throwaway fixture repo before being treated
  as confirmed, grouped as two coherent classes:
  - **Coverage gaps** (findings: text-suffix allowlist skipped
    `.env`/shell/extensionless files; PDF artifacts under `artifacts/`
    were never opened; DOCX body text was sent only to the metadata
    check, never to the secret/email scan). Fixed by dropping the
    suffix allowlist (every non-artifact-binary tracked file now goes
    through the same text scan; a file that fails UTF-8 decoding is
    silently skipped, same as before) and adding `scan_pdf_metadata()`
    (checks `/Author` — the PDF spec's personal-identity field, unlike
    `/Creator`/`/Producer` which name the authoring *application* — plus
    the same secret/email scan against the PDF's raw bytes).
  - **DOCX parsing fidelity** (findings: `dc:creator`/`cp:lastModifiedBy`
    regexes used exact open/close tags and missed a valid attributed form
    like `<dc:creator xml:space="preserve">…`; tracked-changes detection
    only inspected `word/document.xml`, missing headers/footers/
    footnotes/endnotes). Fixed by parsing `docProps/core.xml` with
    `xml.etree.ElementTree` (namespace-aware, attribute-agnostic) instead
    of regex, and by running both the tracked-changes check and the
    secret/email body scan across every `word/(document|header*|footer*|
    footnotes|endnotes).xml` part, not just the main body.
- Added `tests/test_public_safety_scan.py`: one regression test per fixed
  finding (each fails against the pre-fix code, passes after), plus a
  clean-tree false-positive test and two `check_commit_identities()`
  tests (accept a `noreply@github.com` committer, reject a real address).
- **Investigated, not fixed:** the 6th finding claimed GitHub's synthetic
  `pull_request` merge-ref commit (`refs/pull/N/merge`) would have a
  committer email the scan's allowlist rejected. Verified against this
  PR's actual live merge ref, fetched directly from GitHub
  (`refs/pull/17/merge`, commit `74e8094`): committer is
  `GitHub <noreply@github.com>`, which `ALLOWED_EMAIL_PATTERN` already
  accepts — via a fix the PR's own second commit (`c57e653`) had already
  made, before this recovery work began. The review comment was anchored
  to the PR's first commit and was stale by the time of this recovery. No
  code change was made for this finding; a hypothesis that cannot be
  reproduced against the current code is reported as such, not patched.

### Verification

`python -m unittest discover -s tests -v` — 147 tests, `OK (skipped=4)`
(139 pre-existing + 8 new). `tools/validate_blank_templates.py`,
`tools/validate_artifact_manifest.py`, and `tools/public_safety_scan.py`
itself all pass clean (zero false positives) against the real merged
tree. Each of the 5 fixed findings was reproduced failing against the
pre-fix code and confirmed passing after, both via an ad hoc throwaway
fixture repo and via the corresponding committed regression test.

## 2026-09-02 — public-safety self-scan false positive (real CI, PR #17)

**Category:** CI correctness fix (public-safety scanner)
**Compatibility:** Additive/corrective only; no runtime/API behavior changed.

### Why

After pushing the Gate 10 recovery commit (`6f428e2`) and letting real GitHub
Actions CI run on PR #17 (not a local simulation), the `public-safety` job
failed on both `push` and `pull_request` triggers. This was independent of
the Finding #3 (synthetic merge-ref committer) investigation recorded above,
which was correctly *not* reproducible — this was a separate, new defect
introduced by this recovery's own Finding-1 fix.

### Change

Removing the old text-suffix allowlist (per the Finding-1 fix above) means
`tools/public_safety_scan.py` now scans every tracked non-artifact-binary
file, including its own new regression suite,
`tests/test_public_safety_scan.py`, which deliberately embeds
secret-shaped strings (`AKIA...`, `github_pat_...`) and non-noreply sample
emails as fixtures to prove detection works. The scanner correctly
mechanically flagged its own test fixtures as if they were leaked
material. Fixed by adding `SELF_TEST_FIXTURE_PATH` and skipping that exact
path in both `main()`'s dispatch loop and the test suite's own `_run_scan()`
harness, with a comment documenting why (not real secrets, not general
suppression).

### Verification

Reproduced directly from real CI logs on PR #17 (run `33654734706`, job
`public-safety`, head `6f428e2`, checked out at synthetic merge ref
`83a8655`): `tools/public_safety_scan.py` exited 1, flagging
`tests/test_public_safety_scan.py` for an AWS-key-shaped string, a
GitHub-token-shaped string, and 4 sample emails. After the fix,
`python tools/public_safety_scan.py` passes clean locally and
`python -m unittest discover -s tests` still reports `OK (skipped=4)`.

## 2026-09-02 — public-safety hardening round 2 (fresh exact-head Codex review, PR #17)

**Category:** CI hardening / public-safety scanner correctness
**Compatibility:** Additive/corrective only; no runtime/API behavior changed.

### Why

Per Gate 10, an independent Codex review was explicitly requested (`@codex
review` PR comment) bound to the exact pushed head `7983e5b`, rather than
relying on the two stale review threads from 2026-08-21. It returned 5 new
findings, all anchored with `original_commit_id == commit_id == 7983e5b`
(genuinely fresh, not GitHub's auto-remap of an old thread). Each was
reproduced against a throwaway fixture before being treated as confirmed,
per the same discipline used for the earlier Finding #3 investigation.

### Change

- **Supply-chain pin** (`.github/workflows/secret-scan.yml`): the
  scheduled/manual full-history gitleaks job used floating
  `actions/checkout@v4` and `gitleaks/gitleaks-action@v2` tags while every
  other workflow in the repo is SHA-pinned. Pinned both to the commit SHAs
  those tags currently resolve to (`actions/checkout` — the same SHA
  already used elsewhere; `gitleaks/gitleaks-action` —
  `ff98106e4c7b2bc287b24eaf42907196329070c7`, i.e. v2.3.9).
- **Push-to-main identity-check gap** (`check_commit_identities()`): on a
  `push` event, `actions/checkout` leaves `origin/main` pointing at the
  same commit as `HEAD` (the push already landed before CI ran), so
  `git merge-base HEAD origin/main` is `HEAD` itself and
  `git log HEAD..HEAD` is empty — a directly-pushed commit to `main` with a
  personal identity would never be checked. Reproduced with a bare-origin
  simulation before fixing. Fixed by reading an optional
  `PUBLIC_SAFETY_COMMIT_RANGE_BASE` env var (set only for `push` events in
  `tests.yml`, from `github.event.before`, with the all-zero "new branch"
  SHA treated as absent) as the diff base instead of the merge-base
  computation; `pull_request` and local/unset runs are unaffected and keep
  the existing merge-base logic.
- **PDF hex-string `/Author`**: the PDF spec allows a string to be written
  as a parenthesized literal or a hex string (commonly UTF-16BE with a
  `FEFF` BOM for Unicode); the scanner only matched the literal form, so a
  hex-encoded personal name in `/Author` passed silently. Added
  `PDF_METADATA_HEX_PATTERN` + `_pdf_decode_hex_string()` alongside the
  existing literal-form check.
  - **DOCX text split across adjacent runs / instrText false positive**:
  two related parsing-fidelity gaps in the same story-part loop. (a) The
  body/header/footer scan ran regexes against raw serialized XML, so an
  email or secret split across adjacent `<w:t>` runs by formatting (e.g.
  `alice@real-` / `company.com` in separate runs, which Word still
  displays as one continuous string) was never joined and so never
  matched. (b) Tracked-changes detection used a `"w:ins" in content`
  substring test, which also matches unrelated field codes like
  `<w:instrText>` (e.g. a plain PAGE field), flagging documents with no
  real tracked changes. Fixed both by parsing each story part with
  `ElementTree` once: real `ins`/`del` elements are matched by local tag
  name (not substring), and adjacent `<w:t>` element text is joined in
  document order and scanned as one string; a part that fails to parse as
  XML falls back to the old substring check rather than being silently
  skipped.
- Added 4 new regression tests (findings 7–10, continuing the existing
  numbering) to `tests/test_public_safety_scan.py`, one per confirmed
  finding above; each reproduces the pre-fix gap and confirms the fix.

### Verification

Each of the 4 code-level findings (identity-check gap, PDF hex author,
split-run text, instrText false positive) was reproduced failing against
an ad hoc throwaway fixture before the fix and confirmed passing after,
both in the ad hoc repro and in the corresponding committed regression
test. The 5th (unpinned secret-scan actions) was a static config fact,
verified by direct inspection, no repro needed. `python -m unittest
discover -s tests` — 151 tests, `OK (skipped=4)` (147 prior + 4 new).
`tools/public_safety_scan.py` passes clean against the real tree.

## 2026-09-02 — public-safety hardening round 3 (second exact-head review, PR #17)

**Category:** CI hardening / public-safety scanner correctness
**Compatibility:** Additive/corrective only; no runtime/API behavior changed.

### Why

A second independent Codex review, requested against exact head `1e18711`
after round 2's fixes went green in CI, returned 6 further findings (all
`original_commit_id == 1e18711`). Each was reproduced before being fixed.

### Change

- **Self-grading gate** (`.github/workflows/tests.yml`): the
  `public-safety` job ran the scanner *from the PR's own merge tree*, so a
  PR could weaken the scanner in the same commit that adds the material
  the gate exists to reject. Adopted the identical trusted-base idiom the
  `change-ledger` job already uses — restore `tools/public_safety_scan.py`
  from `origin/main` when it exists there. This is inert on this PR (the
  scanner is not on `main` yet) and becomes self-protecting the moment
  this PR merges.
- **Unquoted secret assignments**: the generic API-key pattern required
  quotes around the value, so the ordinary dotenv/shell form
  (`OPENAI_API_KEY=sk-proj-…`, `secret=…`) never matched. Quotes are now
  optional. Keyword list deliberately unchanged, to avoid widening
  false-positive surface beyond the confirmed finding.
- **DOCX relationship targets**: hyperlink targets live in relationship
  parts (`word/_rels/document.xml.rels`), which the story-part loop never
  read — a `mailto:` personal address or credential-bearing URL passed
  untouched. All `.rels` parts are now scanned.
- **PDF XMP authorship**: a PDF can record its author only in an XMP
  packet (`dc:creator`) with no Info-dictionary `/Author` at all; both
  existing patterns missed it and a personal name is not secret-shaped, so
  the file passed clean. Added XMP `dc:creator`/`rdf:li` extraction.
  Compressed XMP packets remain the same documented gap as compressed
  content streams.
- **Non-ASCII tracked filenames**: with Git's default `core.quotePath`,
  `git ls-files` renders such a name C-escaped and quoted
  (`"r\303\251sum\303\251.env"`); the resulting `Path` does not exist, so
  `main()` silently skipped the file and never scanned its contents.
  Reproduced with a real AWS-key-bearing file that scanned clean. Switched
  to `git ls-files -z` with NUL-delimited decoding. This is the most
  material of the six: it silently disabled scanning per-file, and this
  repository's artifact library does carry non-ASCII names.
- **Legacy GitHub noreply identities**: `ALLOWED_EMAIL_PATTERN` accepted
  only the modern numeric-id noreply form, so a contributor using the
  legitimate legacy bare-username noreply address would have every commit
  rejected. Both forms are now accepted.
- Added 5 new regression tests (findings 11–15) to
  `tests/test_public_safety_scan.py`.

### Verification

All 6 findings reproduced against throwaway fixtures before fixing and
confirmed fixed after (the filename finding visibly: the constructed path
went from nonexistent to resolving, and its AWS key from unscanned to
flagged). Fixing the noreply pattern initially introduced a self-scan
false positive — the explanatory comment contained a literal
address-shaped example the scanner correctly rejected — caught by running
the scanner on the real tree before commit and fixed by rewording.
`python -m unittest discover -s tests` — 156 tests, `OK (skipped=4)`.
`tools/public_safety_scan.py` passes clean against the real tree.

## 2026-09-02 — public-safety hardening round 4 (third exact-head review, PR #17)

**Category:** CI hardening / public-safety scanner correctness
**Compatibility:** Additive/corrective only; no runtime/API behavior changed.

### Why

A third independent Codex review against exact head `b9c77b3` returned 4
findings, two of which were criticisms of fixes made in earlier rounds of
this same recovery — the blanket test-file exemption, and a false positive
introduced by the run-joining fix. All 4 were reproduced before action.

### Change

- **Removed the blanket self-exemption entirely.** Round 1 skipped
  `tests/test_public_safety_scan.py` wholesale so its deliberate
  secret-shaped fixtures would not self-trip the scanner. That was
  strictly worse than it looked: a *real* credential committed to that
  path would also have been skipped, including when the trusted copy from
  `main` grades a PR. `SELF_TEST_FIXTURE_PATH` and both skip sites are
  gone; instead every fixture is assembled at runtime from fragments
  (`"AKIA" + "ABCDEFGHIJKLMNOP"`), so the file contains no contiguous
  match and is now scanned in full by the tool it tests. A regression test
  asserts the constant no longer exists and that a credential in that path
  is caught.
- **Run-joining no longer crosses structural boundaries.** Round 2 joined
  every `<w:t>` in a story part with no separator to catch text split
  across runs; that also joined text across paragraph, table row/cell,
  tab, and line-break boundaries, which Word does not display as
  continuous — inventing addresses the document never shows and blocking
  safe artifact updates. Those elements now emit a separator. Verified
  both directions: adjacent runs inside one paragraph are still caught,
  and paragraph/tab boundaries no longer produce a match.
- **Bot noreply identities accepted**: the username component rejected
  bracketed bot addresses (dependabot, github-actions), which would have
  failed the mandatory job for every automated commit.

### Deferred, with reason: incoming-range history scanning

The fourth finding is real and reproduced: the scan inspects only the
checked-out tip tree, so a secret added in one commit and deleted by the
tip passes both jobs while remaining reachable in history after a merge
that preserves commits. It is **not fixed here**, because implementing it
would immediately fail this PR against its own history: 4 earlier blobs of
`tests/test_public_safety_scan.py` in this branch's range still contain
the pre-fix contiguous fixture literals (verified by walking
`merge-base..HEAD`). Passing would require rewriting PR #17's history,
which the governing instruction for this recovery explicitly forbids.
Deferring is clean rather than merely convenient: once this PR merges,
those blobs are ancestors of `main`, so a later PR adding range scanning
starts from a base that already contains them and never re-scans them.
The compensating control already shipped in this same PR — the weekly
full-history gitleaks scan in `secret-scan.yml` — covers reachable
history, and the blobs in question hold synthetic test constants, not
real credentials.

### Verification

All 4 findings reproduced before action; the 3 fixed ones confirmed fixed,
including two explicit no-regression checks on the run-joining change.
Removing the exemption immediately surfaced a real self-scan hit (the
constant name `_GENERIC_SECRET` plus its assignment matched the generic
pattern), which was fixed by renaming rather than by re-adding any
exemption. `python -m unittest discover -s tests` — 159 tests,
`OK (skipped=4)`. `tools/public_safety_scan.py` passes clean against the
real tree with no path exempted.

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
3. **Fixed (usability, not a security gap) — then found to have introduced
   a real one, and fixed again.** The `Ledger-Exempt:` trailer is read from
   committed commit messages, but preflight runs *before* `git commit` — a
   genuine first-time exemption could never produce COMMIT-READY through
   the primary local path, since the commit carrying the trailer doesn't
   exist yet. The first fix added `scripts/preflight_commit.py
   --pending-exempt "FILE REASON"`, which set
   `CAMPAIGN_SIMULATION_PENDING_LEDGER_EXEMPT` and had
   `exempted_ledgers()` in `tools/validate_change_ledger.py` read it. A
   second round of automated review (after this fix was pushed) correctly
   flagged that as a **P1 CI bypass**: `validate_change_ledger.py` is the
   exact file CI executes for the required `change-ledger` check, so any
   environment variable it reads is one a pull request could set for that
   job — e.g. by editing `.github/workflows/tests.yml` — and merge with no
   commit ever carrying the real trailer. Re-fixed by removing all
   environment-variable awareness from `validate_change_ledger.py` (it is
   now, again, a pure function of committed Git history) and moving the
   prediction entirely into `preflight_commit.py`: `validate_change_ledger.py`
   gained a `--list-missing-domains` flag that only ever adds
   machine-readable `MISSING-DOMAIN:` lines to its output on the one
   waivable failure category, and **never changes its own exit code** —
   so a workflow passing this flag gains nothing. `preflight_commit.py`
   parses those lines and only treats the check as locally satisfied when
   *every* reported domain is explicitly named on `--pending-exempt`; any
   other failure category, or any uncovered domain, still fails closed.
4. **Documented, not changed.** Two findings (self-referential trust: a
   locally-modified `preflight_commit.py`/`validate_change_ledger.py` run
   directly, not from a trusted copy, could lie to itself) describe a true
   and irreducible property of any local-only gate — there is no local root
   of trust that can stop someone from lying to their own working tree. This
   was already the documented design (the real, non-bypassable boundary is
   CI's trusted-copy-from-`origin/main` execution plus the
   non-exemptable self-check above). Strengthened `preflight_commit.py`'s
   module docstring to state this explicitly rather than leaving it implicit.

**Verification:** all fixes (including the re-fix of finding 3) were
adversarially reproduced by hand before being accepted (staged a
revert-while-sensitive-change scenario and confirmed the old union logic
would have wrongly passed it while the new logic correctly fails it; staged
a self-weakening with disk reverted to safe content and confirmed the old
`HEAD`-read would have missed it while the new index-read catches it;
confirmed no candidate environment-variable name, including the exact one
this repository actually shipped and then rejected, has any effect on
`exempted_ledgers()`; confirmed `--list-missing-domains` never changes the
exit code and only reports the one waivable category). All scenarios are
now permanent regression coverage in `tests/test_validate_change_ledger.py`
(disposable temp-directory git repos via
`unittest.mock.patch.object(vcl, "ROOT", ...)`, not the real repository)
and in `tests/test_preflight_commit.py` (the coverage-decision logic:
partial coverage still fails, full coverage passes, non-exemptable
categories always fail regardless of `--pending-exempt`). Full suite: 139
tests, `OK (skipped=4)`.

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
