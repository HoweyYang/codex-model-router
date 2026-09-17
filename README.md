# codex-model-router

让 Codex 右下角的模型选择器里**同时**出现 GPT、DeepSeek 以及其他任何 OpenAI 兼容后端，点谁用谁。

Codex 原生做不到这件事：每个进程只能绑定一个供应商，选择器只能列出该供应商认识的模型。模型目录的字段表里没有 provider（`base_instructions, direct, code_mode_only, slug, display_name, ... availability_nux, model_messages ...`），所以跨供应商的模型塞不进同一个选择器。

这个项目在 Codex 前面加一层本地路由，让 Codex 只认一个供应商，由路由器按模型名分发到各家。

```
Codex ──> codex-model-router (:8765)
              ├── gpt-*       ──> https://chatgpt.com/backend-api/codex/responses   （透传 Codex 自带的 ChatGPT 凭据，不需要 key）
              ├── deepseek*   ──> https://api.deepseek.com/v1/responses              （用 config.toml 里的 key）
              └── 其他         ──> 任意 OpenAI 兼容后端
```

GPT 那条之所以不用配 key：Codex 会把 ChatGPT 登录凭据发给自定义供应商（前提是供应商标了 `requires_openai_auth = true`），路由器原样转发即可，连 401 也原样透传，让 Codex 自己刷新 token。**路由器不碰 OAuth。**

只依赖 Python 标准库，Python 3.8+。

## 安装

**1. 放文件**

```bash
git clone https://github.com/HoweyYang/codex-model-router ~/.codex/services/codex-model-router
```

**2. 写路由表**

```bash
cp ~/.codex/services/codex-model-router/examples/model-router.json ~/.codex/model-router.json
```

`examples/model-router.json` 长这样：

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

`auth` 三种写法：

| 写法 | 含义 |
| --- | --- |
| `"passthrough"` | 原样转发 Codex 带来的凭据。ChatGPT 原生模型用这个，不需要 key |
| `{"provider": "deepseek"}` | 从 `~/.codex/config.toml` 的 `[model_providers.deepseek]` 里读 `experimental_bearer_token` 或 `env_key` |
| `{"env": "ARK_API_KEY"}` | 从环境变量读 key |

**3. 在 `~/.codex/config.toml` 里注册供应商**

```toml
[model_providers.router]
name = "Router"
base_url = "http://127.0.0.1:8765/v1"
wire_api = "responses"
requires_openai_auth = true
```

**4. 生成合并后的模型目录**

选择器里能列出什么，完全由 `model_catalog_json` 指向的文件决定。把各家的目录合成一份：

```bash
python ~/.codex/services/codex-model-router/tools/merge-catalogs.py \
    ~/.codex/models-openai.json ~/.codex/models.json \
    --out ~/.codex/models-router.json
```

**5. 启动**

```powershell
.\start-router.ps1     # 后台启动，已经在跑就不重复启动
.\stop-router.ps1      # 按端口停掉
```

开机自启用计划任务最稳（Windows 上用 Startup 快捷方式启动的进程可能随启动它的 shell 一起退出）：

```powershell
schtasks /Create /TN "codex-model-router" /SC ONLOGON /RL LIMITED /F `
  /TR '"C:\Program Files\Python310\pythonw.exe" "%USERPROFILE%\.codex\services\codex-model-router\router.py"'

schtasks /Run    /TN "codex-model-router"   # 立刻起一次
schtasks /Delete /TN "codex-model-router" /F # 不再自启
```

macOS / Linux 用 systemd user unit 或 launchd，把同样的命令行包一层即可。

**6. 让 Codex 用它**

```toml
model = "gpt-5.6-terra"
model_provider = "router"
model_catalog_json = "C:/Users/you/.codex/models-router.json"
```

改完**重启 Codex App**（App 只在启动时读配置）。右下角应该就能看到全部模型了。

## 加一个新后端

以豆包为例，三步：

1. `config.toml` 加 `[model_providers.doubao]`，写好 `base_url` 和 `env_key`
2. `model-router.json` 的 `routes` 加一条：`{"name": "doubao", "match": ["doubao"], "upstream": "https://ark.cn-beijing.volces.com/api/v3/responses", "auth": {"provider": "doubao"}}`
3. 把豆包的模型条目加进 `models-router.json`

重启 App。没有 key 的模型照样能出现在选择器里，只是选中后发请求会失败——目录不校验真实性。

## 配套技能

`skills/codex-model-switch/` 是一个 Codex 技能，负责命令行侧的切换、给指定模型跑一次性请求、以及生成多模型协作的 custom agent：

```bash
python skills/codex-model-switch/scripts/msw.py list
python skills/codex-model-switch/scripts/msw.py test router
python skills/codex-model-switch/scripts/msw.py switch router
```

装技能：把 `skills/codex-model-switch` 复制或软链到 `~/.codex/skills/` 下。

## 已知限制

- **它是个常驻进程。** 路由器挂了，Codex 就走不通——把默认改回直连供应商即可恢复。
- **GPT 那条走的是 Codex 的私有接口**（`chatgpt.com/backend-api/codex`）。Codex 升级有可能改掉它，这是整个方案唯一长期脆弱的地方。API key 路线没有这个问题。
- 模型目录只是清单，**不校验模型是否真实存在**。写错了要等发请求才报错。

## English

Codex binds one provider per process and its model picker can only list models that provider knows about, so GPT and DeepSeek can never share one picker natively. This router puts a single provider in front of Codex and dispatches each request by model name.

The GPT route needs no API key: Codex sends its ChatGPT credential to any custom provider marked `requires_openai_auth = true`, and the router forwards it verbatim (401s included, so Codex keeps refreshing its own token).

Install: clone, copy `examples/model-router.json` to `~/.codex/model-router.json`, register `[model_providers.router]` in `config.toml`, merge your catalogs with `tools/merge-catalogs.py`, start the service, restart the Codex app. Adding another backend is three edits.

Caveats: a resident process is required, and the ChatGPT route rides on a private endpoint that a Codex update could change.

## License

MIT
