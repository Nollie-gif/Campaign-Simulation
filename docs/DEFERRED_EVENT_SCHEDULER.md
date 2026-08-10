# Deferred Event Scheduler

The Deferred Event Scheduler is campaign-neutral infrastructure for future obligations, deadlines and deferred consequences.

It answers one question only:

> Which pending events are eligible now?

It never decides what the consequence means and never writes narrative.

## Architectural position

```text
Gameplay resolution
        ↓
Campaign Clock updates
        ↓
Scheduler evaluates pending events
        ↓
0..N eligible events surface
        ↓
DM/runtime resolves consequences
        ↓
Campaign-state mutations
        ↓
Existing save/autosave pipeline persists the result
```

Scheduler and Autosave are siblings. Both consume Campaign Time; neither owns the other.

## Event lifecycle

```text
pending -> resolved
        -> cancelled
```

There is deliberately no persisted `eligible` state in v1. Eligibility is derived from committed state every time the scheduler evaluates.

That gives the subsystem its crash behavior:

- Crash before resolution commit: the event remains `pending` and may surface again.
- Crash after resolution commit: the event is `resolved` or `cancelled` and cannot fire again.

This is **at-least-once delivery with exactly-once committed resolution**.

## Event identity

Events use the permanent `event-000001` identifier namespace. IDs are allocated by the same durable, advisory-locked counter system used for Hooks and Scenarios and are never recycled.

Every event also has a `dedupe_key`. Retrying creation with the same key and identical definition returns the existing event instead of creating a duplicate. Reusing the same key for a different definition is rejected.

## Trigger types

v1 supports five deterministic trigger families:

1. `campaign_time` — eligible when a target campaign day/broad phase is definitely reached.
2. `elapsed_time` — eligible when the monotonic `elapsed_campaign_minutes` cursor reaches a stored due value. Relative delays are normalized into that due value when the event is created.
3. `long_rest` — eligible when the monotonic Long Rest counter reaches the stored due count.
4. `state_condition` — eligible when an explicit JSON-state predicate becomes true.
5. `transition` — eligible when the current resolved runtime boundary reports a matching stable transition key.

Recurring jobs are intentionally out of v1. A resolved event may schedule another one-shot event later.

## Optional guard

Any event may carry a `guard` condition in addition to its trigger.

Example conceptually:

- trigger: `+24 campaign hours`
- guard: target status is not `safe`

When the deadline becomes due but the guard is false, the scheduler does not auto-cancel or auto-resolve anything. It reports the event as due-but-blocked so the owning DM/runtime layer can reconcile/cancel it explicitly.

## Hook relationship

Scheduler events may reference stable IDs such as:

```json
{
  "origin_hook_id": "hook-000042"
}
```

The event does not own the Hook lifecycle.

A Hook may cause an event to be scheduled; the event may later surface a consequence that causes the DM/runtime to resolve one Hook and activate another. Those mutations still happen through the normal Hook lifecycle and save pipeline.

This prevents circular ownership such as "Hook owns Event owns Hook" while still allowing both systems to interact.

## State conditions

State-condition paths are arrays of object keys. Supported operators are:

- `equals`
- `not_equals`
- `exists`
- `not_exists`
- `greater_or_equal`
- `less_or_equal`
- `contains`

The scheduler only evaluates the state snapshot supplied by the runtime. It does not know what NPCs, locations, money, factions or quests mean.

## Transition triggers

Transition keys are domain-neutral strings supplied by the current resolved gameplay boundary, for example a location entry or another stable state transition.

A transition trigger is intentionally ephemeral at evaluation time. The persistence owner must ensure that a crash before commit causes the unresolved gameplay boundary to be replayed or reconstructed; the scheduler itself does not create a hidden transition log in v1.

## Persistence contract

The engine-owned checkpoint record ID is `scheduler_state`.

Scheduler state is validated before a checkpoint commits. Event resolution/cancellation and the campaign-state consequence it caused must be included in the **same checkpoint/publication generation**.

This means:

- staging-only event creation is not published truth;
- aborting staging means the event never existed to published gameplay;
- an interrupted resolution commit leaves both the previous campaign state and the event's previous `pending` status intact;
- a successful commit advances both together.

Adapters with generation-pinned storage must apply the same rule: only published scheduler state is eligible for normal gameplay reads.

## Future systems

NPC Projects and World Ticks should use the Scheduler as infrastructure rather than adding their own timer engines.

The Scheduler stays intentionally ignorant of their domain rules. It remembers *when something deserves attention* so the DM/runtime can focus on *what happens next*.
