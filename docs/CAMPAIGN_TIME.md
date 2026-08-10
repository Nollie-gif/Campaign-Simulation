# Campaign Time

Campaign Time is deterministic infrastructure for in-world time. It never reads wall-clock time and never invents narrative outcomes.

## Two clocks, one state

The engine intentionally keeps two kinds of time together without pretending they are equally precise:

- **Presentation time** — `day` plus a broad `phase` (`unknown`, `dawn`, `morning`, `midday`, `afternoon`, `evening`, `night`, `late_night`). This is what the DM can safely use for narration and broad sequencing.
- **Monotonic duration** — `elapsed_campaign_minutes`. This is an engine-only cursor that advances only when an in-world duration is actually established. It is not a minute-of-day clock.

The separation prevents a broad statement such as "afternoon" from becoming fake precision such as 15:42.

## Runtime state

The engine-owned checkpoint record ID is `campaign_clock`.

Required state:

```json
{
  "schema_version": 1,
  "day": 1,
  "phase": "unknown",
  "elapsed_campaign_minutes": 0,
  "long_rests_completed": 0
}
```

## Safe advancement rules

- Explicit durations advance `elapsed_campaign_minutes` exactly.
- A completed Long Rest increments `long_rests_completed`; a duration is added only when the duration is actually established.
- Day and phase observations advance only when the fiction/mechanics establish them.
- Day may never decrease.
- A known phase may not move backwards within the same day.
- A new day may begin at any valid phase.
- If only a broad phase becomes known, update the phase and leave `elapsed_campaign_minutes` unchanged.
- If only an exact duration becomes known, advance the monotonic cursor and do not invent a new day/phase.
- If both are known, apply both in the same semantic time update.

Travel, rests, rituals, downtime, spell durations, appointments and other mechanically established durations are normal sources of exact elapsed minutes. Chat length and message count are never time sources.

## Why Long Rest has a counter

`next Long Rest` is a common deterministic trigger but it should not depend on guessing when midnight happened. `long_rests_completed` gives the scheduler a monotonic event counter: an event created at rest count N can deterministically become eligible at N+1.

## Downstream consumers

Campaign Clock does not save, narrate or mutate unrelated campaign state. It is consumed by sibling subsystems:

- Autosave asks whether the current time/progress boundary warrants a checkpoint.
- Deferred Event Scheduler asks whether a pending obligation is now eligible.
- Future systems may use the same clock without owning it.

All durable clock changes travel through the existing validated checkpoint/persistence pipeline.
