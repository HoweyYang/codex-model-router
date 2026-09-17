---
name: codex-model-switch
description: Switch Codex between configured models and providers, add new provider or model-catalog targets, run one-off requests on a chosen model, and set up several models working together as custom agents. Use when the user wants to change which model Codex uses, add another model/API provider, or combine models in one task.
---

# Codex Model Switch

Codex picks one model and one provider per process. This skill makes that
choice a named, reversible target instead of something the user edits by hand.

Two artifacts, both under `$CODEX_HOME` (default `~/.codex`):

- `model-switch.json`  -  the registry: every target's model, provider, catalog, and extra keys.
- `config.toml`  -  holds one marked block that this skill owns. Everything outside the block is untouched.

Use `scripts/msw.py` (Python 3.8+, standard library only). Every write makes a
timestamped backup of `config.toml` first.

## Workflow

```bash
python scripts/msw.py list                       # targets, with the active one marked
python scripts/msw.py adopt <name>               # save the current config.toml settings as a target
python scripts/msw.py add <name> --model gpt-5.6-terra --provider openai \
    --catalog ~/.codex/models-openai.json --key forced_login_method=chatgpt
python scripts/msw.py test <name>                # one real request, no config change
python scripts/msw.py switch <name>              # make it the default
python scripts/msw.py run <name>                 # print a one-off `codex -c ...` command instead
python scripts/msw.py doctor                     # model / provider / auth / proxy lines
```

Prefer `test` before `switch`: it proves the target actually answers before the
user's default changes. Treat a target as working only after a real reply
comes back  -  config that parses is not config that connects.

## Rules that prevent real breakage

**Never put `forced_login_method = "api"` or `preferred_auth_method = "apikey"`
on a target that uses the built-in `openai` provider.** Codex resolves that
combination by logging the user out and deleting `auth.json`. It is a
credential-destroying setting, not a preference. Targets that need ChatGPT
sign-in should carry `forced_login_method = "chatgpt"` or omit the key.

**Give every provider its own `model_catalog_json`.** Without an entry for the
selected model, Codex logs `Model metadata for <slug> not found. Defaulting to
fallback metadata` and runs with wrong context limits. Build a catalog by
running `codex debug models` with that provider active and saving the JSON.

**Provider is global, profiles are not.** `switch` rewrites `config.toml`,
which the desktop app reads when it starts a chat  -  the app's model picker
cannot cross providers, so it needs this. `--profile` and `-c` only affect CLI
runs. When switching the default, tell the user to start a new chat, and to
restart the app if the old model persists.

**Network reachability is part of the switch.** If a target times out, run
`msw.py doctor` before touching config. Hosted OpenAI endpoints are unreachable
from some networks without a proxy; either set `HTTPS_PROXY`/`HTTP_PROXY` or add
`features.respect_system_proxy = true` to `config.toml` and turn the system
proxy on.

**Do not hand-edit the managed block.** Edit the registry through `msw.py add`
so targets stay consistent; a manual edit inside the block is overwritten on
the next switch.

## Several models on one task

Codex supports custom agents that carry their own model, reasoning effort, and
sandbox mode. `msw.py team` generates them from targets so a reviewer, an
explorer, and an implementer can run on different models.

Read [references/multi-model-teams.md](references/multi-model-teams.md) when the
user asks for models to work together, cross-check each other, or split a task.

## Supporting a new provider

1. Add the provider to `config.toml` under `[model_providers.<id>]` (base URL,
   `wire_api = "responses"`, and an auth method  -  `env_key` for an API key).
2. Produce a model catalog for it (`codex debug models` while it is active).
3. `msw.py add <name> --model <slug> --provider <id> --catalog <path>`.
4. `msw.py test <name>`, then `msw.py switch <name>`.

Only the `openai`, `ollama`, and `lmstudio` provider ids are reserved; custom
providers need `wire_api = "responses"`.
