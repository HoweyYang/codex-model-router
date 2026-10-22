# Codex 原生 Provider 切换器

[English](README.md)

在同一台电脑上使用 GPT/Codex 和 DeepSeek，不再把本地 Router 放在两者中间。
每个 Provider 是一个原生、具名的配置档；切换时只修改 Codex 配置中的受管区块，
并先生成带时间戳的备份。

## 为什么替代旧 Router 方案

Codex 的一个会话绑定一个 Provider。把多个 Provider 塞进同一个模型选择器，
需要额外代理层，也会把原本独立的认证状态绑在一起。

- gpt 直接使用 Codex 原生 ChatGPT 账号和原生模型目录。
- deepseek 直接请求已经配置的 DeepSeek 兼容 Provider。
- ChatGPT 登录、套餐额度或网络问题，不会让直连 DeepSeek 也被要求使用该账号。

切换后请新建会话；只有桌面端仍显示旧配置时才需要重启 App。只需 Python 3.8+，
不依赖第三方库。

## 安装

克隆仓库后，把切换 Skill 复制或链接到 Codex 的 Skill 目录：

    git clone https://github.com/HoweyYang/codex-model-router ~/.codex/services/codex-native-provider-switcher
    Copy-Item -Recurse ~/.codex/services/codex-native-provider-switcher/skills/codex-model-switch ~/.codex/skills/

第一条命令仍使用原有 GitHub 仓库地址；仓库内容已改为原生 Provider 切换器。

## 配置 Provider

原生 OpenAI Provider 由 Codex 管理。请在 ~/.codex/config.toml 中加入直连
DeepSeek Provider；使用环境变量名，不要把密钥直接写进文件：

    [model_providers.deepseek]
    name = "DeepSeek"
    base_url = "https://api.deepseek.com/v1"
    wire_api = "responses"
    env_key = "DEEPSEEK_API_KEY"

通过系统环境变量或密钥管理器设置 DEEPSEEK_API_KEY，不要提交它。

把 examples/model-switch.json 复制到 ~/.codex/model-switch.json。必要时把
C:/Users/you 改成真实用户目录。内置 gpt（原生 openai，models-openai.json）
和 deepseek（直连 deepseek，models.json）两个配置档。更多配置档请通过
msw.py add 新增，脚本不需要在命令行接收 API Key。

## 刷新原生 GPT 模型目录

正常登录 Codex 后运行：

    python ~/.codex/services/codex-native-provider-switcher/tools/refresh-openai-catalog.py

它会执行 codex debug models，先验证 JSON，再更新
~/.codex/models-openai.json，并保留旧目录的时间戳备份。它不会修改当前 Provider
或登录凭据。

## 安全切换

在克隆仓库目录中运行：

    python skills/codex-model-switch/scripts/msw.py list
    python skills/codex-model-switch/scripts/msw.py test deepseek
    python skills/codex-model-switch/scripts/msw.py switch deepseek
    python skills/codex-model-switch/scripts/msw.py switch gpt

新增 Provider 时先用 test。它会用临时配置发送一次请求，不修改 config.toml。
使用 switch --dry-run 可以先查看将写入的受管键。

真正切换只改下面的顶层受管区块：

    # >>> codex-model-switch >>>
    model = "..."
    model_provider = "..."
    model_catalog_json = "..."
    # <<< codex-model-switch <<<

Provider 定义和其他设置不会被动到。若该区块缺失结束标记，脚本会停止且不写入
配置文件。

## 从旧版本迁移

不要把旧的 Provider 配置档复制进新的 model-switch.json。如果想保留手动回退
空间，可以让旧服务文件继续留在硬盘上，但日常只通过原生切换器选择 gpt 或
deepseek。此版本没有后台常驻服务、开机钩子、代理转发或跨 Provider 共享模型
目录。

已有会话仍绑定创建时的 Provider，这是 Codex 的正常行为。切换后请新建会话，
不要尝试仅靠模型选择器在旧会话里更换 Provider。

## 许可证

MIT，见 [LICENSE](LICENSE)。
