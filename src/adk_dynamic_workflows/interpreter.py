"""Deterministic interpreter for generated workflow specifications."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from typing import Any, Protocol, cast

from .spec import (
    AgentStep,
    ConditionStep,
    CurrentItemValue,
    LiteralValue,
    MapStep,
    ParallelStep,
    SequenceStep,
    Step,
    StepOutputValue,
    ValueSource,
    WorkflowSpec,
)


@dataclass(frozen=True, slots=True)
class AgentRequest:
    """One backend-independent agent invocation."""

    execution_id: str
    agent: str
    prompt: str
    input: Any


class AgentBackend(Protocol):
    async def run_agent(self, request: AgentRequest) -> Any:
        """Run one registered agent and return its structured result."""
        ...


@dataclass(slots=True)
class _ExecutionContext:
    workflow_input: Any
    outputs: dict[str, Any] = field(default_factory=lambda: dict[str, Any]())
    current_item: Any = None

    def fork(self, *, current_item: Any = None) -> _ExecutionContext:
        return replace(
            self,
            outputs=dict(self.outputs),
            current_item=current_item,
        )


class WorkflowInterpreter:
    """Execute the same spec against local ADK or durable Temporal backends."""

    def __init__(self, backend: AgentBackend) -> None:
        self._backend = backend

    async def execute(self, spec: WorkflowSpec, workflow_input: Any = None) -> Any:
        context = _ExecutionContext(workflow_input=workflow_input)
        return await self._execute_step(spec.root, context, (spec.name,))

    async def _execute_step(
        self,
        step: Step,
        context: _ExecutionContext,
        path: tuple[str, ...],
    ) -> Any:
        step_path = (*path, step.id)

        if isinstance(step, AgentStep):
            result = await self._backend.run_agent(
                AgentRequest(
                    execution_id="/".join(step_path),
                    agent=step.agent,
                    prompt=step.prompt,
                    input=self._resolve(step.input, context),
                )
            )
        elif isinstance(step, SequenceStep):
            result = None
            for child in step.steps:
                result = await self._execute_step(child, context, step_path)
        elif isinstance(step, ParallelStep):
            result = await asyncio.gather(
                *(
                    self._execute_step(child, context.fork(), step_path)
                    for child in step.branches
                )
            )
        elif isinstance(step, MapStep):
            result = await self._execute_map(step, context, step_path)
        elif isinstance(step, ConditionStep):
            branch = (
                step.then
                if self._resolve(step.value, context) == step.equals
                else step.otherwise
            )
            result = (
                await self._execute_step(branch, context.fork(), step_path)
                if branch
                else None
            )
        else:
            result_list: list[Any] = []
            for index in range(step.count):
                iteration_context = context.fork(current_item=index)
                result_list.append(
                    await self._execute_step(
                        step.body,
                        iteration_context,
                        (*step_path, str(index)),
                    )
                )
            result = result_list

        context.outputs[step.id] = result
        return result

    async def _execute_map(
        self,
        step: MapStep,
        context: _ExecutionContext,
        path: tuple[str, ...],
    ) -> list[Any]:
        items = self._resolve(step.items, context)
        if not isinstance(items, list):
            raise TypeError(
                f"map step {step.id!r} expected a list, got {type(items).__name__}"
            )
        typed_items = cast(list[Any], items)

        semaphore = asyncio.Semaphore(step.max_concurrency)

        async def execute_item(index: int, item: Any) -> Any:
            async with semaphore:
                return await self._execute_step(
                    step.body,
                    context.fork(current_item=item),
                    (*path, str(index)),
                )

        return await asyncio.gather(
            *(execute_item(index, item) for index, item in enumerate(typed_items))
        )

    @staticmethod
    def _resolve(source: ValueSource, context: _ExecutionContext) -> Any:
        if isinstance(source, LiteralValue):
            return source.value
        if isinstance(source, CurrentItemValue):
            return context.current_item
        if isinstance(source, StepOutputValue):
            try:
                return context.outputs[source.step_id]
            except KeyError as error:
                raise ValueError(
                    f"step output {source.step_id!r} is not available in this branch"
                ) from error
        value = context.workflow_input
        if source.key is None:
            return value
        if not isinstance(value, dict):
            raise TypeError("keyed workflow input requires an object")
        try:
            return cast(Any, value[source.key])
        except KeyError as error:
            raise ValueError(f"workflow input has no key {source.key!r}") from error
