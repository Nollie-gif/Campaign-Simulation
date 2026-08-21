# Engineering Documentation Coverage Policy

## Purpose

Meaningful software changes must carry their repository documentation with them. The user must not be expected to remember which README, contract, lifecycle document, schema note, or engineering guide needs updating.

The live repository is the source of truth for current mechanics and implementation behavior. External/project Workflow Decision Records preserve rationale, architectural boundaries, status, and verification evidence; they must not become a second copy of live mechanics.

## Required workflow

For every change that can alter runtime behavior, architecture, persistence, schemas, lifecycle rules, validation, compatibility, CI, or developer workflow:

1. Make the implementation change on a focused branch.
2. Update the relevant repository documentation in the same branch.
3. Update or add tests/validation appropriate to the change.
4. Let the Documentation Coverage Gate inspect the pull request.
5. Create/update an external Workflow Decision Record only when the change represents a durable workflow or architecture decision.
6. Before writing that external record, perform a duplication audit against the live branch so mechanics remain in GitHub and the record stays lean.

## Documentation authority

Detailed current behavior belongs in repository-owned sources such as:

- `README.md` / `HUMAN_README.md` for framework-facing behavior;
- `docs/` for subsystem contracts and lifecycle documentation;
- schemas for persisted data contracts;
- source code for executable behavior;
- tests for executable verification.

A Workflow Decision Record may reference those files, but should not restate constants, algorithms, schema fields, trigger lists, lifecycle mechanics, or other implementation details that can drift.

## Documentation Coverage Gate

The CI gate evaluates pull-request diffs. When a change touches implementation-sensitive paths, the pull request must satisfy one of these conditions:

- at least one repository documentation source is changed in the same pull request; or
- the pull request body contains the exact marker `Documentation impact: none` and explains why the implementation change does not alter user/runtime/architectural behavior.

The second path is an explicit exemption, not a shortcut. It is appropriate for internal refactors or similarly behavior-neutral work where changing docs would create noise rather than truth.

## Agent responsibility

The agent/developer performing the software change is responsible for identifying and updating the correct repository documentation. The user is not the documentation reminder system.

When in doubt, inspect the repository before editing, prefer the narrowest authoritative document, and avoid duplicating the same live rule across multiple docs.
