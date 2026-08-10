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
- [ ] Add canonical monotonic elapsed campaign time for deterministic durations/deadlines.
- [ ] Prefer a duration cursor such as `elapsed_campaign_minutes`; this is engine time, not player-facing clock precision.
- [ ] Define safe advancement rules for travel, rests, rituals, downtime and explicitly known durations.
- [ ] Define behavior when only a broad phase is known but exact elapsed duration is not.
- [ ] Add regression tests for monotonic time, day rollover and no-backwards-time behavior.

## Automatic Autosave

- [x] Autosave evaluator is deterministic and side-effect free.
- [x] AI supplies semantic inputs; evaluator decides trigger/no-trigger.
- [x] Approximately 3–5 autosaves per active campaign day is a soft target.
- [x] Major/critical persistent boundaries can trigger immediate autosave.
- [x] Duplicate state may suppress redundant automatic checkpoints.
- [x] Manual save remains a hard override.
- [x] Autosave is an initiator only; it must use the existing validated save pipeline.
- [ ] Finish playtest tuning against real Mission 10 gameplay.
- [ ] Review false-positive and false-negative autosave decisions.
- [ ] Merge only after playtest behavior is stable.

## Deferred Event Scheduler — approved design, NOT YET IMPLEMENTED

- [x] Scheduler solves a separate problem from Hooks: future world obligations/deadlines must not rely on AI memory.
- [x] Architectural position: `Campaign Clock -> Scheduler -> eligible events -> DM/runtime -> state mutation -> save pipeline`.
- [x] Scheduler is a sibling of Autosave, not part of Autosave.
- [x] Scheduler must never write narrative or decide consequences.
- [x] Scheduler may reference Hooks, NPCs, locations, scenarios or other stable IDs without owning them.
- [x] Hook/Event relationship uses references + atomic resolution, not mutual ownership.
- [x] Example: rescue Hook active + `+24 campaign hours` event; rescue cancels event, deadline expiry surfaces event to DM.
- [x] Event eligibility may transform the Hook graph through normal DM/runtime resolution.
- [ ] Add permanent non-recycled `event` identifier namespace.
- [ ] Define minimal event lifecycle: `pending -> resolved | cancelled`.
- [ ] Do not persist a separate `eligible` lifecycle state in v1 unless testing proves it necessary.
- [ ] Define event trigger types for v1:
  - [ ] absolute campaign day/time target;
  - [ ] relative elapsed duration (`+N` campaign minutes/hours/days);
  - [ ] next Long Rest;
  - [ ] explicit state condition;
  - [ ] location/event transition.
- [ ] Add idempotency/dedupe key for event creation retries.
- [ ] Evaluate only published/committed scheduler state during normal runtime reads.
- [ ] Surface all currently eligible pending events to DM/runtime; do not auto-resolve them.

## Crash / replay safety for Scheduler

- [x] Preferred semantics: at-least-once delivery + exactly-once committed resolution.
- [x] Crash before resolution commit => event remains `pending` and may surface again after load.
- [x] Crash after resolution commit => event is `resolved`/`cancelled` and must not fire again.
- [ ] Event resolution status and resulting campaign state mutations must be persisted in the same checkpoint/generation.
- [ ] Test crash/reload before resolution commit.
- [ ] Test crash/reload after resolution commit.
- [ ] Test duplicate creation retry using idempotency key.
- [ ] Test multiple eligible events in the same clock advancement.

## Hooks / IDs / Saves integration

- [x] Hooks remain owners of narrative Hook lifecycle.
- [x] Events get their own permanent IDs; do not reuse Hook IDs.
- [x] Events may store `origin_hook_id` and other stable references.
- [x] Scheduler state should become a normal first-class checkpoint record.
- [x] Staging-only events must never become gameplay truth before publication.
- [x] Aborted staging means the staged event never existed for published gameplay.
- [ ] Extend persistent identifier allocation with `event` kind.
- [ ] Define scheduler-state schema.
- [ ] Add scheduler-state validation to save/checkpoint validation.
- [ ] Add generation/publication tests where event creation, cancellation and resolution remain atomic with related state.

## Future extensibility — do not overengineer v1

- [x] Scheduler must stay domain-agnostic.
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
- [x] No backwards campaign time.
- [x] No reuse/recycling of persistent IDs.
- [x] No staging leakage into published runtime.
- [x] Feature remains removable: disabling Clock/Scheduler must not break manual saves or the core simulation engine.

## Recommended implementation order

- [ ] 1. Stabilize Campaign Clock + Autosave playtest.
- [ ] 2. Add monotonic elapsed campaign-time cursor.
- [ ] 3. Add tests for deterministic time advancement.
- [ ] 4. Design minimal scheduler-state schema.
- [ ] 5. Add permanent event IDs.
- [ ] 6. Implement pure side-effect-free scheduler evaluator.
- [ ] 7. Add checkpoint/generation integration.
- [ ] 8. Add crash/replay/idempotency tests.
- [ ] 9. Playtest real deferred consequences.
- [ ] 10. Only then consider NPC Projects / World Ticks.

## Design goal

The runtime should remember operational campaign obligations so the DM can focus on being a DM instead of remembering timers, deferred consequences, save cadence and hidden bookkeeping.
