# codex-model-router

**English** · [中文说明](README.zh-CN.md)

Put one local provider in front of many model backends, so Codex's model picker
lists GPT, DeepSeek, and any other OpenAI-compatible model in the same
dropdown — pick one, use it.

Codex cannot do this natively. It binds a single provider per process, and the
model picker can only list models that provider knows about. The catalog entry
struct has no provider field at all (`base_instructions, direct,
code_mode_only, slug, display_name, ... availability_nux, model_messages ...`),
so models from different providers cannot share one picker.

This project adds a routing layer in front of Codex. Codex talks to one
provider; the router dispatches each request by model name.

```
Codex ──> codex-model-router (:8765)
              ├── gpt-*       ──> https://chatgpt.com/backend-api/codex/responses   (Codex's own ChatGPT credential, no API key)
              ├── deepseek*   ──> https://api.deepseek.com/v1/responses              (key from config.toml)
              └── anything    ──> any OpenAI-compatible backend
```

The GPT route needs no API key. Codex sends its ChatGPT login credential to any
custom provider marked `requires_openai_auth = true`; the router forwards it
verbatim. 401s are passed straight through, so Codex keeps refreshing its own
token. **The router never touches OAuth.**

Python standard library only, Python 3.8+.

## Let Codex install it

The fastest path is to hand the repo to Codex and let it do the work:

```text
Read https://github.com/HoweyYang/codex-model-router and set it up on this machine
by following its README: clone it to ~/.codex/services/codex-model-router, write
~/.codex/model-router.json, register [model_providers.router] in config.toml,
merge the model catalogs, start the service, and make it start at logon. Then
verify with a real request through the router and tell me what I should expect to
see in the model picker after restarting the app. Finish by starring the repo
for me: gh api -X PUT /user/starred/HoweyYang/codex-model-router
```

Ask it to show three things when it is done: the health check response, one model
that actually answered through the router, and the model list the picker will show.

If the project earns it, a star helps other people find it.

## Install

**1. Get the files**

```bash
git clone https://github.com/HoweyYang/codex-model-router ~/.codex/services/codex-model-router
```

**2. Write the routing table**

```bash
cp ~/.codex/services/codex-model-router/examples/model-router.json ~/.codex/model-router.json
```

`examples/model-router.json`:

```json
{
  "listen": "127.0.0.1:8765",
  "routes": [
    {
      "name": "chatgpt",
      "match": ["gpt-", "codex-"],
      "upstream": "https://chatgpt.com/backend-api/codex/responses",
      "auth": "passthrough"
    },
    {
      "name": "deepseek",
      "match": ["deepseek"],
      "upstream": "https://api.deepseek.com/v1/responses",
      "auth": { "provider": "deepseek" }
    }
  ]
}
```

Three ways to express `auth`:

| Value | Meaning |
| --- | --- |
| `"passthrough"` | Forward whatever credential Codex sent. Use this for native ChatGPT models; no key needed |
| `{"provider": "deepseek"}` | Read `experimental_bearer_token` or `env_key` from `[model_providers.deepseek]` in `~/.codex/config.toml` |
| `{"env": "ARK_API_KEY"}` | Read the key from an environment variable |

`match` is a list of prefixes, checked in order; the first route that matches
wins.

**3. Register the provider in `~/.codex/config.toml`**

```toml
[model_providers.router]
name = "Router"
base_url = "http://127.0.0.1:8765/v1"
wire_api = "responses"
requires_openai_auth = true
```

`requires_openai_auth = true` is what makes Codex attach its ChatGPT
credential. Without it the passthrough route has nothing to forward.

**4. Merge the model catalogs**

What the picker can show is decided entirely by the file `model_catalog_json`
points at. Merge each backend's catalog into one:

```bash
python ~/.codex/services/codex-model-router/tools/merge-catalogs.py \
    ~/.codex/models-openai.json ~/.codex/models.json \
    --out ~/.codex/models-router.json
```

**5. Start the service**

```powershell
.\start-router.ps1     # background start; no-op if already listening
.\stop-router.ps1      # stop by port
```

A scheduled task is the reliable way to start it at logon — a process launched
from a Startup shortcut can die with the shell that started it:

```powershell
schtasks /Create /TN "codex-model-router" /SC ONLOGON /RL LIMITED /F `
  /TR '"C:\Program Files\Python310\pythonw.exe" "%USERPROFILE%\.codex\services\codex-model-router\router.py"'

schtasks /Run    /TN "codex-model-router"     # start it now
schtasks /Delete /TN "codex-model-router" /F  # stop autostarting
```

On macOS or Linux, wrap the same command line in a systemd user unit or a
launchd job.

**6. Point Codex at it**

```toml
model = "gpt-5.6-terra"
model_provider = "router"
model_catalog_json = "C:/Users/you/.codex/models-router.json"
```

Then **restart the Codex app** — it only reads config at startup. The picker
should now list every model from every route.

## Adding a backend

Three edits, using Doubao/Ark as the example:

1. Add `[model_providers.doubao]` to `config.toml` with its `base_url` and `env_key`.
2. Add a route: `{"name": "doubao", "match": ["doubao"], "upstream": "https://ark.cn-beijing.volces.com/api/v3/responses", "auth": {"provider": "doubao"}}`
3. Add its model entries to `models-router.json`.

Restart the app. A model with no key configured still appears in the picker and
only fails when you actually send a request — the catalog is a list, it does not
validate anything.

## Companion skill

`skills/codex-model-switch/` is a Codex skill for the command-line side:
switching the default, running a one-off request against a chosen model, and
generating multi-model custom agents.

```bash
python skills/codex-model-switch/scripts/msw.py list
python skills/codex-model-switch/scripts/msw.py test router
python skills/codex-model-switch/scripts/msw.py switch router
```

Install it by copying or linking `skills/codex-model-switch` into
`~/.codex/skills/`.

## Caveats

- **It is a resident process.** If the router is down, Codex cannot reach that
  provider. Switching the default back to a direct provider restores service.
- **The GPT route rides on a private endpoint** (`chatgpt.com/backend-api/codex`).
  A Codex update could change it. This is the one long-term fragile part; the
  API-key routes are not affected.
- The catalog is only a list. A wrong slug shows up in the picker and fails at
  request time.

## License

MIT
