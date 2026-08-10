# Campaign-Simulation Repository Workflow

## Protected Main Rule

`main` is the canonical integration branch. Do not write, commit, or push changes directly to `main`.

For every code, test, workflow, schema, template, or documentation change:

1. Start from the latest `main`.
2. Create a focused feature/fix/hardening branch.
3. Make only the scoped change on that branch.
4. Run the relevant local validation when execution is available.
5. Open a pull request targeting `main`.
6. Let the existing GitHub Actions workflow run.
7. Do not weaken or remove tests merely to make CI pass.
8. If CI fails, stop, diagnose the actual failure, and fix it on the branch.
9. Merge only after the required CI jobs are green and the proposed change has been reviewed.

For the current framework test workflow, both Ubuntu and Windows jobs must pass before merge.

The branch and pull request are safety mechanisms, not optional ceremony. They keep `main` usable while implementation and verification happen elsewhere.

## Agent Operating Rule

The user should not be expected to remember or manually enforce this Git workflow. Agents working in this repository must apply it automatically whenever they are asked to modify the repository.

If the user explicitly asks for review-only, proposed diffs only, or no repository mutation, do not create, update, merge, or push anything until the user later authorizes implementation.
