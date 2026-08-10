# Ownership Contract

| Record class | Authoritative owner |
| --- | --- |
| Entity card | Campaign data repository |
| Scenario record | Campaign data repository |
| Hook record | Campaign data repository |
| Session state | Campaign data repository |
| Save manifest | Campaign data repository |
| Runtime preference | Local ignored runtime directory |
| External knowledge projection | Optional derived store |

Each record has one authoritative owner. A derived copy may exist only when it identifies its source record and revision.
