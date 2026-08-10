# Campaign Simulation Framework

This repository is a reusable, campaign-neutral foundation for starting and running a simulation sequel.

It contains no campaign data, names, locations, characters, or populated examples.

## Start here

1. Complete the three minimum playable inputs described in [Onboarding](docs/ONBOARDING.md).
2. Run the admission check.
3. Review the optional campaign-material menu.
4. Either add material now or continue directly to storage setup and play.

The optional-material menu is informational and never blocks play.

## Included mechanics

- scenario lifecycle contract
- hook lifecycle contract
- quick-save and final-save contract
- first-boot storage selection with repository fallback
- blank entity, scenario, hook, save, and session templates
- Minimum Playable Campaign Gate
- optional campaign-material onboarding

## Verification

Run:

```bash
python -m unittest discover -s tests -v
```
