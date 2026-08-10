# Main Campaign Admission Gate

A simulation branch can start only from a separate Main Campaign data repository. The engine never guesses missing campaign information and never imports it into this framework repository.

## Required source file

The Main Campaign repository must contain a populated `main-campaign-manifest.json`, created from `templates/main-campaign-manifest.template.json`.

The manifest must contain only:

1. a short campaign history;
2. a current starting situation;
3. one or more references to usable character profiles.

Each referenced character profile needs a character name and short character summary. This is the **Minimum Playable Campaign Gate**: enough information to begin play without demanding a world encyclopedia.

Supporting characters, locations, organizations, items, relationships, timeline records, and knowledge boundaries are all optional.

## Enforced startup order

1. Validate the Main Campaign manifest.
2. Only if admitted, ask whether the user wants to explore a Prequel or Sequel.
3. Resolve the branch anchor.
4. Display the optional-material menu.
5. Accept an optional selection, including no additional material.
6. Only then select or load the storage mode.
7. Only then persist branch configuration or create scenario state, hooks, or saves.

On admission failure the runtime creates no configuration, asks no branch or Supabase question, and writes no simulation record. The error names the missing requirement so the user can finish the Main Campaign setup first.

## Boundary

Every simulation branch may read the declared Main Campaign as its source. It never writes back to the Main Campaign automatically. Any later canon promotion is a deliberate user-controlled operation outside the normal simulation flow.

This is enforced for runtime paths: a simulation runtime configuration, checkpoint, or other write target may not be inside the selected Main Campaign directory or in a parent directory that contains it. The engine therefore refuses both `--runtime /path/to/main-campaign` and broad choices such as `--runtime /path/to` when `/path/to/main-campaign` is the selected source.

Character-profile references must be relative paths that resolve inside the chosen Main Campaign directory. Absolute paths, `../` escapes, and symlinks that resolve outside that directory are rejected. A simulation therefore cannot accidentally read unrelated local files while validating its campaign foundation.
