"""Serializable workflow language accepted from a planner model."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base model that rejects planner output we do not understand."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class LiteralValue(StrictModel):
    type: Literal["literal"] = "literal"
    value: Any


class WorkflowInputValue(StrictModel):
    type: Literal["workflow_input"] = "workflow_input"
    key: str | None = None


class StepOutputValue(StrictModel):
    type: Literal["step_output"] = "step_output"
    step_id: str


class CurrentItemValue(StrictModel):
    type: Literal["current_item"] = "current_item"


ValueSource = Annotated[
    LiteralValue | WorkflowInputValue | StepOutputValue | CurrentItemValue,
    Field(discriminator="type"),
]


class AgentStep(StrictModel):
    type: Literal["agent"] = "agent"
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    agent: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    prompt: str = Field(min_length=1)
    input: ValueSource = Field(default_factory=WorkflowInputValue)


class SequenceStep(StrictModel):
    type: Literal["sequence"] = "sequence"
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    steps: list[Step] = Field(min_length=1)


class ParallelStep(StrictModel):
    type: Literal["parallel"] = "parallel"
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    branches: list[Step] = Field(min_length=1, max_length=100)


class MapStep(StrictModel):
    type: Literal["map"] = "map"
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    items: ValueSource
    body: Step
    max_concurrency: int = Field(default=8, ge=1, le=32)


class ConditionStep(StrictModel):
    type: Literal["condition"] = "condition"
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    value: ValueSource
    equals: Any
    then: Step
    otherwise: Step | None = None


class RepeatStep(StrictModel):
    type: Literal["repeat"] = "repeat"
    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    count: int = Field(ge=1, le=20)
    body: Step


Step = Annotated[
    AgentStep | SequenceStep | ParallelStep | MapStep | ConditionStep | RepeatStep,
    Field(discriminator="type"),
]


class WorkflowSpec(StrictModel):
    """Canonical, versioned representation of a generated workflow."""

    version: Literal[1] = 1
    name: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    description: str = Field(min_length=1)
    root: Step

    @model_validator(mode="after")
    def validate_graph(self) -> WorkflowSpec:
        step_ids: set[str] = set()
        references: set[str] = set()

        def visit_value(value: ValueSource) -> None:
            if isinstance(value, StepOutputValue):
                references.add(value.step_id)

        def visit(step: Step) -> None:
            if step.id in step_ids:
                raise ValueError(f"duplicate step id: {step.id}")
            step_ids.add(step.id)

            if isinstance(step, AgentStep):
                visit_value(step.input)
            elif isinstance(step, SequenceStep):
                for child in step.steps:
                    visit(child)
            elif isinstance(step, ParallelStep):
                for child in step.branches:
                    visit(child)
            elif isinstance(step, MapStep):
                visit_value(step.items)
                visit(step.body)
            elif isinstance(step, ConditionStep):
                visit_value(step.value)
                visit(step.then)
                if step.otherwise:
                    visit(step.otherwise)
            else:
                visit(step.body)

        visit(self.root)
        if len(step_ids) > 100:
            raise ValueError("workflow exceeds the 100-step definition limit")
        if missing := references - step_ids:
            raise ValueError(f"unknown step output references: {sorted(missing)}")
        return self


SequenceStep.model_rebuild()
ParallelStep.model_rebuild()
MapStep.model_rebuild()
ConditionStep.model_rebuild()
RepeatStep.model_rebuild()
WorkflowSpec.model_rebuild()
