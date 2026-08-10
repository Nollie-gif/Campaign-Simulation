# Main Campaign Admission Gate

A sequel simulation can start only from a separate, populated main-campaign data repository. The engine never guesses missing campaign information and never imports it into this repository.

## Required source file

The main campaign repository must contain a populated `main-campaign-manifest.json`, created from `templates/main-campaign-manifest.template.json`.

The manifest must:

1. declare itself as `main-campaign`;
2. identify the source campaign and immutable source revision;
3. set `readiness.status` to `ready`;
4. provide evidence record identifiers for every required coverage area.

The coverage areas are campaign context, world state, participants, timeline, knowledge boundaries, and open threads. `not_applicable` is allowed only when it is explicit and still points to a record explaining that decision. This prevents silent gaps.

## Enforced startup order

1. Validate the main-campaign manifest.
2. Only if admitted, select or load the storage mode.
3. Only then create a sequel bootstrap request, scenario state, hooks, or saves.

On an admission failure the runtime creates no configuration, asks no Supabase question, and writes no sequel record. The error names the missing requirement so a user can finish the main campaign setup first.

## Boundary

The sequel may read a declared main-campaign revision as its source. It never writes back to the main campaign. Any later canon promotion is a deliberate user-controlled operation outside this engine.
