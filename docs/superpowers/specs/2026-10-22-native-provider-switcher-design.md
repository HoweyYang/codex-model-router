# Native Provider Switcher design

## Goal

Replace the router-first installation with a high-compatibility way to use
native ChatGPT/Codex models and an OpenAI-compatible DeepSeek provider on the
same machine.  The published repository stays at
`HoweyYang/codex-model-router` for this replacement release, but its product
name and documentation become **Codex Native Provider Switcher**.

## Decisions

- A target is one complete, native Codex provider profile: model, provider,
  catalog path, and any required top-level settings.
- `gpt` is a native Codex/ChatGPT profile.  It does not use a local proxy or
  forward credentials.
- `deepseek` is a direct DeepSeek profile.  It uses its configured API key and
  does not require a ChatGPT login or ChatGPT quota.
- The two providers do not share a picker.  Codex binds a chat to its provider;
  after switching, users start a new chat (or restart the desktop app if it
  still shows cached settings).
- The registry records profiles in `~/.codex/model-switch.json`; only the
  marked `codex-model-switch` block in `~/.codex/config.toml` is modified.
  Every real switch makes a timestamped backup first.
- The router, merged cross-provider catalog, MCP autostart hook, port 8765
  service, and `requires_openai_auth` are removed from the normal installation
  path.  A short migration document explains how to leave a legacy router
  setup safely without deleting credentials.

## Repository layout

- `skills/codex-model-switch/scripts/msw.py` remains the standard-library
  switcher and is the only executable installation path.
- `examples/model-switch.json` provides `gpt` and `deepseek` target templates;
  it contains no keys or account data.
- English and Chinese READMEs explain setup, switching, catalog refresh, the
  provider/chat boundary, and migration from the older Router release.
- Router-specific sources, startup helpers, and router configuration examples
  are retired from the replacement release rather than presented as a default.

## Safety and failure handling

- No installer reads, stores, commits, or prints OAuth tokens or provider API
  keys.
- A `--dry-run` shows exactly which managed keys a switch would write.
- A failed model request leaves `config.toml` unchanged; users can switch back
  to the previous profile using the automatically saved registry target and
  timestamped backup.
- The repository update does not edit this computer's active
  `~/.codex/config.toml` or its credentials.  Its untracked
  `ensure-router.ps1` is left outside the commit.

## Verification

- Add standard-library `unittest` coverage for rendering and replacing the
  managed block, preserving unrelated TOML tables, creating a backup, and
  `--dry-run` non-mutation.
- Run the full unit suite and a CLI help/smoke check from a temporary
  `CODEX_HOME`; no real API request or account login is needed to verify the
  repository.
- Confirm the staged release contains no router sources, no credentials, and
  no user-local files before committing and asking for the final push approval.

## Out of scope

- Changing the user’s current Codex configuration, ChatGPT login, DeepSeek
  balance, GitHub repository settings, or repository name.
- Pretending that multiple providers can reliably coexist in one Codex chat or
  one native provider picker.
