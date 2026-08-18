> **Publication note:** Public historical snapshot converted from the working DOCX used in LinkedIn Post 2. Visible content is preserved; formatting is simplified for repository readability. This is durable workflow-history evidence, not current live workflow state.

**MISSION 10 / WHAT IF?**

Workflow & Decision Memory Reference

**v3.1 • 13-08-2026**

WDR = durable memory • Asana = concise live workflow control •
Repository = implementation truth

# 1. Purpose

- This master reference defines how durable Workflow Decision Records
  (WDRs) and the existing Asana workflow structure cooperate.

- WDRs preserve stable decisions, rationale, architecture, failure
  boundaries, and verification evidence. They are not live task/status
  trackers.

- Asana remains concise and uses the existing working structure. Do not
  expand it into a duplicate documentation system.

# 2. Authority model

- GitHub / repository: authoritative for current implementation, code,
  tests, configuration, and repository-facing documentation.

- WDR: authoritative for durable engineering rationale and verified
  decisions at publication time.

- Asana: authoritative for live workflow control, follow-up, review
  gates, incidents, regressions, and work waiting for approval.

- Chat history: supporting context only.

# 3. Asana control rule

- Asana is a control layer, not a second WDR library. Keep entries
  brief, actionable, and inside the existing project/section/task
  structure that already works.

- Any Asana item or gate labelled “No” is blocked / not approved. It
  must wait. Do not execute, promote, rewrite, or treat it as accepted
  until that control changes.

- Before editing a WDR-owned area, check the relevant Asana control
  state. A WDR may describe a previously verified decision while Asana
  correctly shows that new follow-up is waiting or under review.

- Do not duplicate full WDR prose, repository state, or long historical
  narratives into Asana. Store only enough context to manage the work
  safely.

# 4. When work belongs in Asana

- Put active edit requests, investigations, incidents, regressions,
  trial-and-error work, verification work, promotion decisions, and
  cleanup into the relevant Asana workflow.

- If an existing WDR section needs revision, the revision work first
  enters Asana. The WDR changes only after the work is allowed by the
  Asana control state and the durable result is known.

- Experimental or unresolved engineering state remains in Asana rather
  than making the canonical WDR oscillate with every attempt.

# 5. When a WDR changes

- Create or revise a WDR only when a durable engineering decision has
  stabilized enough to preserve for future agents.

- Preserve historical records. When a later decision replaces an earlier
  one, record the historical relationship rather than deleting history.

- Do not infer live status from WDR wording. Check Asana for current
  workflow control.

# 6. Standard sequence

- 1\. Inspect repository truth, relevant WDR, and relevant Asana control
  state.

- 2\. If Asana says “No”, stop and wait.

- 3\. If work is allowed, use the existing Asana structure to track the
  active work concisely.

- 4\. Implement on the appropriate engineering branch/path; avoid unsafe
  direct production/main mutation.

- 5\. Verify with tests, CI, validators, audits, recovery/fault checks,
  or canaries as relevant.

- 6\. When the result becomes durable, update repository documentation
  and the WDR as needed.

- 7\. Keep remaining live follow-up in Asana rather than copying it into
  the WDR.

# 7. Rules for future ChatGPT

- Always distinguish implementation truth (repository), durable decision
  memory (WDR), and current workflow permission/state (Asana).

- Check Asana before revising a WDR-owned mechanism when an active
  follow-up may exist.

- Respect “No” as a hard wait gate.

- Keep Asana concise and preserve its existing working structure; do not
  redesign or inflate it without an explicit engineering decision.

- Do not put mutable OPEN/CLOSED status, live task lists, or trial logs
  into WDRs.

- Verification remains mandatory. “It looks right” is not evidence.

# 8. Minimal verification standard

- Repository diff/file inspection confirms intended scope.

- Relevant automated tests and CI pass where applicable.

- Validators/template checks pass where repository invariants are
  involved.

- Persistence/state changes include concurrency, crash, fault, recovery,
  or production-canary checks when relevant.

- Documentation matches implemented behavior.

- The WDR records the evidence that existed when the durable decision
  was published.

# 9. Master memory rule

- Meaningful workflow or architecture decisions are preserved in WDRs.
  Active work is controlled through the existing concise Asana
  structure. Any Asana “No” gate means wait. The repository remains
  implementation truth. A WDR is revised only after permitted work
  stabilizes into a durable result.

# 10. Master blank Workflow Decision Record template

**USAGE:** CHECK REPO + ASANA → WORK ONLY IF ALLOWED → VERIFY → RECORD
DURABLE RESULT.

| Record metadata           | Entry                                       |
|---------------------------|---------------------------------------------|
| Entry ID                  | \[DD-MM-YYYY / repository / short-slug\]    |
| Date                      | \[DD-MM-YYYY\]                              |
| Change Type               | \[type\]                                    |
| Related Repository Area   | \[repository / path / subsystem\]           |
| Related Chat / Workstream | \[chat / branch / workstream\]              |
| Asana Tracking Reference  | \[existing Asana project/task or N/A\]      |
| Historical Relationship   | \[Supersedes / replaced by WDR ID, or N/A\] |

| Section | Record entry |
|---|---|
| 1. CHANGE SUMMARY | [What durable decision changed?] |
| 2. WHY WE CHANGED IT | [Problem, lesson, limitation, or verified requirement.] |
| 3. PREVIOUS WORKFLOW | [Previous durable mechanism.] |
| 4. NEW WORKFLOW | [New durable mechanism.] |
| 5. IMPORTANT RULES FOR FUTURE CHATGPT | [Rules that must survive future chats. Live workflow state belongs in Asana.] |
| 6. REPOSITORY IMPACT | Files/folders affected: - [path] / Documentation updated: - [path] |
| 7. DATA / ARCHITECTURE IMPACT | [Data, identity, traceability, boundaries, workflow.] |
| 8. SAFETY / FAILURE MODES | [Failure modes and required checks.] |
| 9. ASANA CONTROL REFERENCE | [Relevant existing Asana project/task or N/A.] Do not mirror live task lists here. If the relevant Asana control is “No”, the work waits and this WDR is not revised for that pending change. |
| 10. FUTURE NOTES | [Durable context only; not a task list.] |
| 11. VERIFICATION | [Tests, CI, audits, validators, canaries, read-back evidence.] |

**Lifecycle rule:** Asana controls whether work proceeds. Repository
proves what exists. WDR preserves the durable result. “No” means wait.
