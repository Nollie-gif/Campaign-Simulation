# Campaign-Simulation Installation & Development Guide

## Purpose

This file is the human-readable operating guide for installing, modifying, validating, and integrating changes in this repository.

The user should not be expected to remember or manually enforce the Git workflow below. Any AI agent or developer modifying this repository must apply it automatically.

## Protected Main Rule

`main` is the canonical integration branch. Do not write, commit, or push changes directly to `main`.

For every code, test, workflow, schema, template, or documentation change:

1. Start from the latest `main`.
2. Create a focused feature, fix, hardening, test, or documentation branch.
3. Make only the scoped change on that branch.
4. Run the relevant local validation when execution is available.
5. Open a pull request targeting `main`.
6. Let the existing GitHub Actions workflow run.
7. Do not weaken, remove, or bypass tests merely to make CI pass.
8. If CI fails, stop and diagnose the actual failure on the branch.
9. Merge only after the proposed change has been reviewed and the required CI jobs are green.

For the current Campaign-Simulation framework workflow, both Ubuntu and Windows jobs on Python 3.11 must pass before merge.

Branches and pull requests are safety mechanisms. They keep `main` usable while implementation and verification happen elsewhere.

## Review-Only Requests

If the user explicitly asks for review-only work, proposed diffs only, or no repository mutation, do not create, update, commit, push, or merge repository changes until the user later authorizes implementation.

## Agent Responsibility

The technical workflow is the agent's responsibility, not the user's. When the user says to fix, build, install, harden, or update something, the agent should choose and execute the safe branch/PR/test workflow automatically unless the user has explicitly requested review-only work.
