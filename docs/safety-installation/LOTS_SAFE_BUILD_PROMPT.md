# Campaign Simulation — LotS Safe Build Prompt

> Choose the quest objective. Let the agent plan. Let protected infrastructure execute.

Copy and paste the following into a fresh campaign engineering chat.

---

I want to build or change:

`[describe the desired outcome in one sentence]`

## Control model

Treat this as a player-level semantic command.

**Human WHAT:** I declare the outcome I want.

**Agent PLAN:** Translate it into a scoped engineering plan. You may choose code, abstractions, naming, decomposition, and language where appropriate.

**Protected HOW:** Use deterministic infrastructure for sensitive execution.

**Freedom of implementation does not mean freedom of architecture.** Current repository truth, the installed safety runbook, active project controls, runtime authority, publication semantics, and the single approved persistence path remain invariants unless an explicit verified decision changes them. Do not bypass them, create a second authority or persistence path, or touch production for convenience.

## Cold-start preflight

Before proposing implementation or mutation, read the installed Experiment Safety Runbook and installation receipt. Check the current repository, relevant project controls, and active decision records using current evidence—not chat memory.

Stay read-only. Return `PASS` or `HOLD`:

```text
Experiment:
Repository / target branch:
Relevant control record:
Workflow permission:
Safety gates:
Current main SHA:
Current published runtime generation (if any):
Proposed fresh checkpoint / experiment branch:
External-state boundary:
Architecture invariants:
Allowed next action:
```

Explain the result and next safe action in the user's preferred language. Do not ask the user to remember Git internals. Do not implement yet; wait for approval after the preflight card.

## Promotion and live-progress protection

Before merge or promotion, re-read the latest main SHA and current published runtime generation. Rebase or update and test against the latest live state. Preserve all newer gameplay progress; never use the experiment's starting checkpoint to roll back a campaign that continued while the experiment was running.

A Git rollback does not undo Supabase or other external writes. Any write-capable experiment needs a declared test/staging boundary or an explicit production-adjacent recovery plan.

## Safe removal / uninstall

If I ask to remove this safety layer, begin with a read-only inventory and identify only the files, hooks, configuration, and optional runtime objects recorded by its installation receipt. Return an uninstall plan and wait for explicit approval.

Never delete or roll back campaign history, saves, published generations, user content, credentials, or unrelated Supabase data as part of uninstall. If ownership is ambiguous, return `HOLD`. After approved removal, verify that the campaign still boots and report exactly what remains.

## Stop rule

If evidence is missing, conflicting, blocked, or unverifiable:

```text
STOPPED — [missing or conflicting evidence]. No mutation performed.
```
