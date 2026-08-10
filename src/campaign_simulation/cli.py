"""Guided command-line entry point for branch-neutral campaign simulation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .admission import MainCampaignAdmissionError, admit_main_campaign
from .boundaries import CampaignBoundaryError
from .branches import PREQUEL_MODE, SEQUEL_MODE, SIMULATION_MODES, resolve_simulation_branch
from .convergence import begin_prequel_main_convergence, resolve_prequel_main_convergence
from .onboarding import CONTINUE_WITHOUT_OPTIONAL_MATERIAL
from .runtime import begin_simulation_onboarding, complete_simulation_onboarding
from .saves import load_checkpoint


def _parse_optional_selection(value: str | None, non_interactive: bool) -> list[str]:
    if value is None and non_interactive:
        return [CONTINUE_WITHOUT_OPTIONAL_MATERIAL]
    if value is None:
        value = input(
            "Optional material IDs (comma-separated, or press Enter to continue without adding material): "
        )
    selected = [item.strip() for item in value.split(",") if item.strip()]
    if not selected or selected == ["none"]:
        return [CONTINUE_WITHOUT_OPTIONAL_MATERIAL]
    return selected


def _storage_input(args: argparse.Namespace):
    responses: list[str] = []
    if args.storage is not None:
        responses.append(args.storage)
        if args.storage == "supabase":
            responses.extend([args.supabase_url or "", args.supabase_key_env_var])
    elif args.non_interactive:
        responses.append("repository")

    def read(prompt: str) -> str:
        if responses:
            return responses.pop(0)
        if args.non_interactive:
            raise RuntimeError("non-interactive start needs complete storage arguments or repository mode")
        return input(prompt)

    return read


def _show_menu(menu: dict[str, object]) -> None:
    print(menu["message"])
    for option in menu["options"]:
        line = f"- {option['id']}: {option['label']}"
        description = option.get("description")
        if description:
            line += f" — {description}"
        print(line)


def _choose_mode(args: argparse.Namespace) -> str:
    if args.mode is not None:
        return args.mode
    if args.non_interactive:
        raise RuntimeError("non-interactive start requires --mode prequel or sequel")

    while True:
        answer = input("What would you like to explore? [prequel/sequel]: ").strip().lower()
        shortcuts = {"p": PREQUEL_MODE, "s": SEQUEL_MODE}
        answer = shortcuts.get(answer, answer)
        if answer in SIMULATION_MODES:
            return answer
        print("Please choose 'prequel' to explore the past or 'sequel' to explore the future.")


def _choose_anchor(args: argparse.Namespace, mode: str) -> str | None:
    if args.anchor is not None:
        return args.anchor
    if args.non_interactive:
        if mode == PREQUEL_MODE:
            raise RuntimeError("non-interactive prequel start requires --anchor")
        return None

    if mode == PREQUEL_MODE:
        while True:
            answer = input("Where in the past should the prequel begin? ").strip()
            if answer:
                return answer
            print("A prequel needs a short historical anchor. One sentence is enough.")

    answer = input(
        "Sequel start point (press Enter to use the Main Campaign's current situation): "
    ).strip()
    return answer or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="campaign-simulation")
    subcommands = parser.add_subparsers(dest="command", required=True)

    validate = subcommands.add_parser("validate-main", help="validate the minimum Main Campaign")
    validate.add_argument("--main-campaign", required=True, type=Path)

    start = subcommands.add_parser("start", help="run guided Prequel or Sequel onboarding")
    start.add_argument("--main-campaign", required=True, type=Path)
    start.add_argument("--runtime", required=True, type=Path)
    start.add_argument("--mode", choices=SIMULATION_MODES)
    start.add_argument(
        "--anchor",
        help="branch start point; required for Prequel, optional for Sequel",
    )
    start.add_argument(
        "--optional",
        help="comma-separated optional material IDs; use none or leave empty to continue directly",
    )
    start.add_argument("--storage", choices=("repository", "supabase"))
    start.add_argument("--supabase-url")
    start.add_argument("--supabase-key-env-var", default="SUPABASE_KEY")
    start.add_argument("--non-interactive", action="store_true")

    converge = subcommands.add_parser(
        "converge-prequel", help="freeze a Prequel at its Main Campaign convergence boundary"
    )
    converge.add_argument("--main-campaign", required=True, type=Path)
    converge.add_argument("--prequel-checkpoint", required=True, type=Path)
    converge.add_argument("--main-target", required=True)
    converge.add_argument(
        "--choice",
        choices=("enter_main_unchanged", "propose_canon_changes", "continue_as_alternate_timeline"),
    )
    converge.add_argument("--proposal-json", default="[]")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-main":
            manifest = admit_main_campaign(args.main_campaign)
            print(json.dumps({"status": "admitted", "main_campaign": manifest}, indent=2))
            return 0

        if args.command == "converge-prequel":
            admit_main_campaign(args.main_campaign)
            convergence = begin_prequel_main_convergence(
                load_checkpoint(args.prequel_checkpoint), args.main_target
            )
            if args.choice:
                proposal = json.loads(args.proposal_json)
                if not isinstance(proposal, list):
                    raise ValueError("--proposal-json must be a JSON list")
                convergence = resolve_prequel_main_convergence(convergence, args.choice, proposal)
            print(json.dumps(convergence, indent=2))
            return 0

        onboarding = begin_simulation_onboarding(args.main_campaign)
        if not args.non_interactive:
            _show_menu(onboarding["exploration_menu"])
        mode = _choose_mode(args)
        anchor = _choose_anchor(args, mode)
        branch = resolve_simulation_branch(onboarding["main_campaign"], mode, anchor)

        if not args.non_interactive:
            _show_menu(onboarding["optional_material_menu"])
        selected_optional_material = _parse_optional_selection(args.optional, args.non_interactive)

        result = complete_simulation_onboarding(
            args.main_campaign,
            args.runtime,
            branch,
            selected_optional_material,
            input_fn=_storage_input(args),
        )
    except (CampaignBoundaryError, MainCampaignAdmissionError, ValueError, RuntimeError) as error:
        print(f"campaign-simulation: {error}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "status": "started",
                "simulation_mode": result["branch"]["mode"],
                "branch": result["branch"],
                "selected_optional_material": result["optional_material"],
                "storage": result["storage"],
            },
            indent=2,
        )
    )
    return 0
