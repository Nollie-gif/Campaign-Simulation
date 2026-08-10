# Branching Contract

## Canon anchor

The Main Campaign is the authoritative, read-only anchor for every simulation.

The framework supports two equal branch modes:

**Prequel ← Main Campaign → Sequel**

Neither branch writes automatically into the Main Campaign.

## Source lock

Every simulation branch starts from the accepted Main Campaign.

A Prequel checkpoint is **never** a legal Sequel source. If the Prequel changes history, its save data may be used only as review input to establish or update the accepted Main Campaign state. After that human-controlled Main Campaign update is complete, a new Sequel may start from Main.

Supported handoff:

**Prequel save → Main Campaign review/acceptance → Sequel**

Forbidden handoff:

**Prequel save → Sequel**

This keeps the engine flat and predictable. It does not build an implicit tree of inherited alternate timelines.

## Prequel

A Prequel explores a point before the Main Campaign.

It requires a short historical anchor supplied by the user. The simulation then moves forward in time from that anchor.

The framework does not attempt to "run time backwards" from the Main Campaign because reverse simulation creates unnecessary causal ambiguity.

When a Prequel reaches the declared Main Campaign boundary, it must freeze at a committed checkpoint and use the Prequel → Main Convergence Gate.

The committed Prequel checkpoint is preserved as simulation evidence and review input. It does not gain authority to source a Sequel.

## Sequel

A Sequel explores the future.

Its source is always the accepted Main Campaign. By default, its anchor is the Main Campaign's current starting situation. The user may provide another forward anchor inside the accepted Main Campaign state instead.

## Shared mechanics

Prequel and Sequel branches share the same scenario, hook, save, storage, identifier, and knowledge-boundary mechanics.

Branch direction changes the temporal anchor and boundary behavior; it does not create a separate simulation engine.

## Runtime persistence

The selected branch is persisted as `simulation-branch.json` inside the local simulation runtime. This file records the mode, anchor, source type, source policy, relative position, forward time direction, read-only Main Campaign access, and boundary behavior.

The runtime path must remain outside the Main Campaign directory and may not be an ancestor that contains the Main Campaign.
