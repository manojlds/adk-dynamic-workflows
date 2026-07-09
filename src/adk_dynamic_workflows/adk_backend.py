"""Google ADK 2 execution adapter."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from google.adk.agents import BaseAgent, Context
from google.adk.workflow import START, Workflow, node

from .interpreter import AgentRequest, WorkflowInterpreter
from .spec import WorkflowSpec


class AdkAgentBackend:
    """Run interpreter agent calls as dynamically scheduled ADK nodes."""

    def __init__(self, ctx: Context, agents: Mapping[str, BaseAgent]) -> None:
        self._ctx = ctx
        self._agents = agents

    async def run_agent(self, request: AgentRequest) -> Any:
        try:
            agent = self._agents[request.agent]
        except KeyError as error:
            raise ValueError(f"unknown agent profile: {request.agent}") from error

        digest = hashlib.sha256(request.execution_id.encode()).hexdigest()[:20]
        return await self._ctx.run_node(
            agent,
            _render_agent_input(request),
            run_id=f"generated-{digest}",
            use_sub_branch=True,
        )


def build_adk_workflow(
    spec: WorkflowSpec,
    agents: Mapping[str, BaseAgent],
) -> Workflow:
    """Build an ADK Workflow that interprets a validated generated spec."""

    async def orchestrate(ctx: Context, node_input: Any) -> Any:
        backend = AdkAgentBackend(ctx, agents)
        return await WorkflowInterpreter(backend).execute(spec, node_input)

    adk_name = spec.name.replace("-", "_")
    orchestrator = node(
        orchestrate,
        name=f"{adk_name}_orchestrator",
        rerun_on_resume=True,
    )
    return Workflow(name=adk_name, edges=[(START, orchestrator)])


def _render_agent_input(request: AgentRequest) -> str:
    if request.input is None:
        return request.prompt
    serialized = json.dumps(request.input, sort_keys=True, default=str)
    return f"{request.prompt}\n\nInput:\n{serialized}"
