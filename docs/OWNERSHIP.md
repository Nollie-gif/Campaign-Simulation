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
| Main-campaign admission manifest | Main campaign data repository |
| Sequel bootstrap request | Sequel mission data repository |
| Prequel → Main convergence decision | Prequel/sequel mission data repository |

Each record has one authoritative owner. A derived copy may exist only when it identifies its source record and revision.

The Main Campaign is read-only to this framework. A convergence decision may
describe a proposed canon change, but it is not a Main Campaign write permit.
