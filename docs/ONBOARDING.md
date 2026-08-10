# Onboarding contract

## Minimum Playable Campaign Gate

The framework starts only when these three inputs exist:

1. A short campaign history.
2. At least one usable character profile.
3. A starting situation.

This is deliberately lightweight. A user does not need a world encyclopedia before beginning play.

If the gate fails, the framework reports the missing inputs and stops before storage configuration, scenarios, hooks, or saves are created.

## Optional campaign material

After the gate passes, the framework must display the optional-material menu. Each option may be added now, later, or not at all:

- Supporting-character profiles
- Location profiles
- Organization profiles
- Item profiles
- Relationship records
- Timeline entries
- Knowledge-boundary records

The menu must always include **Continue without adding material**. Choosing it is valid and leads to storage configuration.

## First-boot order

1. Evaluate the Minimum Playable Campaign Gate.
2. If blocked, show only the missing inputs.
3. If admitted, show the optional-material menu.
4. Accept either zero or more optional selections.
5. Ask for the storage preference.
6. Start the simulation runtime.

