# Campaign Simulation Framework

Campaign Simulation is a reusable, campaign-neutral framework for exploring a protected Main Campaign in either direction:

**Prequel ← Main Campaign → Sequel**

The Main Campaign is the authoritative canon anchor. Simulation branches may read it, reason from it, and preserve continuity with it, but they never write into it automatically.

This repository contains no live private campaign state, names, locations, characters, or populated gameplay examples in its framework layer.

## Reference implementation boundary

The framework was developed alongside a private live reference implementation, **Mission 10**, where many of these contracts were first stressed by real gameplay.

Mission 10 remains private because it contains live campaign state, hidden/DM information, and working material that is part of the campaign itself. Campaign-Simulation is the reusable, campaign-neutral implementation of the systems and lessons that survived that environment.

This repository is therefore **not a synchronized mirror of Mission 10**. Campaign-specific adapters, live state, provider credentials, production identifiers, private canon and DM-only information do not belong here.

The public relationship is intentionally simple:

> Mission 10 is the private reference implementation and live simulation environment. Campaign-Simulation is the public, reusable template derived from the systems and lessons validated there.

For the current parity review, see [Public Reference Parity Audit](docs/PUBLIC_REFERENCE_PARITY_AUDIT.md).

Historical working artifacts used to document the evolution live under [artifacts/](artifacts/README.md). Those files are historical evidence, not current framework authority.

## Public use and licensing

This repository is intended to be **public-use**, not merely public-view.

The original Campaign-Simulation framework code and original framework documentation are released under the [MIT License](LICENSE), subject to the explicit scope described in [LICENSE_SCOPE.md](LICENSE_SCOPE.md). People are allowed to take the reusable framework, study it, modify it, fork it, build on it, and redistribute their MIT-licensed changes under the terms of that license.

The historical files under [`artifacts/`](artifacts/) are different. They are development fossils and some contain fan-created material based on or referring to third-party intellectual property. They are **not** included in the repository's MIT software-license grant. See the dedicated [Historical Artifact Rights Notice](artifacts/RIGHTS.md).

**Reuse the framework. Read the fossils as fossils.**

That split is deliberate. The story is useful because the evidence remains attached to it; the software is useful because people are actually allowed to take it somewhere else.

## Start here

1. On the first cold boot, follow the optional [Campaign Safety Installation](docs/safety-installation/README.md). The consent-driven sequence offers repository-only or Supabase-aware protection, presents Nollie's love token, installs the reusable LotS prompt, and writes a receipt only after verification. A compatible verified receipt prevents the ceremony from repeating.
2. Complete the three minimum playable inputs described in [Onboarding](docs/ONBOARDING.md).
3. Install the framework from its repository checkout:

   ```bash
   python -m pip install -e .
   ```

4. Start the guided setup:

   ```bash
   campaign-simulation start --main-campaign /path/to/main-campaign --runtime /path/to/simulation-runtime
   ```

   The equivalent module command is `python -m campaign_simulation start ...`.
5. Choose what you want to explore:
   - **Prequel** — choose a historical anchor before the Main Campaign.
   - **Sequel** — continue from the Main Campaign's current situation or provide another forward anchor.
6. Review the optional campaign-material menu.
7. Choose repository or optional Supabase-backed storage and begin.

The optional-material menu is informational and never blocks play.

## Branch model

Both Prequel and Sequel simulations move **forward in time**.

A Prequel does not reverse time. It starts from a user-selected historical anchor and advances toward the known Main Campaign. When it reaches the Main Campaign boundary, the convergence gate freezes the branch and asks the user what to do next.

A Sequel starts from the accepted Main Campaign state. **A Prequel checkpoint can never be used directly as a Sequel source.** If a Prequel changes history, its save data may be used as review input to establish or update the Main Campaign. Only after the user explicitly accepts that Main Campaign state may a Sequel begin from it.

The supported handoff is therefore:

**Prequel save → Main Campaign review/acceptance → Sequel**

Never:

**Prequel save → Sequel**

See [Branching](docs/BRANCHING.md) for the complete contract.

## Language policy

The framework's technical layer is deliberately written in English: source code, command names, JSON keys, schema identifiers, and lifecycle values are stable machine-facing contracts.

Campaign prose is language-neutral. A Main Campaign, Prequel, or Sequel may be written entirely in Greek, English, or any other language without changing a technical file, ID, schema, or runtime rule. The engine preserves campaign text as supplied and does not require translation before play can begin.

## Included mechanics

- branch-neutral Prequel / Sequel onboarding
- hard Main-Campaign-only source policy for every simulation branch
- historical-anchor Prequel bootstrap
- forward-anchor Sequel bootstrap
- scenario lifecycle contract
- hook lifecycle contract
- quick-save and final-save contract
- first-boot storage selection with repository fallback
- command-line guided startup (`campaign-simulation start`)
- blank entity, scenario, hook, save, session, and simulation-bootstrap templates
- Minimum Playable Campaign Gate
- optional campaign-material onboarding
- path-safe Main Campaign references
- persisted hook and scenario identifier allocation
- atomic full-checkpoint persistence
- procedure-aware mutation scope and lifecycle gates
- mutation-path audit registry for provider adapters
- credential-safe Supabase validation and repository fallback
- hard read-only Main Campaign write boundary
- explicit Prequel → Main Convergence Gate with no automatic merge

## Platform compatibility

Added cross-platform Windows compatibility and Windows CI coverage.

The framework uses native advisory locking on supported platforms: POSIX `flock` on Unix-like systems and `msvcrt.locking()` on Windows. The GitHub Actions test matrix runs the full unit/integration suite and blank-template validation on both Ubuntu and Windows with Python 3.11.

This is Windows-platform CI coverage, not a claim of certification for a specific Windows release. A separate real-machine smoke test may be used to record Windows 10-specific verification.

## Verification

Run:

```bash
python -m unittest discover -s tests -v
```
