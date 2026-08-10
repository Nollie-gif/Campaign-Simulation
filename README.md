# Campaign Simulation Framework

> **New here?** Start with the plain-language [Human User Guide](HUMAN_README.md) to understand the purpose of the framework, canon protection, and the sequel-sandbox workflow before using the technical setup below.

This repository is a reusable, campaign-neutral foundation for starting and running a simulation sequel.

It contains no campaign data, names, locations, characters, or populated examples.

## Start here

1. Complete the three minimum playable inputs described in [Onboarding](docs/ONBOARDING.md).
2. Install the framework from its repository checkout:

   ```bash
   python -m pip install -e .
   ```

3. Start the guided setup:

   ```bash
   campaign-simulation start --main-campaign /path/to/main-campaign --runtime /path/to/sequel-runtime
   ```

   The equivalent module command is `python -m campaign_simulation start ...`.
4. Review the optional campaign-material menu.
5. Either add material now or continue directly to storage setup and play.

The optional-material menu is informational and never blocks play.

## Language policy

The framework's technical layer is deliberately written in English: source code,
command names, JSON keys, schema identifiers, and lifecycle values are stable
machine-facing contracts.

Campaign prose is language-neutral. A main campaign and its sequel may be written
entirely in Greek, English, or any other language without changing a technical
file, ID, schema, or runtime rule. The engine preserves campaign text as supplied;
it does not require a translation or a `content_language` field before play can
begin.

## Included mechanics

- scenario lifecycle contract
- hook lifecycle contract
- quick-save and final-save contract
- first-boot storage selection with repository fallback
- command-line guided startup (`campaign-simulation start`)
- blank entity, scenario, hook, save, and session templates
- Minimum Playable Campaign Gate
- optional campaign-material onboarding
- path-safe main-campaign references
- persisted hook and scenario identifier allocation
- atomic full-checkpoint persistence
- credential-safe Supabase validation and repository fallback

## Verification

Run:

```bash
python -m unittest discover -s tests -v
```
