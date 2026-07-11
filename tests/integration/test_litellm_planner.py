from __future__ import annotations

import os

import pytest
from dotenv import load_dotenv

from adk_dynamic_workflows.planner import PlannerConfig, planner_from_config
from adk_dynamic_workflows.spec import (
    AgentStep,
    ConditionStep,
    MapStep,
    ParallelStep,
    RepeatStep,
    SequenceStep,
    Step,
    WorkflowSpec,
)

load_dotenv()


def _provider_is_configured() -> bool:
    key = os.getenv("DYNAMIC_WORKFLOWS_LLM_API_KEY", "")
    return bool(key and key != "replace-with-your-api-key")


@pytest.mark.integration
@pytest.mark.skipif(
    not _provider_is_configured(),
    reason="set the OpenAI-compatible provider values in .env",
)
async def test_real_litellm_planner_generates_valid_allowlisted_workflow() -> None:
    planner = planner_from_config(
        PlannerConfig.from_env(),
        agent_profiles=["explorer", "reviewer"],
    )

    spec = await planner.plan(
        "Create a workflow that receives an object with a files array and reviews "
        "every file concurrently using the reviewer agent."
    )

    assert isinstance(spec, WorkflowSpec)
    assert _agent_names(spec.root) == {"reviewer"}


def _agent_names(step: Step) -> set[str]:
    if isinstance(step, AgentStep):
        return {step.agent}
    names: set[str] = set()
    for child in _children(step):
        names.update(_agent_names(child))
    return names


def _children(step: Step) -> list[Step]:
    if isinstance(step, SequenceStep):
        return step.steps
    if isinstance(step, ParallelStep):
        return step.branches
    if isinstance(step, (MapStep, RepeatStep)):
        return [step.body]
    if isinstance(step, ConditionStep):
        return [step.then, *([step.otherwise] if step.otherwise else [])]
    return []
