# Campaign Simulation

Reusable, campaign-neutral simulation foundation.

This repository contains mechanics, contracts, blank templates, and validation only. It must never contain a populated campaign record, a real person, a real place, a real organization, or a named scenario.

## What is included

- scenario lifecycle contract
- hook lifecycle contract
- quick-save and final-save contract
- first-boot storage selection with repository fallback
- blank entity-card templates
- blank-template validator
- main-campaign admission gate before any sequel runtime starts

## Operating rule

Create a campaign-specific data repository before creating any record. If a required record does not have an approved blank template, do not add the record here or in a campaign repository; add the missing template through a deliberate design change first.

## Required start order

A sequel simulation does **not** start from an empty repository. It first requires a separate main-campaign data repository with a valid, populated `main-campaign-manifest.json`. The runtime validates that source before it asks about storage, initializes Supabase, creates a scenario, allocates a hook, or saves anything.

See [Main Campaign Admission Gate](docs/MAIN_CAMPAIGN_ADMISSION.md).

## Local validation

```bash
python3 tools/validate_blank_templates.py
```
