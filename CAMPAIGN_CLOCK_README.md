# Campaign Clock — Development Checklist

Purpose: keep the Campaign Clock work self-contained and easy to resume from a fresh chat without relying on conversation memory.

## Core principle

- [x] Campaign Clock tracks in-world campaign time, not real-world wall-clock time.
- [x] AI/runtime performs conservative semantic time evaluation.
- [x] Deterministic subsystems consume evaluated time/state.
- [x] No subsystem invents narrative outcomes.
- [x] Existing save/persistence architecture remains authoritative.

## Campaign Clock

- [x] Broad presentation phases defined: `unknown`, `dawn`, `morning`, `midday`, `afternoon`, `evening`, `night`, `late_night`.
- [x] Explicit/mechanical durations override intuition.
- [x] Chat/message count never equals elapsed campaign time.
- [x] Uncertain time does not create fake progression.
- [x] Fast-forward across multiple phases yields one consolidated evaluation.
- [x] Canonical monotonic `elapsed_campaign_minutes` added for deterministic durations/deadlines.
- [x] Monotonic cursor is engine duration, not player-facing minute-of-day precision.
- [x] Safe advancement rules defined for travel, rests, rituals, downtime and other established durations.
- [x] If only a broad phase is known, presentation time may advance while elapsed duration remains unchanged.
- [x] `long_rests_completed` added as a monotonic trigger counter.
- [x] Same-day known phases cannot move backwards; campaign day cannot move backwards.
- [x] Regression tests cover monotonic duration, explicit day rollover, phase ordering and conservative unknown-time behavior.

## Automatic Autosave

- [x] Autosave evaluator is deterministic and side-effect free.
- [x] AI supplies semantic inputs; evaluator decides trigger/no-trigger.
- [x] Approximately 3–5 autosaves per active campaign day is a soft target.
- [x] Major/critical persistent boundaries can trigger immediate autosave.
- [x] Duplicate state may suppress redundant automatic checkpoints.
- [x] Manual save remains a hard override.
- [x] Manual save resets accumulated unsaved progress without consuming the automatic-save soft cap.
- [x] Autosave is an initiator only; it must use the existing validated save pipeline.
- [x] Autosave runtime state is a validated first-class checkpoint record (`autosave_state`).
- [x] Unit tests cover phase/day transitions, accumulation, duplicate suppression, cap behavior and critical override.
- [ ] Finish playtest tuning against real gameplay.
- [ ] Review false-positive and false-negative autosave decisions from that playtest.
- [ ] Merge only after playtest behavior is stable.

## Deferred Event Scheduler — v1 implemented

- [x] Scheduler solves a separate problem from Hooks: future world obligations/deadlines must not rely on AI memory.
- [x] Architectural position: `Campaign Clock -> Scheduler -> eligible events -> DM/runtime -> state mutation -> save pipeline`.
- [x] Scheduler is a sibling of Autosave, not part of Autosave.
- [x] Scheduler never writes narrative or decides consequences.
- [x] Scheduler may reference Hooks, NPCs, locations, scenarios or other stable IDs without owning them.
- [x] Hook/Event relationship uses references + atomic resolution, not mutual ownership.
- [x] Event eligibility may transform the Hook graph only through normal DM/runtime resolution.
- [x] Permanent non-recycled `event-000001` identifier namespace added.
- [x] Minimal lifecycle implemented: `pending -> resolved | cancelled`.
- [x] No persisted `eligible` lifecycle state in v1.
- [x] v1 trigger types implemented:
  - [x] absolute campaign day/broad-phase target;
  - [x] relative elapsed duration normalized to a due monotonic cursor;
  - [x] next Long Rest via monotonic rest counter;
  - [x] explicit JSON state condition;
  - [x] generic location/event transition key.
- [x] Optional guard condition supported for deadline-plus-world-state logic.
- [x] Idempotency/dedupe key added for event creation retries.
- [x] Reusing a dedupe key for a different event definition is refused.
- [x] Runtime evaluation surfaces all currently eligible pending events deterministically and never auto-resolves them.
- [x] Committed checkpoint loading rejects uncommitted save manifests; generation-pinned adapters must expose only published scheduler state.

## Crash / replay safety for Scheduler

- [x] Semantics: at-least-once delivery + exactly-once committed resolution.
- [x] Crash before resolution commit => event remains `pending` and surfaces again after load.
- [x] Crash after resolution commit => event is `resolved`/`cancelled` and cannot fire again.
- [x] Event status and resulting campaign-state mutations are persisted together in one atomic checkpoint.
- [x] Fault-injection test proves failed atomic replacement preserves both previous pending event state and previous world state.
- [x] Test duplicate creation retry using idempotency key.
- [x] Test multiple eligible events in the same clock advancement.
- [x] Test resolved/cancelled events never fire again.

## Hooks / IDs / Saves integration

- [x] Hooks remain owners of narrative Hook lifecycle.
- [x] Events have their own permanent IDs; Hook IDs are never reused for events.
- [x] Events may store `origin_hook_id` and other stable references.
- [x] Scheduler state is a first-class checkpoint record (`scheduler_state`).
- [x] Campaign Clock and Autosave state are also first-class engine-owned checkpoint records.
- [x] Scheduler-state schema and runtime validation are implemented.
- [x] Save/checkpoint validation rejects malformed Clock, Autosave and Scheduler records before commit.
- [x] Atomic checkpoint tests cover event resolution/cancellation together with related world-state mutation.
- [x] Staging-only events are not committed gameplay truth; aborted/failed checkpoint writes leave the previous committed registry intact.
- [ ] When a generation-pinned storage adapter consumes this subsystem, add adapter-specific publication/staging regression tests there.

## Future extensibility — do not overengineer v1

- [x] Scheduler is domain-agnostic.
- [x] Scheduler does not know NPC logic, economy rules or narrative meaning.
- [x] Future NPC Projects may create scheduled one-shot milestones.
- [x] Future World Ticks may create scheduled one-shot evaluations.
- [x] Recurring jobs are intentionally out of v1 scope.
- [x] A resolved event may schedule another one-shot event instead of adding cron/recurrence complexity.
- [ ] Revisit recurring events only after real use proves they are needed.

## Non-negotiable safety rules

- [x] No automatic narrative generation from deterministic infrastructure.
- [x] No automatic Hook resolution merely because a timer expired.
- [x] No production save bypasses the existing persistence pipeline.
- [x] No backwards campaign day or known same-day phase.
- [x] No reuse/recycling of persistent IDs.
- [x] No staging leakage into published runtime by adapter contract.
- [x] Feature remains removable: disabling Clock/Scheduler does not break manual saves or the core simulation engine.

## Recommended implementation order

- [ ] 1. Stabilize Campaign Clock + Autosave through real gameplay playtest.
- [x] 2. Add monotonic elapsed campaign-time cursor.
- [x] 3. Add tests for deterministic time advancement.
- [x] 4. Design and validate minimal scheduler-state schema.
- [x] 5. Add permanent event IDs.
- [x] 6. Implement pure side-effect-free scheduler evaluator.
- [x] 7. Add atomic checkpoint integration.
- [x] 8. Add crash/replay/idempotency tests.
- [ ] 9. Playtest real deferred consequences.
- [ ] 10. Only then consider NPC Projects / World Ticks.

## Files added by this branch

- `src/campaign_simulation/clock.py`
- `src/campaign_simulation/autosave.py`
- `src/campaign_simulation/scheduler.py`
- `docs/CAMPAIGN_TIME.md`
- `docs/AUTOSAVE.md`
- `docs/DEFERRED_EVENT_SCHEDULER.md`
- `schemas/campaign-clock.schema.json`
- `schemas/autosave-state.schema.json`
- `schemas/scheduler-state.schema.json`
- focused Clock / Autosave / Scheduler / checkpoint regression tests

## Design goal

The runtime should remember operational campaign obligations so the DM can focus on being a DM instead of remembering timers, deferred consequences, save cadence and hidden bookkeeping.
