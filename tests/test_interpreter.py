from __future__ import annotations

import asyncio
from typing import Any

import pytest

from adk_dynamic_workflows.interpreter import AgentRequest, WorkflowInterpreter
from adk_dynamic_workflows.spec import WorkflowSpec


class RecordingBackend:
    def __init__(self) -> None:
        self.requests: list[AgentRequest] = []
        self.active = 0
        self.max_active = 0

    async def run_agent(self, request: AgentRequest) -> Any:
        self.requests.append(request)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return {"agent": request.agent, "input": request.input}


async def test_sequence_passes_step_output() -> None:
    backend = RecordingBackend()
    spec = WorkflowSpec.model_validate(
        {
            "version": 1,
            "name": "sequence-test",
            "description": "Pass output between agents",
            "root": {
                "type": "sequence",
                "id": "pipeline",
                "steps": [
                    {
                        "type": "agent",
                        "id": "discover",
                        "agent": "explorer",
                        "prompt": "Discover files",
                    },
                    {
                        "type": "agent",
                        "id": "summarize",
                        "agent": "writer",
                        "prompt": "Summarize findings",
                        "input": {
                            "type": "step_output",
                            "step_id": "discover",
                        },
                    },
                ],
            },
        }
    )

    result = await WorkflowInterpreter(backend).execute(spec, {"path": "src"})

    assert result == {
        "agent": "writer",
        "input": {"agent": "explorer", "input": {"path": "src"}},
    }
    assert [request.execution_id for request in backend.requests] == [
        "sequence-test/pipeline/discover",
        "sequence-test/pipeline/summarize",
    ]


async def test_map_is_ordered_and_concurrency_is_bounded() -> None:
    backend = RecordingBackend()
    spec = WorkflowSpec.model_validate(
        {
            "version": 1,
            "name": "map-test",
            "description": "Map over files",
            "root": {
                "type": "map",
                "id": "review-all",
                "items": {"type": "workflow_input", "key": "files"},
                "max_concurrency": 2,
                "body": {
                    "type": "agent",
                    "id": "review",
                    "agent": "reviewer",
                    "prompt": "Review file",
                    "input": {"type": "current_item"},
                },
            },
        }
    )

    result = await WorkflowInterpreter(backend).execute(
        spec, {"files": ["a.py", "b.py", "c.py"]}
    )

    assert [item["input"] for item in result] == ["a.py", "b.py", "c.py"]
    assert backend.max_active == 2
    assert [request.execution_id for request in backend.requests] == [
        "map-test/review-all/0/review",
        "map-test/review-all/1/review",
        "map-test/review-all/2/review",
    ]


async def test_unavailable_branch_output_fails_clearly() -> None:
    backend = RecordingBackend()
    spec = WorkflowSpec.model_validate(
        {
            "version": 1,
            "name": "branch-test",
            "description": "Invalid runtime branch access",
            "root": {
                "type": "parallel",
                "id": "branches",
                "branches": [
                    {
                        "type": "agent",
                        "id": "producer",
                        "agent": "producer",
                        "prompt": "Produce",
                    },
                    {
                        "type": "agent",
                        "id": "consumer",
                        "agent": "consumer",
                        "prompt": "Consume",
                        "input": {
                            "type": "step_output",
                            "step_id": "producer",
                        },
                    },
                ],
            },
        }
    )

    with pytest.raises(ValueError, match="not available in this branch"):
        await WorkflowInterpreter(backend).execute(spec)
