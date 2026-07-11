"""Small CLI for validating generated workflow specifications."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

from .planner import PlannerConfig, planner_from_config
from .spec import WorkflowSpec


def main() -> None:
    parser = argparse.ArgumentParser(prog="adk-dynamic-workflows")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate a workflow JSON file")
    validate.add_argument("path", type=Path)
    plan = subparsers.add_parser("plan", help="generate a workflow with an LLM")
    plan.add_argument("request")
    plan.add_argument(
        "--agent-profile",
        action="append",
        required=True,
        help="allowlisted agent profile; repeat for more than one",
    )
    plan.add_argument("--output", type=Path)
    plan.add_argument("--yes", action="store_true", help="skip approval prompt")
    args = parser.parse_args()

    if args.command == "validate":
        spec = WorkflowSpec.model_validate_json(args.path.read_text())
        print(f"valid workflow: {spec.name}")
    elif args.command == "plan":
        load_dotenv()
        asyncio.run(
            _plan(
                request=args.request,
                agent_profiles=args.agent_profile,
                output=args.output,
                assume_yes=args.yes,
            )
        )


async def _plan(
    *,
    request: str,
    agent_profiles: list[str],
    output: Path | None,
    assume_yes: bool,
) -> None:
    planner = planner_from_config(
        PlannerConfig.from_env(), agent_profiles=agent_profiles
    )
    spec = await planner.plan(request)
    rendered = spec.model_dump_json(indent=2)
    print(rendered)

    approved = assume_yes or input("Approve this workflow? [y/N] ").lower() in {
        "y",
        "yes",
    }
    if not approved:
        raise SystemExit("workflow rejected")
    if output:
        output.write_text(f"{rendered}\n")
        print(f"saved approved workflow to {output}")
