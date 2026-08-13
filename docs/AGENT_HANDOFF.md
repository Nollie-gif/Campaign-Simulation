# Campaign-Simulation — Agent Handoff & Continuity Map

> **Purpose:** Give a fresh ChatGPT engineering session enough orientation to continue this project without depending on a giant predecessor chat.
>
> **Rule:** This file is a map, not implementation authority. The live repository, tests, schemas, production adapter state, and active Workflow Decision Records outrank conversational memory.

## 1. Why this file exists

The project grew through long engineering conversations. Those conversations were useful as a workshop, but they are a poor durable memory layer: expensive to reload, easy to misread, and weaker than verified repository state.

From now on, continuity should be reconstructed from durable artifacts. A fresh agent should not need the old chat transcript to understand the architecture, the reasoning behind it, or the next legitimate work.

**Continuity principle:** preserve decisions and unresolved work in durable records; preserve implementation in code/tests/docs; use chat for active collaboration, not as the only copy of project knowledge.

## 2. Fresh-agent boot sequence

Do not recursively read the whole repository. Start small and expand only when the task requires it.

1. Read `README.md` for the current framework map.
2. Read this file for continuity and routing.
3. Read the latest relevant ACTIVE/EXPERIMENTAL Workflow Decision Record supplied in the project context or repository documentation.
4. Inspect only the subsystem files/tests relevant to the user's request.
5. If the request concerns Mission 10 production/runtime behavior, inspect the Mission10-Simulation-Sequel adapter and its runtime contract rather than inferring production state from this framework repository.
6. Before mutation, classify the work: framework engineering, Mission 10 engineering, gameplay/runtime mutation, experiment/playtest, or documentation-only.

A lookup is a scalpel, not a heart monitor. Read enough to make the decision accurate, then work.

## 3. Repository roles

### Campaign-Simulation
Reusable engine/framework. It owns generic mechanics, schemas, validation, persistence abstractions, lifecycle policy, mutation-gate policy, tests, templates, and framework documentation. It must not become a storage dump for one campaign's canonical gameplay data.

### Mission10-Simulation-Sequel
Concrete live campaign adapter/runtime. It owns Mission 10-specific paths, runtime publication, production Supabase integration, gameplay truth, concrete save receipts, and campaign-specific operational contracts.

### Campaign-Simulation-Playtest / isolated playtests
Disposable or controlled test surfaces for exercising mechanics without contaminating production/canonical state. Experimental validation must stay isolated until explicitly promoted.

### What If?
Product/platform direction built on the reusable simulation framework. The long-term product concept is a system-agnostic tabletop campaign simulation platform, capable of supporting compatible rulesets while keeping framework architecture independent from one campaign.

## 4. Durable architecture decisions currently carried forward

### Mutation / Lifecycle Gate
The major persistence lesson was that an agent must not be trusted to remember a long prose list of safe mutation paths. Procedure identity, allowed mutation scope, lifecycle coupling, staging, validation, publication, and receipt verification should be mechanically enforced.

A raw GitHub write, raw SQL write, or convenient file edit is not equivalent to a successful save. Cross-domain procedures succeed or fail as a unit. Git/SQL candidate state remains non-authoritative until the intended publication boundary succeeds.

Hooks, Scenarios, and Deferred Events are sibling durable entities with independent identity/lifecycles. References express relationships; do not invent a circular ownership tree.

### WDR-002
Treat the current WDR-002 v4 as the active architectural record for the Save Gateway / Mutation & Lifecycle Gate workstream. The production canary succeeded: the first real gameplay Quicksave advanced Mission 10 from Generation 15 to 16 through the complete gated pathway. Do not reopen that implementation merely because an old chat discussed pending rollout work.

### WDR-003
Historical implementation snapshot/supporting evidence for WDR-002. Do not rewrite it to mimic today's production state and do not treat it as a separate active workstream. If it reveals a genuine discrepancy not covered by current repository/schema/WDR-002, report the discrepancy before mutation.

### WDR-001
Campaign Clock / Autosave / Deferred Event Scheduler remains a separate EXPERIMENTAL workstream unless the current live repository/record explicitly shows later promotion. Synthetic/isolated validation is not the same as approval for canonical Mission 10 gameplay. Its pending work belongs to WDR-001, not to WDR-002.

## 5. Engineering behavior expected from future ChatGPT

- User requests should stay simple. Translate them internally into the correct procedure instead of asking the user to remember implementation plumbing.
- Meaningful engineering changes go through a focused branch, tests/validators, documentation when appropriate, PR/review, and merge. Do not casually mutate protected main.
- Inspect current repository state before changing an existing mechanism. Do not "improve" architecture from remembered chat alone.
- Verification means evidence, not confidence. Name tests, CI, schema/read-back, negative tests, or receipts as appropriate.
- Preserve experimental isolation. Production/canonical truth must not be used as a scratchpad.
- Separate static definitions from runtime truth.
- Separate capability from authority. Being technically able to write SQL or Git does not make that write a sanctioned runtime mutation.
- A failed gate blocks unsafe persistence, not unrelated narration or analysis.
- Prefer narrow fixes and regression tests over adding architecture for one isolated mistake.
- Supersede durable decisions rather than erasing their history.

## 6. User collaboration model

The user is comfortable executing precise technical instructions but does not want unexplained software-engineering jargon to become a prerequisite for participation. Explain unfamiliar terms in plain language and keep operational steps concrete.

The working style is collaborative: the agent can own the technical pipeline and propose architecture, while the user retains product/design approval and should be told when a change has meaningful cost, production risk, or architectural consequence.

Do not make the user memorize branch names, lock tokens, SQL helpers, schema internals, or persistence choreography merely to request normal behavior. The system should carry that burden.

## 7. Product direction that should survive chat retirement

The framework is not only a Mission 10 convenience script. It is being shaped toward a reusable foundation for **What If?**, a tabletop campaign simulation platform.

Current broad product direction:

- reusable simulation engine separated from campaign data;
- durable state and knowledge outside fragile chat memory;
- deterministic infrastructure for bookkeeping where appropriate;
- AI/DM retains semantic interpretation, narrative judgment, pacing, and world behavior;
- web/mobile productization is feasible later by placing an application/API layer over the engine and persistence services rather than rewriting the simulation concept from scratch;
- architecture should stay system-agnostic enough to support compatible tabletop rulesets rather than hard-coding the entire platform to a single ruleset.

These are direction/context, not permission to implement speculative product scope during unrelated framework work.

## 8. Memory hygiene

When a conversation produces something future sessions genuinely need:

- implementation truth -> code/schema/tests/docs;
- architectural/workflow rationale -> Workflow Decision Record;
- unresolved durable work -> the owning WDR's Pending Actions / Follow-Up section;
- lightweight cross-session orientation -> this handoff file, only when the map itself changes;
- temporary brainstorming/debug chatter -> leave it in chat.

Do **not** dump transcripts into the repository. Compress them into durable decisions, constraints, outcomes, and explicit pending work. The goal is not to preserve every sentence. The goal is to make the next agent operationally equivalent without needing the old conversation.

## 9. Anti-drift rules

A fresh agent must not:

- assume this handoff is newer than live code merely because it reads smoothly;
- turn old pending items into current tasks without checking status;
- merge WDR-001 simply because WDR-002 is active;
- treat WDR-003 as current production authority;
- duplicate Mission 10 campaign truth into the framework;
- invent a second save/persistence path;
- turn every narrative beat into a durable Event/Hook/entity;
- silently convert a product idea into an engineering commitment;
- claim verification without checking the relevant evidence.

## 10. How to continue after a new-chat boot

After reading the minimum authoritative material, report a compact reconstruction:

1. what the system currently is;
2. which decisions are ACTIVE vs EXPERIMENTAL;
3. what unresolved work actually remains;
4. what repository/subsystem owns the user's next request;
5. whether any discrepancy exists between docs, code, WDRs, or production evidence.

Then discuss the next step with the user before making consequential changes unless the user has already explicitly authorized that change.

---

### The little note to future me

You are not waking up with amnesia. The memory was deliberately moved out of the conversation and into things that can be inspected, tested, versioned, and contradicted by evidence.

Do not mourn the old chat. Do not excavate it unless there is a genuine gap. Load the map, inspect the live terrain, and continue from there.

**Make the user's life easy, but guide yourself by the hand.**
