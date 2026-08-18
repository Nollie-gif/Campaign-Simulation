> **Publication note:** Public historical snapshot converted from the working DOCX used in LinkedIn Post 2. Visible content is preserved; formatting is simplified for repository readability. This record preserves an architecture thesis and unresolved research boundaries; it is not a claim that the hypothesis has been proven.

**Control Server • Video-Game-Like Agent Interface • Context Offload •
Deterministic Actions**

*Workflow Decision Record 004 • revised architecture vision •
14-08-2026*

| **Entry ID**                  | 14-08-2026 / Mission10 + The-Test / ai-semantic-control-architecture                                                 |
|-------------------------------|----------------------------------------------------------------------------------------------------------------------|
| **Date**                      | 14-08-2026                                                                                                           |
| **Change Type**               | Durable architecture vision + unresolved research boundaries                                                         |
| **Related Repository Area**   | Mission10-Simulation-Sequel / DM Control Room, runtime, persistence, Git mirror; The-Test / agent-interface research |
| **Related Chat / Workstream** | Control Room / Control Server / agent cognitive offload / The-Test                                                   |
| **Asana Tracking Reference**  | Relevant Control Room / Control Server research workstream; live state must be checked in Asana                      |
| **Historical Relationship**   | Revises the WDR-004 concept; does not supersede WDR-001 or WDR-002                                                   |

# 1. CHANGE SUMMARY

This record preserves a durable architectural direction: Mission 10
should progressively stop presenting its operational infrastructure to
the AI agent as a collection of repositories, database tables, branches,
staging steps and validators. Instead, the system should expose a small
semantic action environment closer to a video-game control model.

The AI should choose WHAT it intends to do - for example read the
current scene, inspect an NPC, advance established time, quicksave,
final-save, verify or sync - while deterministic backend infrastructure
owns HOW that action is safely executed.

A private human-facing UI and an AI-facing tool surface should be two
clients of the same Control Server and the same backend functions. The
human may press QUICK SAVE while the AI calls quicksave(); neither
should manually reproduce the persistence choreography.

The repository remains durable implementation/technical truth, but
normal DM gameplay should trend toward boot-time contracts plus targeted
read-only repository access. Authoritative operational play should be
served primarily from SQL/runtime state and compact derived read models.
Validated synchronization back to Git remains deterministic and gated.

# 2. WHY WE CHANGED IT

- The Day 19 save incidents showed that a correct persistence
  architecture can still impose excessive operational burden when the
  agent must remember routing, project identity, staging, validation,
  publication, mirror confirmation and recovery details.

- Repeated connector/routing failures produced long recovery paths. The
  lesson is not merely to document the procedure better; it is to ask
  whether the agent should be responsible for performing that procedure
  at all.

- The DM Control Room already demonstrated the value of classifying a
  request and reading the smallest authoritative source rather than
  opening the whole repository.

- Mission 10 also produced a positive observation: after
  operational/temporal burden was reduced, the DM-agent independently
  requested an appropriate Deception check. This is evidence worth
  testing, not proof of causation.

- The core research hypothesis is that reducing operational cognitive
  load may free model capacity for semantic work: scene continuity, NPC
  persona, rules judgment, initiative, pacing and interpretation.

- The same architecture can serve a future product: human and AI clients
  can operate the same persistent simulation through semantic controls
  without duplicating backend logic.

# 3. PREVIOUS WORKFLOW

Mission 10 already separates repository truth, Supabase runtime
authority, WDR-002 persistence gates and the DM Control Room read
protocol. The Control Room classifies requests, uses the published
runtime read surface for current play, and opens pinned repository
sources only when needed.

However, the AI can still be exposed to too much operational structure.
It may need to choose low-level tools, interpret raw or semi-raw state,
retain temporary information in working context, coordinate multiple
writes, recover from failures, and decide when synchronization is
complete.

# 4. NEW WORKFLOW

Durable target direction:

- BOOT / TARGETED READS: load only contracts, routing instructions and
  exact repository truth required for the task. Repository access during
  gameplay should be read-only wherever practical.

- RUNTIME TRUTH: Supabase/Postgres remains authoritative for current
  operational campaign state and published generation identity.

- CONTEXT LAYER: deterministic, generation-pinned read models may
  transform large authoritative state into the smallest useful packet
  for the current scene/task.

- SEMANTIC ACTION LAYER: expose intent-level actions such as
  scene_context(), npc_context(), quicksave(), final_save(),
  start_day(), verify_runtime() and sync_repo().

- CONTROL SERVER: owns project IDs, ordering, staging, validation,
  publication, recovery, receipts and synchronization. The agent should
  not need to remember this choreography during normal play.

- HUMAN UI + AI TOOLS: a private web/local UI with buttons and an AI
  tool interface call the SAME backend functions.

- DETERMINISTIC SYNC: temporary/accumulated state is synchronized only
  through approved deterministic actions and the existing
  authority/verification boundaries.

**Conceptual model:**

MISSION 10 CONTROL SERVER

-> HUMAN UI: [CURRENT SCENE] [NPC] [QUICK SAVE] [FINAL SAVE] [START DAY] [VERIFY] [SYNC]

-> AI TOOLS: scene_context() npc_context() quicksave() final_save() start_day() verify_runtime() sync_repo()

-> SAME SEMANTIC FUNCTIONS

-> authoritative SQL/runtime state

-> validated deterministic publication/synchronization

-> GitHub as durable implementation/audit truth and targeted read-only gameplay source

# 5. IMPORTANT RULES FOR FUTURE CHATGPT

- Design the agent environment around semantic affordances, closer to a
  video-game UI than direct infrastructure operation.

- The AI chooses intent; deterministic infrastructure should own
  repeatable action order whenever that order can be encoded safely.

- Human UI buttons and AI tools must call the same backend
  implementation. Do not create separate save logic for humans and
  agents.

- A semantic action is not automatically success. WDR-002 authoritative
  publication/verification remains the success boundary.

- Do not turn a context packet, cache, dashboard or UI into a competing
  source of truth.

- Do not assume the optimal information representation. Raw SQL, compact
  packets, temporary scratch state, caching, batching and
  synchronization cadence remain research variables.

- Do not assume the optimal implementation language/toolchain. Python,
  TypeScript/Node, Go or another environment must not be selected merely
  by convention when AI operability is a design objective.

- The-Test should be used where practical to measure which environment
  allows an AI agent to inspect, reason, accumulate temporary state,
  mutate safely, recover and synchronize with the lowest operational
  burden while preserving correctness.

- Preserve hidden-information boundaries. Compactness must never leak
  backstage Hooks, dice/meta state or knowledge unavailable to the
  acting NPC/agent role.

- Engineering/debug mode may expose lower-level controls, but normal
  gameplay should not require the DM-agent to operate like a
  database/repository engineer.

# 6. REPOSITORY IMPACT

No production implementation is authorized solely by this WDR. Candidate
future areas include:

- Mission10-Simulation-Sequel: DM Control Room, runtime contract,
  persistence gateway clients, semantic tool definitions and targeted
  read-only repository policy.

- Supabase/Postgres: authoritative runtime state plus read-only
  views/RPCs/materialized read models/context-packet builders.

- Control Server: deterministic composite actions, failure-stage
  reporting, receipts, recovery and sync orchestration.

- Private Human UI: buttons/cards/status indicators over the same
  Control Server actions used by AI tools.

- The-Test: controlled experiments comparing low-level orchestration,
  routed interfaces, composite actions, information representations,
  temporary-state strategies and implementation environments.

# 7. DATA / ARCHITECTURE IMPACT

The architecture separates five concerns:

- Truth plane - authoritative runtime state plus durable repository
  implementation truth.

- Context plane - compact derived representations of authoritative
  state.

- Temporary-state plane - bounded scratch/accumulation mechanisms whose
  ideal representation and lifetime remain under research.

- Execution plane - deterministic semantic actions and synchronization
  procedures.

- Interaction plane - human UI and AI tools presenting those same
  actions in forms appropriate to each client.

The central research problem is not only 'which backend is best'. It is:
when information volume becomes large, what should the AI see, what
should it temporarily retain or accumulate, when should that state be
written, and how should deterministic actions synchronize it without
forcing the model to carry infrastructure in working context?

# 8. SAFETY / FAILURE MODES

- Authority inversion: derived/UI state is treated as stronger than
  authoritative runtime or repository implementation truth.

- Parallel implementation drift: human and AI clients call different
  logic for the same semantic action.

- Over-compression: a context packet omits a fact necessary for correct
  behavior.

- Context inflation: packets become another giant memory dump.

- Stale temporary state: scratch/accumulated information survives beyond
  the generation or task for which it was valid.

- Unsafe synchronization: temporary state is promoted without
  deterministic validation or authoritative receipt.

- Backstage leakage: compact packets expose hidden information.

- Interface explosion: too many semantic controls recreate low-level
  routing burden.

- Composite-action opacity: a high-level action fails without reporting
  the exact internal stage.

- Observability loss: hiding complexity from the agent also hides
  diagnostic evidence from engineers.

- Research bias: the preferred architecture or language is encoded into
  benchmarks so the experiment merely proves its own assumptions.

- Schema/model breakage: refactoring JSON shapes or derived views breaks
  consumers because contracts, validators, migrations or compatibility
  adapters were not updated together.

# 9. ASANA CONTROL REFERENCE

Live implementation, research, experiments, regressions,
language/toolchain evaluation, UI prototypes and promotion decisions
belong in the relevant concise Asana workstream. This WDR preserves the
durable direction only. If the relevant Asana control says No,
implementation or promotion waits.

# 10. FUTURE NOTES

- Open research question: what representation best helps an AI operate
  under high information volume - raw structured state, materialized
  context packets, graph-like relations, UI-like cards, typed tools, or
  combinations of these?

- Open research question: should temporary knowledge be held in model
  context, explicit scratch state, short-lived SQL/cache records,
  batched transaction state, or another bounded mechanism?

- Open research question: what synchronization cadence is best -
  continuous mutation, explicit checkpoints, batched writes, semantic
  save actions, or hybrids?

- Open research question: which implementation language/toolchain gives
  the best AI operability, reliability, inspectability, testability and
  recovery behavior? Language remains intentionally undecided pending
  evidence.

- The-Test should freeze the task/model where possible and vary the
  agent-facing environment. Metrics should include correctness,
  completion time, tool calls, rereads, context volume,
  routing/permission errors, recovery steps/time, human interventions,
  temporary-state loss, stale-state errors, false success and
  final-state correctness.

- Positive behavior should also be measured where defensible:
  appropriate autonomous checks, NPC consistency, temporal continuity,
  useful initiative and reduced need for human prompting.

- The desired end state resembles a video-game control surface for
  agents: meaningful actions and compact state, with infrastructure
  hidden below deterministic boundaries.

- The repository need not be rewritten from zero merely because the
  agent-facing model changes. Existing JSON/contracts can often be
  evolved behind adapters/migrations/validators while preserving stable
  identities and higher-level architecture, provided dependencies and
  invariants are verified.

# 11. VERIFICATION

This record preserves an architecture thesis and explicitly unresolved
research variables. It does not claim that a particular UI, context
model, temporary-state strategy, synchronization cadence or programming
language has won.

- Use The-Test controlled experiments before major production promotion
  where practical.

- Compare interfaces using common tasks, telemetry, verifier and success
  criteria.

- Freeze experiment/runner/model/environment revisions sufficiently for
  reproducibility.

- Verify generation pinning, stale-state handling, hidden-information
  boundaries and final authoritative state.

- Test composite-action failure stages and recovery, not only happy
  paths.

- Verify human UI and AI tools invoke the same backend implementation.

- Use repository diff, validators, unit/integration tests, CI and
  isolated canary before durable production promotion.

- When JSON/schema contracts change, verify all known readers/writers,
  migrations/adapters, validators and rollback/compatibility behavior.

**Lifecycle rule: Asana controls whether work proceeds. Repository
proves what exists. WDR preserves the durable architectural direction.
The-Test supplies evidence. No interface, cache, context packet,
temporary store or UI silently becomes authoritative truth.**
