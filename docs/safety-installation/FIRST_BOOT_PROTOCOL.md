# First-Boot Safety Installation Protocol

## Purpose

Provide a short, consent-driven installation sequence for DMs who may have no software-engineering background. The sequence is intentionally multi-turn. Do not collapse consent, configuration, installation, and verification into one reply.

## State 0 — Detection

Check for a verified compatible receipt at `.campaign-simulation/safety-installation.json`.

If it exists and matches the installed mechanism, continue normal onboarding without replaying this sequence.

If it is missing, invalid, or incompatible:

- remain read-only;
- do not create branches, checkpoints, runtime objects, or receipts yet;
- present State 1.

## State 1 — Storage-aware invitation

Display exactly this user-facing message:

> Before we begin, I can install an optional safety layer for future campaign engineering changes.
>
> It gives us a protected place to test new mechanics without treating unfinished work as production or sacrificing gameplay progress that continued while an experiment was running.
>
> Choose the protection mode:
>
> 1. **Repository only** — protected branches, fresh checkpoints, review, verification, and rollback planning without an external runtime.
> 2. **Supabase aware** — repository protection plus explicit staging/production boundaries and external-state recovery checks.
> 3. **Not yet** — install repository protection now and preserve a future Supabase upgrade path.
>
> No repository, campaign state, or external service has been changed.
>
> Reply with **1**, **2**, or **3**, and confirm that you want to continue.

Do not infer Supabase from the presence of credentials alone. The human chooses the mode.

## State 2 — Human configuration confirmation

Accept a clear selection and confirmation.

If the reply is ambiguous, ask one short clarifying question and remain read-only.

If the human declines, record nothing and continue without the optional safety layer.

If the human confirms, present State 3.

## State 3 — Love token and final mutation consent

Display the text in [LOVE_TOKEN.md](LOVE_TOKEN.md), including its link to the reusable [LotS Safe Build Prompt](LOTS_SAFE_BUILD_PROMPT.md).

Then display:

> **Ready to install the Campaign Safety Layer.**
>
> Selected mode: `[repository-only | supabase-aware]`
>
> Reply: **Install and protect the campaign.**

This is the final consent boundary before any installation mutation.

## State 4 — Read-only preflight

After the exact intent to install is clear:

1. Read current repository truth and installation instructions.
2. Resolve the current default-branch SHA.
3. Confirm protected branch/PR workflow.
4. Propose a fresh checkpoint and focused installation branch.
5. Declare the external-state boundary.
6. In Supabase-aware mode, validate configuration without exposing credentials.
7. Return `PASS` or `HOLD` with the proposed next action.

If evidence is missing, conflicting, blocked, or unverifiable:

```text
STOPPED — [missing or conflicting evidence]. No mutation performed.
```

Do not write a receipt on `HOLD`.

## State 5 — Installation

On `PASS`, install only the approved safety components:

- experiment safety runbook;
- cold-start preflight instructions;
- checkpoint and experiment-branch conventions;
- external-state boundaries for the selected mode;
- the reusable LotS Safe Build Prompt;
- an installation inventory sufficient for safe removal.

Installation must not mutate campaign story/runtime truth.

## State 6 — Verification and receipt

Verify by read-back that every installed component matches the approved version and selected mode.

Only after verification succeeds, write:

```json
{
  "schema_version": 1,
  "status": "complete",
  "installer_version": 1,
  "mode": "repository-only",
  "artifact_installed": true,
  "installed_components": [],
  "verification": {
    "status": "pass",
    "verified_at": "<ISO-8601 timestamp>",
    "repository_main_sha": "<current main SHA>",
    "runtime_generation": null
  }
}
```

For Supabase-aware mode, set `mode` to `supabase-aware` and record only non-secret identifiers needed for verification and removal. Never store credentials in the receipt.

Then display:

> **Campaign Safety Layer installed and verified.**
>
> Mode: `[repository-only | supabase-aware]`
>
> Verification: `PASS`
>
> This mechanism exists to reduce operational burden—not to interrupt gameplay.
>
> Take care of your campaign. ❤️

## Safe removal / uninstall

An uninstall request begins read-only.

1. Read and validate the installation receipt.
2. Inventory only components explicitly owned by that receipt.
3. Present an uninstall plan and wait for explicit approval.
4. Remove only verified receipt-owned components.
5. Never delete or roll back campaign history, saves, published generations, user content, credentials, or unrelated Supabase data.
6. If ownership is ambiguous, return `HOLD`.
7. Verify that the campaign still boots.
8. Report exactly what was removed and what remains.

Deleting the receipt is the final uninstall step, never the first.
