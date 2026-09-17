# Multi-model teams

Codex can run subagents alongside the main thread, and each subagent can carry
its own model. That is the mechanism for putting two or more models on one
task: a strong model reviews while a cheap one explores, or two models
independently answer the same question so the parent can compare.

## Global settings

Under `[agents]` in `config.toml`:

| Field | Purpose |
| --- | --- |
| `enabled` | Turns the multi-agent tools on or off. Defaults to `true`. |
| `max_concurrent_threads_per_session` | Cap on simultaneous spawned threads. |
| `default_subagent_model` | Model for spawned agents when nothing else selects one. |
| `default_subagent_reasoning_effort` | Matching default effort. |
| `interrupt_message` | Whether an interrupted agent's turn leaves a message in context. |

`msw.py team init --max-threads 6` adds this table if it is missing. It never
rewrites an `[agents]` table that already exists.

## Custom agents

One TOML file per agent, in `~/.codex/agents/` for personal agents or
`.codex/agents/` for project-scoped ones.

Required fields: `name`, `description`, `developer_instructions`.

The file is loaded as a configuration layer, so it also accepts other
`config.toml` keys — `model`, `model_reasoning_effort`, `sandbox_mode`,
`model_provider`, `mcp_servers`, `skills.config`. A file that sets `model`
wins over the value resolved from the spawn request or the `[agents]` default.
A `model` without a `model_reasoning_effort` keeps the previously resolved
effort, which can be wrong for the new model — set both together.

Codex ships `default`, `worker`, and `explorer`. A custom agent with one of
those names takes precedence over the built-in.

Generate them from existing targets:

```bash
python scripts/msw.py team init --max-threads 6
python scripts/msw.py team add reviewer --target gpt --effort high \
    --description "Independent reviewer on a second model" \
    --instructions "Review like an owner. Lead with concrete findings and reproduction steps."
python scripts/msw.py team add scout --target deepseek --effort high
python scripts/msw.py team list
```

## Cross-provider teammates: verify before promising

The documentation states that a custom agent file may include other supported
`config.toml` keys, and the restriction that drops provider keys applies only
to project-local `.codex/config.toml`. So `model_provider` in a user-level
agent file is expected to work and is what `msw.py team add` writes.

It is not spelled out explicitly, so verify it once with a real delegated run
before relying on it. If a cross-provider teammate fails, the safe fallback is
to keep the team inside one provider and switch targets between runs — run one
pass on the deep model, switch, and run the review pass on the other.

## Asking for the team

Naming the agents in the request is what makes delegation reliable:

```text
Review this branch against main. Have scout map the affected code paths, then
have reviewer find correctness, security, and test gaps. Wait for both, then
summarize findings by severity with file references.
```

Two habits keep this useful rather than expensive: give each agent a narrow
job, and ask each one to return a summary rather than raw output. Every agent
does its own model work, so a team costs more tokens than a single run.
