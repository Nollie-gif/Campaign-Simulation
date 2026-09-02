# Campaign Safety Installation

This folder defines the optional first-boot safety layer for future campaign engineering work.

The safety layer exists so a DM can describe **what** they want to build while the AI plans the work and protected infrastructure controls **how** sensitive changes are executed. It is not a gameplay gate, a second source of campaign truth, or permission to mutate production.

**Scope:** this installs into a DM's own campaign runtime — a separate repository/directory from Campaign-Simulation's own source. It is not the workflow for changing this framework repository's own code, schema, docs, or CI; that is Flight Control, described in [`AGENT_HANDOFF.md`](../../AGENT_HANDOFF.md). If a request is about engineering *this* repository, use Flight Control even if it is phrased the way the [LotS Safe Build Prompt](LOTS_SAFE_BUILD_PROMPT.md) phrases a gameplay request — classify by which repository the change targets, not by the request's wording alone.

## First-boot contract

On boot, check the selected runtime for a verified installation receipt at:

```text
.campaign-simulation/safety-installation.json
```

- If a verified compatible receipt exists, do not repeat the first-boot ceremony.
- If the receipt is absent, invalid, or incompatible, remain read-only and follow [FIRST_BOOT_PROTOCOL.md](FIRST_BOOT_PROTOCOL.md).
- Do not write the receipt until installation and read-back verification have succeeded.
- A failed or interrupted installation must leave the last healthy campaign state unchanged.

## Included artifact

Future DMs receive the reusable [LotS Safe Build Prompt](LOTS_SAFE_BUILD_PROMPT.md). It can be used whenever they want to build, change, or safely remove a system.

## Boundaries

- Repository-only mode must always remain available.
- Supabase-aware protection is optional and requires successful credential-safe validation.
- Repository fallback must not be described as Supabase success.
- Git rollback does not undo database or other external writes.
- An experiment checkpoint must never overwrite gameplay progress created after the experiment began.
- Uninstall may remove only components owned by the verified installation receipt.
- Campaign history, saves, published generations, user content, credentials, and unrelated external data are outside uninstall scope.

## Language policy

All future-user installation, confirmation, love-token, receipt, error, and uninstall messages defined by this mechanism are written in English. Campaign prose remains language-neutral.
