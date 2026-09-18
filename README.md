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
      "auth": "passthrough",
      "proxy": "system"
    },
    {
      "name": "deepseek",
      "match": ["deepseek"],
      "upstream": "https://api.deepseek.com/v1/responses",
      "auth": { "provider": "deepseek" },
      "proxy": "direct"
    }
  ]
}
```

Each route also decides its own proxy behaviour. Letting every route inherit the
system proxy means a regional API dies whenever the proxy restarts — which looks
like the router being broken while it is only the proxy blipping.

| Value | Meaning |
| --- | --- |
| `"system"` | Follow the OS proxy settings. Use this for the ChatGPT route |
| `"direct"` | Never use a proxy. Use this for directly reachable regional APIs |
| `"http://host:port"` | Use that proxy explicitly |

On many networks `chatgpt.com` is unreachable without a proxy while
`api.deepseek.com` is reachable directly, so those two routes want opposite
settings. With `"direct"` on the DeepSeek route, DeepSeek keeps working while
the VPN is off; GPT still needs the VPN, because that is a network fact, not a
router limitation.

**This whole proxy discussion only applies to networks where OpenAI is blocked —
mainland China being the main one.** Where OpenAI is directly reachable, set
every route to `"direct"` and ignore the proxy column entirely: no VPN, no
system proxy, no `"system"` value anywhere.

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

Then run **once** to tie the router to Codex's lifecycle — it registers
`mcp-autostart.py` as a no-tool MCP server. Codex launches its MCP servers
when it starts, so the router comes up with Codex and nothing is left running
after you close it. No logon task, no Startup folder, no separate process to
forget about:

```powershell
.\install-mcp-autostart.ps1    # add the hook to config.toml, then restart Codex
.\uninstall-mcp-autostart.ps1  # remove the hook
```

The hook exposes no tools; its only job is to be launched. It makes sure the
router is listening, then idles on stdin until Codex exits. Skip this if you
would rather start `.\start-router.ps1` by hand each session.

On macOS or Linux, `mcp-autostart.py` works the same way through Codex's MCP
config; the two `.ps1` files are just the Windows helpers for editing
`config.toml`.

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
- **Changing the provider does not change existing chats.** A chat binds its
  provider when it is created, and the model picker only changes the model name.
  Pick a model from another backend inside an old chat and the request still goes
  to that chat's original provider, which is why you can see
  `The supported API model names are deepseek-flash, deepseek-v4-pro, but you
  passed gpt-5.6-terra` after choosing GPT in a chat created while DeepSeek was
  the default. **Start a new chat** after changing the provider or pointing
  Codex at the router.


- **It is a resident process.** If the router is down, Codex cannot reach that
  provider. Switching the default back to a direct provider restores service.
- **The GPT route rides on a private endpoint** (`chatgpt.com/backend-api/codex`).
  A Codex update could change it. This is the one long-term fragile part; the
  API-key routes are not affected.
- The catalog is only a list. A wrong slug shows up in the picker and fails at
  request time.

## Troubleshooting

**Codex shows `Reconnecting... waiting for network` / `Connection failed: error
sending request`.** Almost always this means the router itself is not running —
Codex cannot reach `127.0.0.1:8765`, and that refused connection is what it
mislabels as a network problem. Run `.\start-router.ps1` (or just restart
Codex if you used `install-mcp-autostart.ps1`). If it still will not listen,
the last lines of `~/.codex/model-router.log` tell you why (busy port, missing
config, ...).

**Picking a model from another backend throws the old provider's error.** A chat
binds its provider when it is created, and the model picker only changes the
model name. Start a new chat.

To confirm which provider a chat is bound to, read the first line of its session
file under `~/.codex/sessions/` and look at `model_provider`. The router log
(`~/.codex/model-router.log`) shows whether a request ever reached the router: if
the model you picked never appears there, it went straight to another provider.

**The picker still lists the old models after a config change.** The desktop app
reads config at startup. Restart it.

**Requests hang or time out.** Check the router is alive:

```powershell
Invoke-WebRequest http://127.0.0.1:8765/ -UseBasicParsing
```

It should return `{"status": "ok", "routes": [...]}`. If it does and the model is
a hosted OpenAI one, the problem is your network: `codex doctor` prints the
reachability lines, and `features.respect_system_proxy = true` lets Codex use a
system proxy.

**`Model metadata for <slug> not found`.** That slug is missing from the catalog
`model_catalog_json` points at. Re-run `tools/merge-catalogs.py`, then restart the
app.

**Commands are rejected with `apply deny-read ACLs`.** That is a Codex sandbox
provisioning failure on Windows, unrelated to this router. `codex doctor` reports
it as `elevated Windows sandbox provisioning recorded a structured failure`.

## License

MIT
