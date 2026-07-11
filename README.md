# ADK Dynamic Workflows

[![CI](https://github.com/manojlds/adk-dynamic-workflows/actions/workflows/ci.yml/badge.svg)](https://github.com/manojlds/adk-dynamic-workflows/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/adk-dynamic-workflows.svg)](https://pypi.org/project/adk-dynamic-workflows/)

Model-generated, validated workflows that can execute against Google ADK 2 or
Temporal without evaluating arbitrary generated Python.

This project is an early bootstrap. The implemented vertical slice includes:

- A strict, versioned `WorkflowSpec` suitable for structured LLM output
- An ADK planner agent backed by LiteLLM structured output
- Agent, sequence, parallel, map, condition, and bounded-repeat steps
- Stable execution IDs for replay and caching
- A backend-neutral asynchronous interpreter
- An ADK 2 adapter built on `Context.run_node()`
- A Temporal adapter that dispatches agent calls as child workflows

## Install

```bash
uv sync
```

Install the Temporal adapter dependencies when needed:

```bash
uv sync --extra temporal
```

The official `temporalio[google-adk]` extra currently requires
`google-adk<2`. This project therefore uses Temporal's core SDK and leaves the
ADK 2 child-workflow implementation as the next integration milestone.

## Validate A Workflow

```bash
uv run adk-dynamic-workflows validate examples/review.json
```

## Generate A Workflow With LiteLLM

Edit the gitignored `.env` file with your OpenAI or OpenAI-compatible provider:

```dotenv
DYNAMIC_WORKFLOWS_LLM_MODEL=openai/gpt-4o-mini
DYNAMIC_WORKFLOWS_LLM_API_BASE=https://api.openai.com/v1
DYNAMIC_WORKFLOWS_LLM_API_KEY=replace-with-your-api-key
```

For a compatible gateway, retain LiteLLM's `openai/` model prefix and replace
the model name and base URL with values supported by that gateway.

Generate, review, approve, and save a workflow:

```bash
uv run adk-dynamic-workflows plan \
  "Review every file provided in the files input" \
  --agent-profile explorer \
  --agent-profile reviewer \
  --output generated-review.json
```

The planner uses ADK `LlmAgent.output_schema` to request a `WorkflowSpec`, then
validates the result locally. It retries once with validation feedback when the
provider returns a structurally invalid workflow. The generated workflow may
only reference profiles passed through `--agent-profile`.

## Execute Locally

Register the agent profiles that a generated spec is allowed to invoke, then
build a normal ADK workflow:

```python
from adk_dynamic_workflows.adk_backend import build_adk_workflow
from adk_dynamic_workflows.spec import WorkflowSpec

spec = WorkflowSpec.model_validate_json(open("examples/review.json").read())
root_agent = build_adk_workflow(
    spec,
    {
        "reviewer": reviewer_agent,
    },
)
```

The allowlisted registry is intentional: generated workflows select an agent
profile but cannot create unrestricted agents or grant themselves new tools.

## Development

```bash
uv run ruff format --check .
uv run ruff check .
uv run pyright
uv run pytest
```

Run the real LiteLLM integration test after configuring `.env`:

```bash
uv run pytest -m integration tests/integration/test_litellm_planner.py
```

With placeholder credentials the integration test is skipped. With configured
credentials it performs a real provider request and verifies that the returned
workflow is valid and uses only the requested agent profile.

## Next Milestones

1. Implement an ADK 2-compatible Temporal child workflow for one agent run.
2. Add budget estimates, progress queries, and cancellation.
3. Store large outputs as artifact references instead of workflow-history data.
4. Add semantic validation for branch scope and step-output dominance.
