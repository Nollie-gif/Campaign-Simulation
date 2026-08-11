"""Procedure-aware mutation scope and lifecycle validation.

The gate is deliberately campaign-neutral.  It validates *how* a caller is
trying to persist a transition; it does not decide any narrative outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence


class MutationGateError(ValueError):
    """A precise, safe-to-show reason why a candidate may not proceed."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class MutationDomain(str, Enum):
    """Stable ownership families, not file names or campaign-specific paths."""

    RUNTIME_STATE = "runtime_state"
    KNOWLEDGE = "knowledge"
    NPC_OPERATIONAL = "npc_operational"
    HOOK = "hook"
    SCENARIO = "scenario"
    DEFERRED_EVENT = "deferred_event"
    CAMPAIGN_CLOCK = "campaign_clock"
    AUTOSAVE = "autosave"
    SCHEDULER = "scheduler"
    IDENTIFIERS = "identifiers"
    SESSION_STATE = "session_state"
    FINALIZED_HISTORY = "finalized_history"
    LIVE_INDEX = "live_index"
    STATIC_DEFINITION = "static_definition"
    ENGINEERING_CODE = "engineering_code"
    ENGINEERING_DOCS = "engineering_docs"
    CI_WORKFLOW = "ci_workflow"
    SCHEMA = "schema"
    TESTS = "tests"
    MAIN_CAMPAIGN = "main_campaign"
    PREQUEL_BOUNDARY = "prequel_boundary"
    GITHUB_STAGING = "github_staging"
    GITHUB_RUNTIME_PUBLISHED = "github_runtime_published"
    SUPABASE_STAGING = "supabase_staging"
    SUPABASE_PUBLICATION = "supabase_publication"
    RECONCILIATION = "reconciliation"
    VALIDATION = "validation"
    PUBLICATION = "publication"
    CONSEQUENCE = "consequence"


class Procedure(str, Enum):
    QUICKSAVE = "quicksave"
    AUTOSAVE = "autosave"
    FINAL_SAVE = "final_save"
    KNOWLEDGE_ONLY = "knowledge_only"
    SCENARIO_ACTIVATION = "scenario_activation"
    SCENARIO_COMPLETION = "scenario_completion"
    HOOK_ACTIVATION = "hook_activation"
    HOOK_RESOLUTION = "hook_resolution"
    HOOK_RETIREMENT = "hook_retirement"
    DEFERRED_EVENT_CREATION = "deferred_event_creation"
    DEFERRED_EVENT_RESOLUTION = "deferred_event_resolution"
    DEFERRED_EVENT_CANCELLATION = "deferred_event_cancellation"
    START_OF_DAY = "start_of_day"
    CAMPAIGN_CLOCK_UPDATE = "campaign_clock_update"
    SCHEDULER_UPDATE = "scheduler_update"
    IDENTIFIER_ALLOCATION = "identifier_allocation"
    NPC_OPERATIONAL_RECONCILIATION = "npc_operational_reconciliation"
    ENGINEERING_CHANGE = "engineering_change"
    PREQUEL_MAIN_CONVERGENCE = "prequel_main_convergence"
    FINALIZED_HISTORY_MAINTENANCE = "finalized_history_maintenance"
    GITHUB_RUNTIME_PUBLICATION = "github_runtime_publication"
    SUPABASE_RUNTIME_PUBLICATION = "supabase_runtime_publication"


class MutationKind(str, Enum):
    WRITE = "write"
    DELETE = "delete"
    TRANSITION = "transition"
    ALLOCATE = "allocate"
    RECONCILE = "reconcile"
    VALIDATE = "validate"
    PUBLISH = "publish"


@dataclass(frozen=True)
class MutationOperation:
    """One declared durable mutation or mandatory procedure action."""

    domain: MutationDomain
    target: str
    kind: MutationKind = MutationKind.WRITE
    current_state: str | None = None
    next_state: str | None = None

    def __post_init__(self) -> None:
        if not self.target or not self.target.strip():
            raise MutationGateError("invalid_target", "every mutation target must be non-empty")


@dataclass(frozen=True)
class MutationPlan:
    """A candidate transaction declared before any authoritative publication."""

    procedure: Procedure
    operations: tuple[MutationOperation, ...]
    facts: frozenset[str] = frozenset()
    branch: str | None = None
    sql_mode: str = "none"
    persistence_mode: str = "repository"
    published_generation: int | None = None
    staging_generation: int | None = None

    def __post_init__(self) -> None:
        if self.sql_mode not in {"none", "gated", "raw"}:
            raise MutationGateError("invalid_sql_mode", "sql_mode must be none, gated, or raw")
        if self.persistence_mode not in {"repository", "generation_pinned"}:
            raise MutationGateError(
                "invalid_persistence_mode",
                "persistence_mode must be repository or generation_pinned",
            )
        if not self.operations:
            raise MutationGateError("empty_plan", "a gated procedure must declare its operations")
        if self.published_generation is not None and self.published_generation < 0:
            raise MutationGateError("invalid_generation", "published generation cannot be negative")
        if self.staging_generation is not None and self.staging_generation < 0:
            raise MutationGateError("invalid_generation", "staging generation cannot be negative")


@dataclass(frozen=True)
class PublicationReceipt:
    """Evidence returned after a provider-specific publication completes."""

    procedure: Procedure
    published_generation: int
    published_git_ref: str
    published_day: int
    git_mirror_confirmed: bool
    store_parity_confirmed: bool
    checkpoint_committed: bool
    last_healthy_checkpoint: str


@dataclass(frozen=True)
class ProcedurePolicy:
    allowed_domains: frozenset[MutationDomain]
    required_facts: frozenset[str] = frozenset()
    requires_staging_generation: bool = False
    requires_publication_receipt: bool = False
    allowed_branch: str | None = None


_SAVE_DOMAINS = frozenset(
    {
        MutationDomain.RUNTIME_STATE,
        MutationDomain.KNOWLEDGE,
        MutationDomain.NPC_OPERATIONAL,
        MutationDomain.HOOK,
        MutationDomain.SCENARIO,
        MutationDomain.GITHUB_STAGING,
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.RECONCILIATION,
        MutationDomain.VALIDATION,
        MutationDomain.PUBLICATION,
    }
)


def _policy(
    *domains: MutationDomain,
    facts: Iterable[str] = (),
    staging: bool = False,
    receipt: bool = False,
    branch: str | None = None,
) -> ProcedurePolicy:
    return ProcedurePolicy(frozenset(domains), frozenset(facts), staging, receipt, branch)


PROCEDURE_POLICIES: Mapping[Procedure, ProcedurePolicy] = {
    Procedure.QUICKSAVE: ProcedurePolicy(
        _SAVE_DOMAINS,
        frozenset({"reconciled", "validated", "same_checkpoint"}),
        True,
        True,
    ),
    Procedure.AUTOSAVE: ProcedurePolicy(
        _SAVE_DOMAINS,
        frozenset({"reconciled", "validated", "same_checkpoint"}),
        True,
        True,
    ),
    Procedure.FINAL_SAVE: ProcedurePolicy(
        _SAVE_DOMAINS | {MutationDomain.FINALIZED_HISTORY, MutationDomain.LIVE_INDEX},
        frozenset({"reconciled", "validated", "same_checkpoint", "day_finalized", "live_indexes_reconciled"}),
        True,
        True,
    ),
    Procedure.KNOWLEDGE_ONLY: _policy(
        MutationDomain.KNOWLEDGE,
        MutationDomain.GITHUB_STAGING,
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.RECONCILIATION,
        MutationDomain.VALIDATION,
        MutationDomain.PUBLICATION,
        facts={"knowledge_reconciled", "validated", "same_checkpoint"},
        staging=True,
        receipt=True,
    ),
    Procedure.SCENARIO_ACTIVATION: _policy(
        MutationDomain.SCENARIO,
        MutationDomain.HOOK,
        MutationDomain.RUNTIME_STATE,
        MutationDomain.GITHUB_STAGING,
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.RECONCILIATION,
        MutationDomain.VALIDATION,
        MutationDomain.PUBLICATION,
        facts={"scenario_references_coherent", "validated", "same_checkpoint"},
        staging=True,
        receipt=True,
    ),
    Procedure.SCENARIO_COMPLETION: _policy(
        MutationDomain.SCENARIO,
        MutationDomain.HOOK,
        MutationDomain.RUNTIME_STATE,
        MutationDomain.CONSEQUENCE,
        MutationDomain.GITHUB_STAGING,
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.RECONCILIATION,
        MutationDomain.VALIDATION,
        MutationDomain.PUBLICATION,
        facts={"primary_hooks_coherent", "consequences_persisted", "validated", "same_checkpoint"},
        staging=True,
        receipt=True,
    ),
    Procedure.HOOK_ACTIVATION: _policy(
        MutationDomain.HOOK,
        MutationDomain.RUNTIME_STATE,
        MutationDomain.GITHUB_STAGING,
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.RECONCILIATION,
        MutationDomain.VALIDATION,
        MutationDomain.PUBLICATION,
        facts={"validated", "same_checkpoint"},
        staging=True,
        receipt=True,
    ),
    Procedure.HOOK_RESOLUTION: _policy(
        MutationDomain.HOOK,
        MutationDomain.SCENARIO,
        MutationDomain.RUNTIME_STATE,
        MutationDomain.CONSEQUENCE,
        MutationDomain.GITHUB_STAGING,
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.RECONCILIATION,
        MutationDomain.VALIDATION,
        MutationDomain.PUBLICATION,
        facts={"linked_scenarios_coherent", "consequences_persisted", "validated", "same_checkpoint"},
        staging=True,
        receipt=True,
    ),
    Procedure.HOOK_RETIREMENT: _policy(
        MutationDomain.HOOK,
        MutationDomain.RUNTIME_STATE,
        MutationDomain.GITHUB_STAGING,
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.RECONCILIATION,
        MutationDomain.VALIDATION,
        MutationDomain.PUBLICATION,
        facts={"validated", "same_checkpoint"},
        staging=True,
        receipt=True,
    ),
    Procedure.DEFERRED_EVENT_CREATION: _policy(
        MutationDomain.DEFERRED_EVENT,
        MutationDomain.SCHEDULER,
        MutationDomain.RUNTIME_STATE,
        MutationDomain.IDENTIFIERS,
        MutationDomain.GITHUB_STAGING,
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.RECONCILIATION,
        MutationDomain.VALIDATION,
        MutationDomain.PUBLICATION,
        facts={"event_id_persisted", "validated", "same_checkpoint"},
        staging=True,
        receipt=True,
    ),
    Procedure.DEFERRED_EVENT_RESOLUTION: _policy(
        MutationDomain.DEFERRED_EVENT,
        MutationDomain.SCHEDULER,
        MutationDomain.RUNTIME_STATE,
        MutationDomain.HOOK,
        MutationDomain.SCENARIO,
        MutationDomain.CONSEQUENCE,
        MutationDomain.GITHUB_STAGING,
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.RECONCILIATION,
        MutationDomain.VALIDATION,
        MutationDomain.PUBLICATION,
        facts={"event_terminal", "consequences_persisted", "validated", "same_checkpoint"},
        staging=True,
        receipt=True,
    ),
    Procedure.DEFERRED_EVENT_CANCELLATION: _policy(
        MutationDomain.DEFERRED_EVENT,
        MutationDomain.SCHEDULER,
        MutationDomain.RUNTIME_STATE,
        MutationDomain.GITHUB_STAGING,
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.RECONCILIATION,
        MutationDomain.VALIDATION,
        MutationDomain.PUBLICATION,
        facts={"event_terminal", "validated", "same_checkpoint"},
        staging=True,
        receipt=True,
    ),
    Procedure.START_OF_DAY: _policy(
        MutationDomain.RUNTIME_STATE,
        MutationDomain.NPC_OPERATIONAL,
        MutationDomain.HOOK,
        MutationDomain.CAMPAIGN_CLOCK,
        MutationDomain.GITHUB_STAGING,
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.RECONCILIATION,
        MutationDomain.VALIDATION,
        MutationDomain.PUBLICATION,
        facts={"previous_day_finalized", "new_day_initialized", "validated", "same_checkpoint"},
        staging=True,
        receipt=True,
    ),
    Procedure.CAMPAIGN_CLOCK_UPDATE: _policy(
        MutationDomain.CAMPAIGN_CLOCK,
        MutationDomain.RUNTIME_STATE,
        MutationDomain.GITHUB_STAGING,
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.VALIDATION,
        MutationDomain.PUBLICATION,
        facts={"clock_monotonic", "validated", "same_checkpoint"},
        staging=True,
        receipt=True,
    ),
    Procedure.SCHEDULER_UPDATE: _policy(
        MutationDomain.SCHEDULER,
        MutationDomain.DEFERRED_EVENT,
        MutationDomain.RUNTIME_STATE,
        MutationDomain.GITHUB_STAGING,
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.VALIDATION,
        MutationDomain.PUBLICATION,
        facts={"scheduler_idempotent", "validated", "same_checkpoint"},
        staging=True,
        receipt=True,
    ),
    Procedure.IDENTIFIER_ALLOCATION: _policy(
        MutationDomain.IDENTIFIERS,
        MutationDomain.SESSION_STATE,
        facts={"identifier_persisted_atomically"},
    ),
    Procedure.NPC_OPERATIONAL_RECONCILIATION: _policy(
        MutationDomain.NPC_OPERATIONAL,
        MutationDomain.RUNTIME_STATE,
        MutationDomain.GITHUB_STAGING,
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.RECONCILIATION,
        MutationDomain.VALIDATION,
        MutationDomain.PUBLICATION,
        facts={"npc_overlay_reconciled", "validated", "same_checkpoint"},
        staging=True,
        receipt=True,
    ),
    Procedure.ENGINEERING_CHANGE: _policy(
        MutationDomain.ENGINEERING_CODE,
        MutationDomain.ENGINEERING_DOCS,
        MutationDomain.CI_WORKFLOW,
        MutationDomain.SCHEMA,
        MutationDomain.TESTS,
        facts={"focused_branch", "tests_passed", "documentation_covered", "pull_request"},
    ),
    Procedure.PREQUEL_MAIN_CONVERGENCE: _policy(
        MutationDomain.PREQUEL_BOUNDARY,
        MutationDomain.RUNTIME_STATE,
        MutationDomain.SESSION_STATE,
        facts={"main_campaign_read_only", "explicit_user_choice"},
    ),
    Procedure.FINALIZED_HISTORY_MAINTENANCE: _policy(
        MutationDomain.FINALIZED_HISTORY,
        MutationDomain.LIVE_INDEX,
        MutationDomain.GITHUB_STAGING,
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.RECONCILIATION,
        MutationDomain.VALIDATION,
        MutationDomain.PUBLICATION,
        facts={"maintenance_authorized", "validated", "same_checkpoint"},
        staging=True,
        receipt=True,
    ),
    Procedure.GITHUB_RUNTIME_PUBLICATION: _policy(
        MutationDomain.GITHUB_RUNTIME_PUBLISHED,
        facts={"published_ref_verified"},
        branch="runtime-published",
    ),
    Procedure.SUPABASE_RUNTIME_PUBLICATION: _policy(
        MutationDomain.SUPABASE_PUBLICATION,
        MutationDomain.PUBLICATION,
        facts={"published_generation_advanced", "store_parity_confirmed"},
        staging=True,
        receipt=True,
    ),
}


LIFECYCLE_TRANSITIONS: Mapping[MutationDomain, Mapping[str, frozenset[str]]] = {
    MutationDomain.SCENARIO: {
        "draft": frozenset({"available"}),
        "available": frozenset({"active", "abandoned", "expired"}),
        "active": frozenset({"completed", "abandoned", "expired"}),
        "completed": frozenset(),
        "abandoned": frozenset(),
        "expired": frozenset(),
    },
    MutationDomain.HOOK: {
        "dormant": frozenset({"active", "retired"}),
        "active": frozenset({"resolved", "retired"}),
        "resolved": frozenset(),
        "retired": frozenset(),
    },
    MutationDomain.DEFERRED_EVENT: {
        "pending": frozenset({"resolved", "cancelled"}),
        "resolved": frozenset(),
        "cancelled": frozenset(),
    },
}


_RUNTIME_SQL_DOMAINS = frozenset(
    {
        MutationDomain.RUNTIME_STATE,
        MutationDomain.KNOWLEDGE,
        MutationDomain.NPC_OPERATIONAL,
        MutationDomain.HOOK,
        MutationDomain.SCENARIO,
        MutationDomain.DEFERRED_EVENT,
        MutationDomain.CAMPAIGN_CLOCK,
        MutationDomain.SCHEDULER,
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.SUPABASE_PUBLICATION,
    }
)


def route_user_request(request: str) -> Procedure:
    """Map simple DM vocabulary to the internal procedure identity."""

    normalized = " ".join(request.casefold().strip().split())
    for prefix in ("dm note:", "dm note"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].lstrip()
    aliases = {
        "save": Procedure.QUICKSAVE,
        "quicksave": Procedure.QUICKSAVE,
        "autosave": Procedure.AUTOSAVE,
        "final save": Procedure.FINAL_SAVE,
        "knowledge save": Procedure.KNOWLEDGE_ONLY,
        "start of day": Procedure.START_OF_DAY,
        "scenario activation": Procedure.SCENARIO_ACTIVATION,
        "scenario completion": Procedure.SCENARIO_COMPLETION,
        "event resolution": Procedure.DEFERRED_EVENT_RESOLUTION,
    }
    try:
        return aliases[normalized]
    except KeyError as error:
        raise MutationGateError("unknown_procedure", f"no safe route exists for {request!r}") from error


def _policy_for(procedure: Procedure) -> ProcedurePolicy:
    try:
        return PROCEDURE_POLICIES[procedure]
    except KeyError as error:
        raise MutationGateError("unknown_procedure", f"no policy exists for {procedure.value}") from error


def _validate_lifecycle_transitions(plan: MutationPlan) -> None:
    for operation in plan.operations:
        if operation.kind is not MutationKind.TRANSITION:
            continue
        transitions = LIFECYCLE_TRANSITIONS.get(operation.domain)
        if transitions is None:
            raise MutationGateError(
                "unsupported_lifecycle_domain",
                f"{operation.domain.value} cannot declare a lifecycle transition",
            )
        if operation.current_state is None or operation.next_state is None:
            raise MutationGateError(
                "incomplete_lifecycle_transition",
                f"{operation.target} must declare both current_state and next_state",
            )
        if operation.next_state not in transitions.get(operation.current_state, frozenset()):
            raise MutationGateError(
                "illegal_lifecycle_transition",
                f"{operation.target}: {operation.current_state!r} -> {operation.next_state!r} is not allowed",
            )


def _validate_record_coverage(plan: MutationPlan, record_ids: Iterable[str] | None) -> None:
    if record_ids is None:
        return
    expected = {record_id for record_id in record_ids}
    declared = {operation.target for operation in plan.operations}
    missing = expected - declared
    if missing:
        raise MutationGateError(
            "undeclared_record_mutation",
            "the plan does not cover checkpoint records: " + ", ".join(sorted(missing)),
        )


def validate_mutation_plan(plan: MutationPlan, *, record_ids: Iterable[str] | None = None) -> None:
    """Reject forbidden scope, unsafe SQL paths, and incomplete coupled transitions."""

    policy = _policy_for(plan.procedure)
    if plan.branch == "main":
        raise MutationGateError("protected_main", "a mutation procedure may never write directly to main")
    if policy.allowed_branch is not None and plan.branch != policy.allowed_branch:
        raise MutationGateError(
            "wrong_publication_branch",
            f"{plan.procedure.value} must run on {policy.allowed_branch!r}",
        )
    if plan.procedure is not Procedure.GITHUB_RUNTIME_PUBLICATION and plan.branch == "runtime-published":
        raise MutationGateError(
            "direct_runtime_publish",
            "runtime-published may only move through the dedicated publication procedure",
        )

    domains = {operation.domain for operation in plan.operations}
    forbidden = domains - policy.allowed_domains
    if forbidden:
        raise MutationGateError(
            "forbidden_domain",
            f"{plan.procedure.value} cannot mutate: "
            + ", ".join(sorted(domain.value for domain in forbidden)),
        )
    if MutationDomain.MAIN_CAMPAIGN in domains:
        raise MutationGateError("main_campaign_write", "the Main Campaign is read-only to simulations")

    missing_facts = policy.required_facts - plan.facts
    if missing_facts:
        raise MutationGateError(
            "missing_postcondition",
            f"{plan.procedure.value} is missing: " + ", ".join(sorted(missing_facts)),
        )

    if policy.requires_staging_generation and plan.persistence_mode == "generation_pinned":
        if plan.published_generation is None or plan.staging_generation is None:
            raise MutationGateError(
                "missing_staging_generation",
                f"{plan.procedure.value} requires published and staging generations",
            )
        if plan.staging_generation <= plan.published_generation:
            raise MutationGateError(
                "invalid_staging_generation",
                "staging generation must be newer than the published generation",
            )

    if plan.persistence_mode == "repository" and domains & {
        MutationDomain.SUPABASE_STAGING,
        MutationDomain.SUPABASE_PUBLICATION,
    }:
        raise MutationGateError(
            "provider_mode_mismatch",
            "Supabase domains require generation_pinned persistence mode",
        )
    if plan.sql_mode == "raw" and domains & _RUNTIME_SQL_DOMAINS:
        raise MutationGateError(
            "ungated_sql_mutation",
            "runtime-owned SQL mutations require the declared generation-aware gated path",
        )
    if MutationDomain.KNOWLEDGE in domains and plan.sql_mode != "gated":
        raise MutationGateError(
            "knowledge_path_not_gated",
            "durable Knowledge mutations require the gated SQL path",
        )

    _validate_lifecycle_transitions(plan)
    _validate_record_coverage(plan, record_ids)


def validate_publication_receipt(plan: MutationPlan, receipt: PublicationReceipt) -> None:
    """Verify the authoritative publication evidence after a provider completes."""

    policy = _policy_for(plan.procedure)
    if not policy.requires_publication_receipt or plan.persistence_mode == "repository":
        return
    if receipt.procedure is not plan.procedure:
        raise MutationGateError("receipt_procedure_mismatch", "receipt belongs to a different procedure")
    if plan.staging_generation is not None and receipt.published_generation != plan.staging_generation:
        raise MutationGateError(
            "publication_generation_mismatch",
            "receipt generation does not equal the staged generation",
        )
    if receipt.published_generation < 1:
        raise MutationGateError("missing_published_generation", "receipt must show a published generation")
    if not receipt.published_git_ref or not receipt.published_git_ref.strip():
        raise MutationGateError("missing_published_git_ref", "receipt must show an exact Git ref")
    if receipt.published_day < 0:
        raise MutationGateError("invalid_published_day", "receipt day cannot be negative")
    if not receipt.checkpoint_committed:
        raise MutationGateError("checkpoint_not_committed", "receipt does not prove checkpoint commit")
    if not receipt.store_parity_confirmed:
        raise MutationGateError("store_parity_unconfirmed", "receipt does not prove store parity")
    if not receipt.git_mirror_confirmed:
        raise MutationGateError("mirror_unconfirmed", "receipt does not prove the Git runtime mirror")
    if not receipt.last_healthy_checkpoint or not receipt.last_healthy_checkpoint.strip():
        raise MutationGateError("missing_recovery_anchor", "receipt must retain the last healthy checkpoint")


def plan_to_mapping(plan: MutationPlan) -> dict[str, object]:
    """Return a JSON-safe audit record without embedding campaign content."""

    return {
        "procedure": plan.procedure.value,
        "branch": plan.branch,
        "sql_mode": plan.sql_mode,
        "persistence_mode": plan.persistence_mode,
        "published_generation": plan.published_generation,
        "staging_generation": plan.staging_generation,
        "facts": sorted(plan.facts),
        "operations": [
            {
                "domain": operation.domain.value,
                "target": operation.target,
                "kind": operation.kind.value,
                "current_state": operation.current_state,
                "next_state": operation.next_state,
            }
            for operation in plan.operations
        ],
    }
