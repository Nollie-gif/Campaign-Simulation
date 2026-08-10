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

## Operating rule

Create a campaign-specific data repository before creating any record. If a required record does not have an approved blank template, do not add the record here or in a campaign repository; add the missing template through a deliberate design change first.

## Local validation

```bash
python3 tools/validate_blank_templates.py
```
