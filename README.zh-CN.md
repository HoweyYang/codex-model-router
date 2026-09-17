# codex-model-router

[English](README.md) · **中文说明**

在 Codex 前面加一层本地路由，让右下角的模型选择器里**同时**出现 GPT、DeepSeek
以及其他任何 OpenAI 兼容模型——点谁用谁。

Codex 原生做不到这件事。它每个进程只能绑定一个供应商，选择器只能列出该供应商认识的
模型；而且模型目录的结构体里根本没有 provider 字段
（`base_instructions, direct, code_mode_only, slug, display_name, ... availability_nux, model_messages ...`）。
所以不同供应商的模型塞不进同一个选择器。

这个项目让 Codex 只认一个供应商，由路由器按模型名把请求分发到各家：

```
Codex ──> codex-model-router (:8765)
              ├── gpt-*       ──> https://chatgpt.com/backend-api/codex/responses   （透传 Codex 自带的 ChatGPT 凭据，不需要 key）
              ├── deepseek*   ──> https://api.deepseek.com/v1/responses              （从 config.toml 读 key）
              └── 其他         ──> 任意 OpenAI 兼容后端
```

GPT 那条之所以不用配 key：Codex 会把 ChatGPT 登录凭据发给自定义供应商（前提是供应商
标了 `requires_openai_auth = true`），路由器原样转发即可；401 也原样透传，让 Codex
自己刷新 token。**路由器不碰 OAuth。**

只用 Python 标准库，需要 Python 3.8+。

## 让 Codex 自己装

最省事的用法：把仓库地址丢给 Codex，让它读 README 并照着做。

```text
读一下 https://github.com/HoweyYang/codex-model-router ，按它的说明在我这台机器上装好：
克隆到 ~/.codex/services/codex-model-router、写 ~/.codex/model-router.json、
在 config.toml 注册 [model_providers.router]、合并模型目录、启动服务并设置开机自启。
装完用真实请求走一遍路由器验证，再告诉我重启 App 后右下角应该看到什么。
```

收尾让它给你三样东西：健康检查的返回、一个真正跑通的模型、以及选择器里会出现的模型清单。

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

`auth` 有三种写法：

| 写法 | 含义 |
| --- | --- |
| `"passthrough"` | 原样转发 Codex 带来的凭据。ChatGPT 原生模型用这个，不需要 key |
| `{"provider": "deepseek"}` | 从 `~/.codex/config.toml` 的 `[model_providers.deepseek]` 读 `experimental_bearer_token` 或 `env_key` |
| `{"env": "ARK_API_KEY"}` | 从环境变量读 key |

`match` 是前缀列表，按顺序匹配，第一条命中的路由生效。

**3. 在 `~/.codex/config.toml` 里注册供应商**

```toml
[model_providers.router]
name = "Router"
base_url = "http://127.0.0.1:8765/v1"
wire_api = "responses"
requires_openai_auth = true
```

`requires_openai_auth = true` 是让 Codex 带上 ChatGPT 凭据的关键。少了它，
passthrough 那条路由就没有东西可转发。

**4. 合并模型目录**

选择器能列出什么，完全由 `model_catalog_json` 指向的文件决定。把各家的目录合成一份：

```bash
python ~/.codex/services/codex-model-router/tools/merge-catalogs.py \
    ~/.codex/models-openai.json ~/.codex/models.json \
    --out ~/.codex/models-router.json
```

**5. 启动服务**

```powershell
.\start-router.ps1     # 后台启动，已经在跑就不重复启动
.\stop-router.ps1      # 按端口停掉
```

开机自启用计划任务最稳——从 Startup 快捷方式启动的进程可能随启动它的 shell 一起退出：

```powershell
schtasks /Create /TN "codex-model-router" /SC ONLOGON /RL LIMITED /F `
  /TR '"C:\Program Files\Python310\pythonw.exe" "%USERPROFILE%\.codex\services\codex-model-router\router.py"'

schtasks /Run    /TN "codex-model-router"     # 立刻起一次
schtasks /Delete /TN "codex-model-router" /F  # 不再自启
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

重启 App。没配 key 的模型照样会出现在选择器里，只是选中后发请求才会失败——
目录只是一份清单，不做校验。

## 配套技能

`skills/codex-model-switch/` 是一个 Codex 技能，负责命令行侧：切换默认模型、给指定模型
跑一次性请求、以及生成多模型协作的 custom agent。

```bash
python skills/codex-model-switch/scripts/msw.py list
python skills/codex-model-switch/scripts/msw.py test router
python skills/codex-model-switch/scripts/msw.py switch router
```

装技能：把 `skills/codex-model-switch` 复制或软链到 `~/.codex/skills/` 下。

## 已知限制

- **它是个常驻进程。** 路由器挂了，Codex 就走不通。把默认改回直连供应商即可恢复。
- **GPT 那条走的是 Codex 的私有接口**（`chatgpt.com/backend-api/codex`）。Codex 升级
  有可能改掉它，这是整个方案唯一长期脆弱的地方；API key 路线不受影响。
- 模型目录只是一份清单，**不校验模型是否真实存在**。写错了要等发请求才报错。

## License

MIT
