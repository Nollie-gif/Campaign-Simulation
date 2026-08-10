# Ownership Contract

| Record class | Authoritative owner |
| --- | --- |
| Entity card | Campaign data repository |
| Scenario record | Campaign data repository |
| Hook record | Campaign data repository |
| Session state | Campaign data repository |
| Save manifest | Campaign data repository |
| Simulation branch configuration | Local ignored runtime directory |
| Runtime preference | Local ignored runtime directory |
| External knowledge projection | Optional derived store |
| Main-campaign admission manifest | Main Campaign data repository |
| Simulation bootstrap request | Simulation branch data repository |
| Prequel → Main convergence decision | Prequel branch data repository |

Each record has one authoritative owner. A derived copy may exist only when it identifies its source record and revision.

The Main Campaign is read-only to this framework. Prequel and Sequel branches may read it but cannot treat their runtime as a Main Campaign write permit.

A convergence decision may describe a proposed canon change, but it is not authorization to write into the Main Campaign.
