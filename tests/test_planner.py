from __future__ import annotations

import pytest

from adk_dynamic_workflows.planner import (
    PlannerConfig,
    WorkflowPlanner,
    parse_spec_response,
)


def test_placeholder_api_key_is_rejected() -> None:
    config = PlannerConfig(
        model="openai/gpt-4o-mini",
        api_base="https://api.openai.com/v1",
        api_key="replace-with-your-api-key",
    )

    with pytest.raises(ValueError, match="DYNAMIC_WORKFLOWS_LLM_API_KEY"):
        config.build_model()


def test_planner_requires_agent_profiles() -> None:
    config = PlannerConfig(
        model="openai/gpt-4o-mini",
        api_base="https://api.openai.com/v1",
        api_key="test-key",
    )

    with pytest.raises(ValueError, match="agent profile"):
        WorkflowPlanner(model=config.build_model(), agent_profiles=[])


def test_parses_json_embedded_in_provider_prose() -> None:
    response = """I created this workflow:
```json
{
  "version": 1,
  "name": "review-files",
  "description": "Review files",
  "root": {
    "type": "agent",
    "id": "review",
    "agent": "reviewer",
    "prompt": "Review the files"
  }
}
```
"""

    spec = parse_spec_response(response)

    assert spec.name == "review-files"
