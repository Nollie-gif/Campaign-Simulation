# Lifecycles

## Scenario

`draft -> available -> active -> completed | abandoned | expired`

A scenario may reference zero or more hook identifiers. It does not own hook records.

## Hook

`dormant -> active -> resolved | retired`

Hook identifiers are permanent. A resolved or retired identifier is never recycled.

## Deferred Event

`pending -> resolved | cancelled`

Deferred Event identifiers are permanent and use their own `event-000001` namespace. Events may reference Hooks, Scenarios or other stable campaign IDs, but they do not own those records.

Eligibility is derived by the Deferred Event Scheduler and is intentionally **not** a persisted lifecycle state. A pending event may surface more than once until its resolution/cancellation is committed. This gives the scheduler at-least-once delivery while keeping resolution exactly-once at the committed-checkpoint level.

The next hook, scenario and event counters are persisted atomically in the simulation session state. Allocation is session-scoped, so restarting a Prequel or Sequel runtime cannot issue the same identifier again.

## Save

`prepared -> validated -> committed`

Quick saves are lightweight recovery points. Final saves are durable end-state checkpoints. Both must carry a manifest that identifies the owned record revisions included in the save.

A save is committed only from `validated`. A complete checkpoint persists the committed manifest and the snapshots of every declared record together in one atomic file. Blank IDs, invalid timestamps, empty revision lists, mismatched record revisions, and direct `prepared -> committed` writes are refused.

Engine-owned runtime records (`campaign_clock`, `autosave_state`, `scheduler_state`) receive subsystem validation before a checkpoint may commit.

If an eligible event is resolved or cancelled, the updated `scheduler_state` and every resulting campaign-state mutation must be part of the same checkpoint/publication generation.

## Prequel → Main convergence

When a Prequel reaches the declared scene where the Main Campaign begins or converges, it enters `frozen_at_main_boundary`. The engine creates an explicit decision state and **does not write to Main Campaign**. The user then chooses one of exactly three paths:

1. `enter_main_unchanged` — resume the existing Main Campaign exactly as it is.
2. `propose_canon_changes` — produce reviewable proposed changes; a separate, explicit Main Campaign owner approval is required before any write.
3. `continue_as_alternate_timeline` — continue the Prequel as an independent timeline without merging it into Main.

There is intentionally no automatic merge or automatic canon promotion.
