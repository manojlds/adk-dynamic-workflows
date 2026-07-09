"""Temporal backend for the generic workflow interpreter.

This adapter intentionally depends only on Temporal's core SDK. The published
``temporalio[google-adk]`` extra currently requires Google ADK 1.x, while this
project targets ADK 2.x. Applications must register an ADK 2-compatible child
workflow under ``child_workflow_name``.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
from typing import Any

from temporalio import workflow

from .interpreter import AgentRequest


class TemporalAgentBackend:
    """Run each generated agent call as an isolated Temporal child workflow."""

    def __init__(
        self,
        *,
        task_queue: str,
        child_workflow_name: str = "AdkAgentWorkflow",
        execution_timeout: timedelta = timedelta(hours=1),
    ) -> None:
        self._task_queue = task_queue
        self._child_workflow_name = child_workflow_name
        self._execution_timeout = execution_timeout

    async def run_agent(self, request: AgentRequest) -> Any:
        return await workflow.execute_child_workflow(
            self._child_workflow_name,
            asdict(request),
            id=request.execution_id.replace("/", "--"),
            task_queue=self._task_queue,
            execution_timeout=self._execution_timeout,
        )
