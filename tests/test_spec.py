from __future__ import annotations

import pytest
from pydantic import ValidationError

from adk_dynamic_workflows.spec import WorkflowSpec


def test_rejects_duplicate_step_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate step id"):
        WorkflowSpec.model_validate(
            {
                "version": 1,
                "name": "duplicate-test",
                "description": "A workflow with duplicate IDs",
                "root": {
                    "type": "sequence",
                    "id": "root",
                    "steps": [
                        _agent_step("same"),
                        _agent_step("same"),
                    ],
                },
            }
        )


def test_rejects_unknown_output_reference() -> None:
    step = _agent_step("review")
    step["input"] = {"type": "step_output", "step_id": "missing"}

    with pytest.raises(ValidationError, match="unknown step output references"):
        WorkflowSpec.model_validate(
            {
                "version": 1,
                "name": "reference-test",
                "description": "A workflow with an invalid reference",
                "root": step,
            }
        )


def _agent_step(step_id: str) -> dict[str, object]:
    return {
        "type": "agent",
        "id": step_id,
        "agent": "reviewer",
        "prompt": "Review the input",
    }
