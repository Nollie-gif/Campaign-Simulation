# Main Campaign Admission Gate

A sequel simulation can start only from a separate main-campaign data repository. The engine never guesses missing campaign information and never imports it into this repository.

## Required source file

The main campaign repository must contain a populated `main-campaign-manifest.json`, created from `templates/main-campaign-manifest.template.json`.

The manifest must contain only:

1. a short campaign history;
2. a starting situation;
3. one or more references to usable character profiles.

Each referenced character profile needs a character name and short character summary. This is the **Minimum Playable Campaign Gate**: enough information to begin play without demanding a world encyclopedia.

Supporting characters, locations, organizations, items, relationships, timeline records, and knowledge boundaries are all optional. After admission, the engine must show the user these capabilities and explicitly offer **Continue without adding material**.

## Enforced startup order

1. Validate the main-campaign manifest.
2. Only if admitted, display the optional-material menu.
3. Accept an optional selection, including no additional material.
4. Only then select or load the storage mode.
5. Only then create a sequel bootstrap request, scenario state, hooks, or saves.

On an admission failure the runtime creates no configuration, asks no Supabase question, and writes no sequel record. The error names the missing requirement so a user can finish the main campaign setup first.

## Boundary

The sequel may read a declared main-campaign revision as its source. It never writes back to the main campaign. Any later canon promotion is a deliberate user-controlled operation outside this engine.

This is enforced for runtime paths: a sequel runtime configuration, checkpoint,
or other write target may not be inside the selected Main Campaign directory or
in a parent directory that contains it. The engine therefore refuses both
`--runtime /path/to/main-campaign` and broad choices such as
`--runtime /path/to` when `/path/to/main-campaign` is the selected source.

Character-profile references must be relative paths that resolve inside the chosen
main-campaign directory. Absolute paths, `../` escapes, and symlinks that resolve
outside that directory are rejected. A sequel therefore cannot accidentally read
unrelated local files while validating its campaign foundation.
