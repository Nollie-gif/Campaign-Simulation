"""Guided command-line entry point for a campaign simulation sequel."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .admission import MainCampaignAdmissionError, admit_main_campaign
from .onboarding import CONTINUE_WITHOUT_OPTIONAL_MATERIAL
from .runtime import begin_sequel_onboarding, complete_sequel_onboarding


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
            raise RuntimeError("non-interactive start needs --storage supabase details or repository mode")
        return input(prompt)

    return read


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="campaign-simulation")
    subcommands = parser.add_subparsers(dest="command", required=True)

    validate = subcommands.add_parser("validate-main", help="validate the minimum main campaign")
    validate.add_argument("--main-campaign", required=True, type=Path)

    start = subcommands.add_parser("start", help="run guided sequel onboarding")
    start.add_argument("--main-campaign", required=True, type=Path)
    start.add_argument("--runtime", required=True, type=Path)
    start.add_argument(
        "--optional",
        help="comma-separated optional material IDs; use none or leave empty to continue directly",
    )
    start.add_argument("--storage", choices=("repository", "supabase"))
    start.add_argument("--supabase-url")
    start.add_argument("--supabase-key-env-var", default="SUPABASE_KEY")
    start.add_argument("--non-interactive", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-main":
            manifest = admit_main_campaign(args.main_campaign)
            print(json.dumps({"status": "admitted", "main_campaign": manifest}, indent=2))
            return 0

        onboarding = begin_sequel_onboarding(args.main_campaign)
        selected_optional_material = _parse_optional_selection(args.optional, args.non_interactive)
        result = complete_sequel_onboarding(
            args.main_campaign,
            args.runtime / "storage-configuration.json",
            selected_optional_material,
            input_fn=_storage_input(args),
        )
    except (MainCampaignAdmissionError, ValueError, RuntimeError) as error:
        print(f"campaign-simulation: {error}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "status": "started",
                "optional_material_menu": onboarding["optional_material_menu"],
                "selected_optional_material": result["optional_material"],
                "storage": result["storage"],
            },
            indent=2,
        )
    )
    return 0
