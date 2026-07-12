from __future__ import annotations

import os
from collections.abc import AsyncGenerator
from contextlib import aclosing, asynccontextmanager
from datetime import timedelta
from uuid import uuid4

import pytest
from google.adk.agents import Agent
from google.adk.models import BaseLlm, LLMRegistry
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import InMemoryRunner
from google.genai import types
from google.genai.types import Content, Part
from temporalio import workflow
from temporalio.client import Client
from temporalio.contrib.google_adk_agents import GoogleAdkPlugin, TemporalModel
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker


class CannedAdk2Model(BaseLlm):
    """Deterministic model used to prove the ADK call crosses an Activity."""

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["compat/adk2"]

    async def generate_content_async(
        self,
        llm_request: LlmRequest,
        stream: bool = False,
    ) -> AsyncGenerator[LlmResponse, None]:
        del llm_request, stream
        yield LlmResponse(
            content=Content(
                role="model",
                parts=[Part(text="ADK 2 ran through Temporal")],
            )
        )


@workflow.defn
class Adk2CompatibilityWorkflow:
    @workflow.run
    async def run(self, prompt: str) -> str:
        agent = Agent(
            name="compatibility_agent",
            model=TemporalModel("compat/adk2"),
        )
        runner = InMemoryRunner(agent=agent, app_name="adk2_compatibility")
        session = await runner.session_service.create_session(
            app_name="adk2_compatibility",
            user_id="integration-test",
        )

        result = ""
        async with aclosing(
            runner.run_async(
                user_id="integration-test",
                session_id=session.id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part(text=prompt)],
                ),
            )
        ) as events:
            async for event in events:
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            result = part.text
        return result


@pytest.mark.integration
async def test_official_temporal_adapter_runs_adk2_workflow() -> None:
    if not os.getenv("TEMPORAL_ADDRESS") and not os.getenv("TEMPORAL_USE_TEST_SERVER"):
        pytest.skip("set TEMPORAL_ADDRESS or TEMPORAL_USE_TEST_SERVER=1 to run")
    LLMRegistry.register(CannedAdk2Model)

    async with _temporal_client() as client:
        task_queue = f"adk2-compatibility-{uuid4()}"

        async with Worker(
            client,
            task_queue=task_queue,
            workflows=[Adk2CompatibilityWorkflow],
            max_cached_workflows=0,
        ):
            result = await client.execute_workflow(
                Adk2CompatibilityWorkflow.run,
                "Confirm compatibility",
                id=f"adk2-compatibility-{uuid4()}",
                task_queue=task_queue,
                execution_timeout=timedelta(seconds=30),
            )

    assert result == "ADK 2 ran through Temporal"


@asynccontextmanager
async def _temporal_client() -> AsyncGenerator[Client, None]:
    if address := os.getenv("TEMPORAL_ADDRESS"):
        yield await Client.connect(address, plugins=[GoogleAdkPlugin()])
        return

    async with await WorkflowEnvironment.start_time_skipping() as environment:
        client_config = environment.client.config()
        client_config["plugins"] = [GoogleAdkPlugin()]
        yield Client(**client_config)
