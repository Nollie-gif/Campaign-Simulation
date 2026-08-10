# Automatic Autosave

Automatic Autosave decides when established gameplay progress warrants a checkpoint. It is a deterministic initiator, not a persistence engine.

## Responsibility split

- The AI/runtime supplies semantic facts: scene resolved or not, persistent-change level, optional state fingerprint, and whether a manual save was requested.
- Campaign Clock supplies current campaign day and broad phase.
- Autosave policy returns `trigger`, `reason`, and the next autosave state.
- The active storage adapter performs the normal validated save flow if `trigger` is true.

Autosave never writes directly to storage and never bypasses save validation or locking.

## Persistent-change levels

- `none`
- `minor`
- `meaningful`
- `major`
- `critical`

Drama alone does not determine the level. Classification follows durable campaign continuity.

## Policy

Priority order:

1. Manual save request -> trigger.
2. Exact duplicate of the last fingerprint -> suppress automatic duplicate.
3. Critical persistence boundary -> trigger even beyond the ordinary cap.
4. Five automatic saves already today -> suppress ordinary automatic triggers.
5. Major persistent event -> trigger.
6. Meaningful progress plus campaign-day transition -> trigger.
7. Meaningful progress plus established day-phase transition -> trigger.
8. Three resolved scenes plus meaningful unsaved progress -> trigger.
9. Otherwise continue.

The 3-5 saves/day goal is deliberately soft. Quiet days may produce fewer; critical boundaries may produce more.

Manual saves reset accumulated unsaved progress but do not consume the automatic-save soft cap.

## Checkpoint state

The engine-owned record ID is `autosave_state`. It exists so the runtime does not need chat memory to remember save cadence.

Disabling Automatic Autosave must leave manual saves and the core persistence engine fully functional.
