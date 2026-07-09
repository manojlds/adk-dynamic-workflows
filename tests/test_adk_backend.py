from pathlib import Path

from google.adk.agents import Agent

from adk_dynamic_workflows.adk_backend import build_adk_workflow
from adk_dynamic_workflows.spec import WorkflowSpec


def test_builds_adk_workflow_from_kebab_case_spec_name() -> None:
    spec = WorkflowSpec.model_validate_json(Path("examples/review.json").read_text())
    reviewer = Agent(name="reviewer", model="gemini-flash-latest")

    workflow = build_adk_workflow(spec, {"reviewer": reviewer})

    assert workflow.name == "review_files"
