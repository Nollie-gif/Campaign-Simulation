# Onboarding contract

## Optional first-boot safety layer

Before gameplay onboarding, check for a verified compatible safety-installation receipt at `.campaign-simulation/safety-installation.json` in the selected runtime.

- If a compatible verified receipt exists, continue without replaying the ceremony.
- If no valid receipt exists, remain read-only and follow [First-Boot Safety Installation Protocol](safety-installation/FIRST_BOOT_PROTOCOL.md).
- The human may decline the optional layer without blocking gameplay.
- Installation consent, configuration consent, mutation consent, verification, and receipt creation are separate states.
- All future-user messages in this technical sequence are English-only. Campaign prose remains language-neutral.

## Minimum Playable Campaign Gate

The framework starts only when these three inputs exist:

1. A short campaign history.
2. At least one usable character profile.
3. A current starting situation.

This is deliberately lightweight. A user does not need a world encyclopedia before beginning play.

If the gate fails, the framework reports the missing inputs and stops before branch selection, storage configuration, scenarios, hooks, or saves are created.

## Exploration choice

After admission, the user chooses one first-class simulation mode:

- **Prequel** — explore the past from an explicit historical anchor.
- **Sequel** — explore the future from the Main Campaign's current situation or another forward anchor.

Both modes simulate forward in time.

A Prequel requires a non-empty historical anchor. A Sequel may use the Main Campaign's current starting situation as its default anchor.

## Optional campaign material

After the branch is selected, the framework displays the optional-material menu. Each option may be added now, later, or not at all:

- Supporting-character profiles
- Location profiles
- Organization profiles
- Item profiles
- Relationship records
- Timeline entries
- Knowledge-boundary records

The menu must always include **Continue without adding material**. Choosing it is valid and leads to storage configuration.

## First-boot order

1. Check the selected runtime for a compatible verified safety-installation receipt.
2. If the receipt is absent, invalid, or incompatible, offer the optional first-boot safety sequence and complete, decline, or safely stop it before gameplay onboarding.
3. Evaluate the Minimum Playable Campaign Gate.
4. If blocked, show only the missing inputs.
5. If admitted, show the Prequel / Sequel exploration menu.
6. Resolve the branch start anchor.
7. Show the optional-material menu.
8. Accept either zero or more optional selections.
9. Ask for the storage preference.
10. Persist the selected simulation branch in the local runtime.
11. Start the simulation runtime.
