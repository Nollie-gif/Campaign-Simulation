# Public Reference Parity Audit

Status: completed public-reference audit. Campaign-Simulation is now public; this document records the parity boundary and remaining framework-review candidates.

## Why this exists

Mission10-Simulation-Sequel remains the private reference implementation and live simulation environment. Campaign-Simulation is the public, reusable framework derived from systems and lessons validated there.

This is not a byte-for-byte mirror contract. The purpose of this audit is to identify which Mission 10 lessons belong in the campaign-neutral framework, which already exist here, and which must remain adapter-specific.

## Already represented in Campaign-Simulation

The following Mission 10 lessons are already generalized here and should not be duplicated:

- protected Main Campaign boundary and explicit simulation branch ownership
- atomic checkpoint persistence and durable identifier allocation
- procedure-aware mutation/lifecycle gates
- repository and generation-pinned persistence modes
- publication receipts with exact Git ref, published day/generation, parity, mirror confirmation, and recovery anchor
- scenario, hook, deferred-event and start-of-day lifecycle contracts
- campaign-neutral ownership rules and optional derived knowledge projection
- repository-first operation with optional Supabase support and safe fallback
- blank entity/location/item/supporting-character/knowledge templates
- protected-main / PR / CI engineering workflow

## Mission 10 concepts that are adapter-specific and should stay private

These are implementation details of the live Mission 10 environment, not generic framework features to copy:

- exact Supabase project, SQL functions, migrations, tables, RLS posture and production generation numbers
- Mission 10 path mappings, state file names, NPC IDs, hook IDs, scenario IDs and campaign-specific validators
- runtime-published / runtime-save-staging branch choreography as a required universal implementation
- current Baldur's Gate canon, player/NPC state, hidden DM information, live knowledge claims and active narrative handoffs
- engineering-release commit trailers and two-parent merge shape where they are specific to the Mission 10 adapter

## Generic candidates learned from Mission 10 that deserve explicit framework review

These should be reviewed one by one. Promotion is evidence-led, not automatic.

### 1. Runtime read contract / selective hydration

Mission 10 proved the value of a compact published-runtime facade followed by the smallest pinned source read when deeper context is needed.

Framework question: define a provider-neutral semantic hydration/read contract without requiring Supabase or Mission 10 file paths.

Do not copy `dm_runtime_read()` itself. Generalize the behavior: published snapshot -> focused semantic query -> pinned supporting definition -> no redundant full-context load.

### 2. Definition / State / History separation

Mission 10 made this operationally strict, including player inventory and NPC state.

Framework question: make the single-owner rule more explicit for static definition, current mutable state, finalized history and derived/read models.

### 3. Knowledge ownership and epistemic boundaries

Campaign-Simulation already has an optional knowledge-boundary template and an external knowledge projection concept. Mission 10 validated a stronger rule: one claim, one owner; migrated claims must not remain as competing mutable copies; unknown remains unknown.

Framework question: formalize a provider-neutral knowledge contract before adding any database-specific implementation.

### 4. Engineering-to-runtime adoption boundary

Mission 10 needed a safe bridge when reviewed engine support existed on protected `main` but a generation-pinned published snapshot did not yet contain it.

Framework question: document the generic invariant first: engineering adoption may change implementation/static definitions but must preserve published campaign truth. Do not assume every adapter needs the Mission 10 two-parent merge mechanism.

### 5. Runtime facade health / proof metadata

Mission 10 showed that a read should carry enough publication metadata to prove which state was read and whether the repository mirror is confirmed.

Framework question: define optional provider-neutral snapshot identity / health metadata for generation-pinned adapters.

### 6. Player-facing save success invariant

Mission 10 exposed the false-success failure mode where a file changed but the authoritative published generation did not advance.

Framework status: publication receipts already generalize most of this. Review docs/HUMAN_README wording so humans understand that persistence success means authoritative publication, not merely "a file changed".

## Experimental work: do not promote merely for public parity

Campaign Clock, Autosave and Deferred Event Scheduler remain evidence-gated concepts. Earlier experimental PR implementations were closed without merge and are not framework authority. Any future implementation must return through fresh Mission10 gameplay evidence and a new, bounded framework review.

The earlier documentation-coverage PR was also closed without merge. Documentation workflow changes should be reconsidered from current repository truth rather than inherited from that discarded implementation.

## Public-reference rule

Campaign-Simulation should remain boring in the best possible way: campaign-neutral, blank, explainable and reusable.

Mission 10 is allowed to be gloriously specific because it is the live creature that discovers the problems. Campaign-Simulation gets only the bones that survived contact with reality.

In public wording:

> Mission 10 is the private reference implementation and live simulation environment. Campaign-Simulation is the public, reusable template derived from the systems and lessons validated there.

We are not hiding the distinction. We just love the monster, therefore strangers do not get the keys to its basement.

## Current status and next review work

The repository is public, the historical artifact library and rights boundary are present, and README/HUMAN_README explain the private-reference/public-framework relationship.

Remaining parity work is intentionally narrow:

1. Review the generic candidates above one by one against current Mission10 evidence.
2. Promote only campaign-neutral behavior that has survived real use.
3. Keep private adapters, live state, provider identifiers, canon and DM-only information out of this repository.
4. Treat public-surface hygiene and security checks as maintenance, not permission to expand framework scope.
