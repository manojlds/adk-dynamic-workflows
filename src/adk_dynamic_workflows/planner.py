"""LLM planner that turns natural language into a validated workflow spec."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from uuid import uuid4

from google.adk.agents import LlmAgent
from google.adk.events import Event
from google.adk.models.base_llm import BaseLlm
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from pydantic import ValidationError

from .spec import WorkflowSpec

_PLACEHOLDER_API_KEYS = {"", "replace-with-your-api-key"}


@dataclass(frozen=True, slots=True)
class PlannerConfig:
    """OpenAI-compatible LiteLLM connection settings."""

    model: str
    api_base: str
    api_key: str

    @classmethod
    def from_env(cls) -> PlannerConfig:
        return cls(
            model=os.getenv("DYNAMIC_WORKFLOWS_LLM_MODEL", "openai/gpt-4o-mini"),
            api_base=os.getenv(
                "DYNAMIC_WORKFLOWS_LLM_API_BASE", "https://api.openai.com/v1"
            ),
            api_key=os.getenv("DYNAMIC_WORKFLOWS_LLM_API_KEY", ""),
        )

    def build_model(self) -> LiteLlm:
        if self.api_key in _PLACEHOLDER_API_KEYS:
            raise ValueError(
                "Set DYNAMIC_WORKFLOWS_LLM_API_KEY in .env before planning"
            )
        return LiteLlm(
            model=self.model,
            api_base=self.api_base,
            api_key=self.api_key,
            drop_params=True,
        )


class WorkflowPlanner:
    """Generate and validate a workflow using an allowlisted set of agents."""

    def __init__(
        self,
        *,
        model: BaseLlm,
        agent_profiles: list[str],
        max_attempts: int = 2,
    ) -> None:
        if not agent_profiles:
            raise ValueError("at least one agent profile is required")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._model = model
        self._agent_profiles = tuple(sorted(set(agent_profiles)))
        self._max_attempts = max_attempts

    async def plan(self, request: str) -> WorkflowSpec:
        """Generate a spec, retrying with validation feedback when possible."""

        if not request.strip():
            raise ValueError("workflow request cannot be empty")

        feedback: str | None = None
        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                events = await self._run_agent(request, feedback, attempt)
                return _extract_spec(events)
            except Exception as error:
                last_error = error
                feedback = str(error)

        raise RuntimeError(
            f"planner failed after {self._max_attempts} attempts: {last_error}"
        ) from last_error

    async def _run_agent(
        self,
        request: str,
        feedback: str | None,
        attempt: int,
    ) -> list[Event]:
        agent = LlmAgent(
            name="workflow_planner",
            model=self._model,
            instruction=_planner_instruction(self._agent_profiles),
            output_schema=WorkflowSpec,
            include_contents="none",
        )
        runner = InMemoryRunner(agent=agent, app_name="adk_dynamic_workflows")
        prompt = request
        if feedback:
            prompt = (
                f"{request}\n\n"
                "The previous generated workflow was rejected. Correct this error:\n"
                f"{feedback}"
            )
        try:
            return await runner.run_debug(
                prompt,
                user_id="planner",
                session_id=f"plan-{attempt}-{uuid4().hex}",
                quiet=True,
            )
        finally:
            await runner.close()


def planner_from_config(
    config: PlannerConfig,
    *,
    agent_profiles: list[str],
    max_attempts: int = 2,
) -> WorkflowPlanner:
    return WorkflowPlanner(
        model=config.build_model(),
        agent_profiles=agent_profiles,
        max_attempts=max_attempts,
    )


def _planner_instruction(agent_profiles: tuple[str, ...]) -> str:
    profiles = ", ".join(agent_profiles)
    return f"""You design safe agent workflows from user requests.

Return only a WorkflowSpec matching the required structured output schema.
You may invoke only these registered agent profiles: {profiles}.

Design rules:
- Use sequence when a later step consumes an earlier step's output.
- Use parallel only for independent branches.
- Use map when an agent should process every item in a runtime list.
- Use current_item as the input to a map body.
- Use step_output only when the referenced step has already completed in the
  same sequence scope.
- Keep repeat counts small and never exceed the schema limits.
- Use stable, descriptive kebab-case IDs.
- The workflow must accomplish the request without inventing unavailable agents.
"""


def _extract_spec(events: list[Event]) -> WorkflowSpec:
    for event in reversed(events):
        if event.author != "workflow_planner" or not event.is_final_response():
            continue
        if event.output is not None:
            return WorkflowSpec.model_validate(event.output)
        text = _event_text(event)
        if text:
            return parse_spec_response(text)
    raise RuntimeError("planner returned no structured final response")


def _event_text(event: Event) -> str:
    if not event.content or not event.content.parts:
        return ""
    return "".join(
        part.text for part in event.content.parts if isinstance(part.text, str)
    )


def parse_spec_response(text: str) -> WorkflowSpec:
    """Parse strict JSON or a valid JSON object embedded in provider prose."""

    try:
        return WorkflowSpec.model_validate_json(text)
    except ValidationError as strict_error:
        decoder = json.JSONDecoder()
        last_error: Exception = strict_error
        for index, character in enumerate(text):
            if character != "{":
                continue
            try:
                value, _ = decoder.raw_decode(text, index)
                return WorkflowSpec.model_validate(value)
            except (json.JSONDecodeError, ValidationError, ValueError) as error:
                last_error = error
        raise ValueError(
            "planner response contains no valid WorkflowSpec"
        ) from last_error
