# Mutation and Lifecycle Gates

**Status:** active baseline. The first consuming adapter (Mission 10) passed focused integration/fault tests, server-side protection checks, and production migration verification on 2026-08-12.

This module is the framework's procedure-level safety layer. It protects persistence authority; it does not decide story outcomes, create narrative content, or gate ordinary conversation.

## Safe path

`simple request -> procedure route -> mutation plan -> candidate validation -> atomic commit/publication -> verified receipt`

The request vocabulary stays simple. For example, `quicksave`, `final save`, `knowledge save`, `Scenario completion`, `Event resolution`, and `Start of Day` route to internal `Procedure` values. An unknown request is rejected rather than silently mapped to a weaker path.

## What the gate enforces

- A procedure may mutate only its declared `MutationDomain` values.
- A checkpoint plan must cover every record that the checkpoint declares.
- One-way Scenario, Hook, and Deferred Event transitions are validated centrally.
- Coupled postconditions are required before a candidate can proceed. Examples include coherent required Hook references for Scenario completion, persisted consequences for terminal events, and a finalized previous day for Start of Day.
- A generation-pinned adapter must declare a strictly newer staging generation. Runtime-owned SQL mutations must use the gated SQL path; raw SQL is rejected.
- `main` is always a forbidden mutation target. `runtime-published` may move only through the dedicated Git publication procedure.
- A generation-pinned publication receipt must prove the published generation, exact Git ref, day, store parity, committed checkpoint, Git mirror confirmation, and retained recovery anchor.

A failed check raises `MutationGateError` with a stable code. The caller must preserve the last healthy checkpoint and retry only through the same intended procedure; it must not attempt compensating writes or broaden scope.

## Persistence modes

The framework supports two safe implementations without creating parallel save systems:

- **repository** — the framework's atomic checkpoint is the authoritative commit. `commit_checkpoint(..., gate_plan=...)` refuses an absent or invalid plan and records the plan in the checkpoint audit metadata.
- **generation_pinned** — an adapter stages a future generation, validates the plan, publishes through its provider-owned transaction, and calls `validate_publication_receipt(...)` after read-back.

The generic framework intentionally does not claim to prove an external provider's publication. That proof remains the adapter's responsibility.

## API surface

- `route_user_request(request)`
- `MutationPlan` and `MutationOperation`
- `validate_mutation_plan(plan, record_ids=...)`
- `validate_publication_receipt(plan, receipt)`
- `commit_checkpoint(..., gate_plan=...)`
- `plan_to_mapping(plan)`

Static definitions describe durable identity/mechanics. Runtime state describes current truth. A procedure may not rewrite a static definition simply to mirror current status.

## Narrative boundary

The gate is invoked only when a durable mutation candidate exists. A DM can narrate, reason, or present an ordinary scene without creating a plan, ID, timer, or persistence transaction. Durable IDs remain reserved for entities that actually need independent identity or lifecycle.
