"""Small CLI for validating generated workflow specifications."""

from __future__ import annotations

import argparse
from pathlib import Path

from .spec import WorkflowSpec


def main() -> None:
    parser = argparse.ArgumentParser(prog="adk-dynamic-workflows")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="validate a workflow JSON file")
    validate.add_argument("path", type=Path)
    args = parser.parse_args()

    if args.command == "validate":
        spec = WorkflowSpec.model_validate_json(args.path.read_text())
        print(f"valid workflow: {spec.name}")
