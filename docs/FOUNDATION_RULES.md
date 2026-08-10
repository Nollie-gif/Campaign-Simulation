# Foundation Rules

1. This repository is an engine, not a campaign database.
2. Templates define fields and ownership; their values remain blank.
3. A campaign data repository owns every populated record.
4. A record may be created only from an approved blank template.
5. Missing templates are design gaps, not invitations to add an ad-hoc field.
6. Runtime configuration is local and ignored by version control.
7. An optional external knowledge layer may accelerate reads but must never be the only recoverable source of truth.
8. A sequel runtime may start only after a separate main-campaign repository passes the Minimum Playable Campaign Gate.
9. The gate requires only history, a starting situation, and at least one usable character profile.
10. After admission, the runtime displays all optional campaign-material capabilities and always permits play without them.
11. The admission gate is evaluated before storage selection, save creation, hook allocation, or scenario activation.
