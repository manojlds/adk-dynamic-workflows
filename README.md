# ADK Dynamic Workflows

Model-generated, validated workflows that can execute against Google ADK 2 or
Temporal without evaluating arbitrary generated Python.

This project is an early bootstrap. The implemented vertical slice includes:

- A strict, versioned `WorkflowSpec` suitable for structured LLM output
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

## Next Milestones

1. Add an ADK planner that emits `WorkflowSpec` via structured output.
2. Implement an ADK 2-compatible Temporal child workflow for one agent run.
3. Add workflow approval, budgets, progress queries, and cancellation.
4. Store large outputs as artifact references instead of workflow-history data.
