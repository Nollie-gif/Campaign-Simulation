# Lifecycles

## Scenario

`draft -> available -> active -> completed | abandoned | expired`

A scenario may reference zero or more hook identifiers. It does not own hook records.

## Hook

`dormant -> active -> resolved | retired`

Hook identifiers are permanent. A resolved or retired identifier is never recycled.

The next hook and scenario counters are persisted atomically in the sequel session
state. Allocation is session-scoped, so restarting the runtime cannot issue the
same identifier again.

## Save

`prepared -> validated -> committed`

Quick saves are lightweight recovery points. Final saves are durable end-state checkpoints. Both must carry a manifest that identifies the owned record revisions included in the save.

A save is committed only from `validated`. A complete checkpoint persists the
committed manifest and the snapshots of every declared record together in one
atomic file. Blank IDs, invalid timestamps, empty revision lists, mismatched
record revisions, and direct `prepared -> committed` writes are refused.
