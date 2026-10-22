# Codex Native Provider Switcher

[中文说明](README.zh-CN.md)

Use GPT/Codex and DeepSeek on one computer without putting a local router
between them. Each provider is a native, named profile. Switching a profile
updates only a marked block in Codex's configuration and creates a timestamped
backup first.

## Why this replaces the old Router workflow

Codex binds a chat to one provider. A shared model picker for several providers
therefore relies on a proxy layer and couples independent authentication states.

- gpt uses Codex's native ChatGPT account and its native model catalog.
- deepseek talks directly to the configured DeepSeek-compatible provider.
- A ChatGPT sign-in, plan limit, or network problem cannot make the direct
  DeepSeek profile require that account.

After switching profiles, start a new chat. Restart the desktop app only if it
still displays the previous profile. Python 3.8+ and the standard library are
sufficient.

## Install

Clone this repository, then copy or link the switcher skill into your Codex
skills directory:

    git clone https://github.com/HoweyYang/codex-model-router ~/.codex/services/codex-native-provider-switcher
    Copy-Item -Recurse ~/.codex/services/codex-native-provider-switcher/skills/codex-model-switch ~/.codex/skills/

The first command intentionally keeps the existing GitHub repository address;
the project itself is now a native provider switcher.

## Configure the providers

Keep the native OpenAI provider managed by Codex. Add a direct DeepSeek
provider to ~/.codex/config.toml; use an environment-variable key name, not a
literal key in the file:

    [model_providers.deepseek]
    name = "DeepSeek"
    base_url = "https://api.deepseek.com/v1"
    wire_api = "responses"
    env_key = "DEEPSEEK_API_KEY"

Set DEEPSEEK_API_KEY through your operating system or secret manager. Do not
commit it.

Copy examples/model-switch.json to ~/.codex/model-switch.json. Replace
C:/Users/you with your real home directory if necessary. The included profiles
are gpt (native openai, models-openai.json) and deepseek (direct deepseek,
models.json). Add extra profiles with msw.py add; the script never needs an API
key on the command line.

## Refresh the native GPT model catalog

Sign in to Codex normally, then run:

    python ~/.codex/services/codex-native-provider-switcher/tools/refresh-openai-catalog.py

It runs codex debug models, validates the JSON before replacing
~/.codex/models-openai.json, and keeps a timestamped backup of the prior
catalog. It does not change the active profile or credentials.

## Switch safely

Run commands from the cloned repository:

    python skills/codex-model-switch/scripts/msw.py list
    python skills/codex-model-switch/scripts/msw.py test deepseek
    python skills/codex-model-switch/scripts/msw.py switch deepseek
    python skills/codex-model-switch/scripts/msw.py switch gpt

Use test before switch when adding a new provider. Test sends one request with
temporary settings and leaves config.toml unchanged. Switch --dry-run prints the
exact managed keys without changing files.

A real switch updates only this top-level block:

    # >>> codex-model-switch >>>
    model = "..."
    model_provider = "..."
    model_catalog_json = "..."
    # <<< codex-model-switch <<<

Everything outside that block, including provider definitions and unrelated
settings, remains untouched. If that block is malformed, the switcher stops
without rewriting the configuration.

## Migrating from the older release

Do not copy any legacy provider profile into the new model-switch.json. Keep
old service files on disk if you want a manual rollback, but select either gpt
or deepseek through the native switcher. No background process, startup hook,
proxy forwarding, or shared provider catalog is part of this release.

Existing chats keep the provider with which they were created. This is expected:
open a new chat after a switch rather than trying to change its provider from
the model picker.

## License

MIT. See [LICENSE](LICENSE).
