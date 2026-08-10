# Lifecycles

## Scenario

`draft -> available -> active -> completed | abandoned | expired`

A scenario may reference zero or more hook identifiers. It does not own hook records.

## Hook

`dormant -> active -> resolved | retired`

Hook identifiers are permanent. A resolved or retired identifier is never recycled.

## Save

`prepared -> validated -> committed`

Quick saves are lightweight recovery points. Final saves are durable end-state checkpoints. Both must carry a manifest that identifies the owned record revisions included in the save.
