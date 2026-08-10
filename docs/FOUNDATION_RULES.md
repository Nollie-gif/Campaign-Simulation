# Foundation Rules

1. This repository is an engine, not a campaign database.
2. Templates define fields and ownership; their values remain blank.
3. A campaign data repository owns every populated record.
4. A record may be created only from an approved blank template.
5. Missing templates are design gaps, not invitations to add an ad-hoc field.
6. Runtime configuration is local and ignored by version control.
7. An optional external knowledge layer may accelerate reads but must never be the only recoverable source of truth.
8. A simulation runtime may start only after a separate Main Campaign repository passes the Minimum Playable Campaign Gate.
9. The gate requires only history, a current starting situation, and at least one usable character profile.
10. After admission, the user explicitly chooses Prequel or Sequel.
11. Both simulation modes move forward in time; Prequel begins from a historical anchor and Sequel begins from the accepted Main Campaign state or another forward anchor within it.
12. After branch selection, the runtime displays all optional campaign-material capabilities and always permits play without them.
13. The Main Campaign is read-only to every simulation branch.
14. Every Prequel and Sequel branch has `source_type = main_campaign` and `source_policy = main_campaign_only`.
15. A Prequel checkpoint can never directly source a Sequel. Prequel save data may be used only as review input to establish or update Main Campaign; a Sequel may begin only after that Main Campaign state is explicitly accepted.
16. The admission gate is evaluated before branch persistence, storage selection, save creation, hook allocation, or scenario activation.
17. A Prequel reaching the Main Campaign must stop at the explicit convergence gate; it never merges automatically.
