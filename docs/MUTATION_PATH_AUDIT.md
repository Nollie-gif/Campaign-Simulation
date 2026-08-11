# Mutation Path Audit

**Scope:** campaign-neutral framework baseline. This audit is the registry that a provider adapter must reconcile against its live implementation before it activates a procedure.

The table describes ownership and coupling, not a narrative ownership tree. Hooks, Scenarios, and Deferred Events remain sibling durable entities with independent stable IDs and explicit references.

| Procedure | Allowed owner/domain family | Required coupled evidence | Forbidden drift / recovery |
| --- | --- | --- | --- |
| Quicksave / Autosave | Current runtime, Knowledge, NPC operational state, Hook/Scenario runtime state, staging/reconciliation/publication | Reconciled, validated, one checkpoint; generation-pinned adapters also need a complete receipt | No engineering/static/final-history mutation. Preserve last healthy checkpoint on failure. |
| Final Save | Quicksave domains plus finalized current-day history and live indexes | Previous live work closes coherently; day finalized; indexes reconciled | No unrelated historical rewrite. Retry through the same final-save path. |
| Knowledge-only persistence | Granular Knowledge plus its evidence/routing metadata and provider staging/publication | Knowledge reconciliation, valid generation-aware path, visibility proof | No raw runtime-visible SQL or unrelated narrative delta. |
| Scenario activation | Runtime Scenario occurrence and explicit related runtime references | Scenario references coherent; legal lifecycle transition | No static seed rewrite merely to mirror status. |
| Scenario completion | Runtime Scenario, explicit related Hooks, required consequences | Required primary-Hook relation coherent; rewards/consequences persisted in the same checkpoint | No dangling active required Hook or partial completion. |
| Hook activation / resolution / retirement | Hook runtime state and explicitly related runtime consequences | Legal one-way transition; any linked Scenario remains coherent | No lifecycle reopening or hidden secondary owner. |
| Deferred Event creation | Event, scheduler state, durable ID, explicit references | Permanent ID persisted; scheduler bookkeeping validated | No ID for ordinary resolved narrative beats. |
| Deferred Event resolution / cancellation | Event, scheduler state, explicit resulting runtime consequences | Terminal state; required consequence committed in the same checkpoint | No event terminal state without its declared consequence. |
| Start of Day | Day boundary, current runtime, deterministic mechanics, operational reconciliation | Previous day finalized; new day initialized and persisted before presentation | No silent skipped final save or unrelated definition edits. |
| Campaign Clock update | Clock and current runtime | Monotonic time and one checkpoint | No narrative interpretation or backwards time. |
| Scheduler update | Scheduler, event eligibility, current runtime | Idempotent bookkeeping and one checkpoint | No automatic narrative consequence or ownership capture. |
| Persistent ID allocation | Identifier/session state | Counter persisted atomically and never recycled | No in-memory-only allocation or duplicate ID after restart. |
| NPC operational reconciliation | NPC operational overlay and matching runtime state | Overlay and canonical runtime state reconciled | No second mutable owner for the same operational fact. |
| Engineering/schema/migration change | Code, tests, docs, workflows, schema on a focused branch | Tests, documentation coverage, PR workflow | No direct main change or runtime/campaign mutation. |
| Prequel -> Main convergence | Prequel boundary and simulation state | Main Campaign remains read-only; explicit user choice | No automatic Main Campaign write or automatic merge. |
| Finalized-history maintenance | Explicit history correction, live indexes, validation/publication | Maintenance authorization and one coherent checkpoint | No broad historical rewrite or current-runtime shortcut. |
| Git runtime publication | Dedicated recovery mirror branch only | Exact published ref verified before mirror confirmation | No direct main write and no arbitrary mirror move. |
| Provider runtime publication | Provider publication point and receipt | Generation advance, parity/read-back, recovery anchor | No partial Git/provider publication or false success receipt. |

## Current framework enforcement

- PROCEDURE_POLICIES declares allowed domains and required facts.
- validate_mutation_plan rejects forbidden scope, direct protected-branch targets, raw runtime SQL, missing generation context, illegal lifecycle transitions, and missing record coverage.
- commit_checkpoint requires a plan and writes it with the committed checkpoint.
- validate_publication_receipt provides the generation-pinned adapter completion gate.
- Negative tests cover forbidden scope, incomplete Scenario/Event transitions, Start-of-Day prerequisite, illegal lifecycle transition, raw SQL, incomplete receipt, valid save, and narration isolation.

## Adapter audit requirement

A consuming adapter must map its actual files, tables, functions, branches, and provider publication points to these domains. It must add adapter tests for every direct mutation path it finds. This registry is not a license to infer new paths from prose; the live adapter code and schema remain authoritative.
