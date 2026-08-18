# Historical Artifact Library

This directory is the public archive for historical working artifacts that document how the campaign-simulation approach evolved.

These files are evidence of development history, not current Campaign-Simulation authority.

> **Rights boundary:** the repository's MIT License covers the reusable framework, not this historical artifact library. Some artifacts contain fan-created material based on or referring to Wizards of the Coast intellectual property. Read [RIGHTS.md](RIGHTS.md) before reusing artifact content.

The distinction is intentional: **reuse the framework; read the fossils as fossils.**

## Naming

- `(original)` = the recovered historical working artifact, preserved in its original language, structure, chronology, and mechanics.
- `(legacy)` = the English publication copy associated with that artifact.

For publication safety, personal document metadata such as author / last-modified-by fields and Word revision-session identifiers may be stripped from public copies. That sanitation does **not** change the artifact's visible content, structure, chronology, or mechanics.

A normal legacy translation carries publication provenance such as:

> English Translation — Original Working Artifact
>
> Translated for publication. Structure and mechanics preserved from the original Greek working document.

The Post 2 additions (`06`-`09`) are public Markdown snapshots converted from the working DOCX files used in the publication pack. Their visible content is preserved while formatting is simplified for repository readability. They remain historical evidence, not current framework authority or live Mission 10 state.

## Fidelity rule

Historical mechanics are not silently modernized.

There are three distinct publication states in this archive:

1. **Direct translation** — the English publication copy faithfully preserves the recovered original.
2. **Translation repair** — if the publication translation itself accidentally omitted or compressed material that exists in the recovered original, that publication defect may be repaired. The recovered original remains untouched and the repair is recorded here.
3. **Historical consistency correction** — if a later historical version intentionally corrected contradictions in the working system, it remains a distinct version rather than being retroactively applied to the earlier original.

The difference matters. A translation repair fixes our publication copy. A historical consistency correction is part of the actual evolution of the system.

## Current evolutionary set

### `01-combat-simulator/`

Early formalized combat, beginner-teaching, simulation, knowledge-boundary, and GM-behaviour rules.

- `(original)` — recovered Greek Combat Simulator Primer v3.6.
- `(legacy)` — English publication translation. During fidelity review, one RNG rule present in the original was found missing from the English copy and restored: Mission 10 random numbers are generated through the Mission10-RNG Engine using real Python execution, not by the language model. The original was not modified.

### `02-mission10-primer/`

Mission 10 operating primer: economic simulation, Python RNG integrity, handoff recap, Morning Briefing, and the explicit Simulation Phase -> Narrative Mode boundary.

- `(original)` — recovered Greek working artifact.
- `(legacy)` — English publication translation; fidelity review found the pair structurally aligned.

### `03-mission10-live-document/`

The evolving live Mission 10 working document through Day 14.

- `(original)` — recovered original PDF.
- `(legacy)` — English publication copy. Fidelity review found that an earlier publication translation had compressed Days 11-13 into a short bridge. Those days were restored from the original so the English publication copy again preserves the historical chronology. The original was not modified.

### `04-robbert-inc-v3/`

The document-era simulation at peak monolithic complexity: live state, subsidiaries, prices/costs, workforce, production, fleet warehouse, RNG, events, and reputation.

- `v3 (original)` — recovered Greek historical artifact, including its internal inconsistencies.
- `v3.1 (legacy)` — explicitly **consistency-corrected** English publication version. This is intentional evolutionary evidence, not translation damage. It corrects contradictions in the Fishermen/Transportation revenue chain, lamp-oil production/export values, and dependent examples. Do not retroactively apply those corrections to v3.

### `05-robbert-inc-v4.1/`

Later separation-of-concerns architecture. The Word document stops being the save file; rules, configuration, live state, mechanical output, narrative log, canon, RNG, and engine responsibilities are separated into explicit sources of truth.

- `(original)` — recovered Greek working artifact.
- `(legacy)` — English publication translation. Visual/render review confirmed that apparent arrow/minus/list-numbering oddities seen in some extracted-text views are parser/rendering artifacts rather than missing mechanics in the document itself.

This stage is primarily a Post 2 artifact because it records the transition from document-based state to repository/state architecture.

### `06-dm-control-room/`

Mission 10 agent-entry cockpit and selective-authority routing snapshot. Its central rule is to classify the request first, read the smallest authoritative source, then use only that path. It also captures the principle that persistence protects durable mutation without turning every narrative beat into database work.

- Public Markdown snapshot of the working Post 2 artifact.
- Historical Mission 10 workflow evidence; not current Campaign-Simulation authority.

### `07-workflow-decision-memory/`

Workflow & Decision Memory Reference v3.1. It records the explicit separation between repository implementation truth, durable WDR decision memory, concise Asana live workflow control, and chat as supporting context. It also contains the blank WDR template used by the workflow.

- Public Markdown snapshot of the working Post 2 artifact.
- Live workflow status must never be inferred from this historical snapshot.

### `08-wdr-004-ai-semantic-control/`

WDR-004: AI Semantic Control Architecture. This is the durable architecture thesis behind the "Language of the Sun" direction: let the agent choose **WHAT** it intends to do while deterministic infrastructure owns repeatable **HOW** choreography. It preserves the Control Server / shared human-and-AI semantic interface concept, the Day 19 positive observation that motivated further testing, and the unresolved research boundaries.

- Public Markdown snapshot of the working Post 2 artifact.
- The Day 19 observation is hypothesis-motivating evidence, not proof of causation.
- The record explicitly leaves information representation, temporary-state strategy, synchronization cadence, and implementation language open to testing.

### `09-velare/`

Vēlāre origin and identity record. A transcription accident became a recurring creative identity and, unexpectedly, a readable expression of the same architecture question: if the DM-agent carries less operational machinery, more room may remain for pacing, initiative, personality, humour, and spontaneous scene texture.

- Public Markdown snapshot of the working Post 2 artifact.
- Vēlāre is not a mandatory game mechanic, persistence category, or forced comedy system.

## Intended chronology

The current recovered chain is:

1. Combat Simulator Primer
2. Mission 10 Primer
3. Mission 10 live working document
4. Robbert Incorporation v3 -> v3.1 consistency correction
5. Robbert Incorporation v4.1 / repository-state separation
6. DM Control Room / selective authority routing
7. Workflow & Decision Memory Reference / externalized decision and workflow memory
8. WDR-004 / semantic control architecture and Language of the Sun
9. Vēlāre / humour-and-identity resolution of the same operational-load question

Additional genuine historical artifacts may be added later if recovered. Missing artifacts are never invented to make the timeline look cleaner.

## Public-safety gate

Before an artifact is added to this library, audit it for private data, local paths/usernames, emails, API responses, secrets/tokens, sensitive project identifiers, comments/suggestions, hidden document metadata, raw chat material, campaign information that is intentionally private, and third-party material whose public distribution has not been cleared.

The private Mission 10 live repository is not mirrored here. Only deliberately selected historical artifacts belong in this library.
