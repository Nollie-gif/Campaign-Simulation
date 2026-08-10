# Foundation Rules

1. This repository is an engine, not a campaign database.
2. Templates define fields and ownership; their values remain blank.
3. A campaign data repository owns every populated record.
4. A record may be created only from an approved blank template.
5. Missing templates are design gaps, not invitations to add an ad-hoc field.
6. Runtime configuration is local and ignored by version control.
7. An optional external knowledge layer may accelerate reads but must never be the only recoverable source of truth.
