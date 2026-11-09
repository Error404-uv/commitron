<div align="center">

# ⚡ Commitron

### A safer, multi-provider AI Git assistant for your terminal

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

Commitron assists with everyday Git workflows and uses an AI provider you choose to draft commit messages or explain changes. It works from staged or unstaged diffs; it can stage only paths you explicitly select with `commitron stage`, and it never silently stages files. It does not push, pull, reset, stash, or rewrite history.

## What's new in 1.0.0rc3

- Validate API credential values from environment variables and the optional OS keychain before use; reject control characters and values longer than 4,096 characters.
- Add regression tests for malformed, oversized, and non-text credential values.
- Correct the documented Python CI matrix to match the configured workflow.
- This remains a release candidate: hosted CI, real provider calls, and native keychain behavior still need external verification.

## What's new in 1.0.0rc2

- Replaced the old root `smart_commit.py` implementation with a compatibility shim to the maintained CLI; the legacy `git add .` behavior is no longer present in that entry point.
- Validate Git branch names before creating or switching branches.
- Harden custom API URL validation and block provider HTTP redirects to avoid forwarding credentials unexpectedly.
- Limit provider responses to 2 MB and handle mixed text/non-text OpenAI response blocks safely.
- Reject malformed project configuration files before overwriting them.
- This is still a release candidate, not a stable 1.0 release. Hosted CI, live AI-provider, and native OS keychain verification are still outstanding.

## What's new in 1.0.0rc1

- Release-candidate build with reproducible coverage reporting and an 80% CI coverage threshold.
- CI runs Ruff, pytest, coverage enforcement, and package builds across the configured Windows, Linux, and macOS matrix.
- Interactive commands exit cleanly if terminal input closes unexpectedly.

## What's new in 0.9.0

- Added `commitron stage` for interactive whole-file staging of explicitly selected changed paths, including untracked files.
- Added optional OS credential-manager support through `commitron[secure-store]` and `commitron auth`; environment variables take precedence and credentials are not stored in JSON.
- Refuse known plaintext/fail/null keyring backends.
- Fixed root-level pytest discovery for the `src/` layout.

## What's new in 0.8.0

- The interactive `commitron menu` now includes a real AI-profile manager: list, save, apply, and delete profiles without leaving the menu.
- Replacing an existing profile through the menu requires confirmation.
- Added automated tests for interactive profile-management flows, overwrite confirmation, empty-profile handling, and malformed configuration handling.
- Configuration updates reject malformed existing setting types rather than silently dropping them.

## What's new in 0.7.0

- `commitron menu` opens a guided terminal menu for status, diff review, smart commit, change explanation, history, settings, and profile management. Menu actions call the same command handlers and retain their safety confirmations.
- `commitron config wizard` interactively configures provider, model, and custom endpoint.
- Named provider profiles can be saved, listed, applied, and deleted with `commitron config profile`. Profiles contain no API keys; credentials are read from environment variables or the optional OS credential manager.

## What's new in 0.6.0

- Added `commitron git-help --error "..."` to explain a pasted Git error and suggest safe diagnostic steps. The error and optional context are sent to the configured AI provider only after explicit confirmation; the assistant is instructed not to recommend destructive commands as routine fixes and does not execute commands.
- Added `commitron history --analyze` to summarize recent commit subjects and bodies, identify recurring work areas, and distinguish observations from cautious inferences. Commit metadata is sent only after explicit confirmation.
- Added structured Git history retrieval with bounded limits and tests for metadata parsing, prompt-injection handling, input limits, and confirmation gates.

## What's new in 0.5.0

- `commitron branch suggest --description "..."` asks the configured AI provider for a branch name, checks it with Git's branch-name validator, and refuses names that already exist. It only prints a suggestion; it never creates a branch.
- `commitron split` analyzes staged tracked-file changes and suggests file-level logical commit groups with a message and rationale for each group. Every staged changed path must appear exactly once in a valid response. It never stages, unstages, or commits files.
- `commitron convention set "..."` saves repository-specific commit-message guidance in `.commitron.json`; `show` displays it and `clear` removes it. Commit-message generation uses this guidance when present.
- Added tests for AI branch-name validation, complete logical-group coverage, project conventions, and non-mutating CLI behavior.

## What's new in 0.4.1

- Validate AI-generated commit messages for the selected style, uniqueness, single-line format, 72-character subject length, and response count.
- Separate Gemini, OpenAI, and Ollama implementations behind one provider adapter contract.
- Process large diffs in ordered, lossless chunks instead of silently truncating them; refuse oversized diffs before sending any content.
- Expand heuristic credential warnings for GitHub, GitLab, Slack, Stripe, npm, AWS, Google, private keys, and JWT-like values.
- Render repository-controlled text and AI output as literal terminal text to prevent Rich markup interpretation.
- The original CI matrix at that milestone targeted Python 3.11–3.13; the current workflow is documented under Requirements and Development.

## What's new in 0.4.0

- Provider adapters for **Google Gemini**, **OpenAI Chat Completions**, and **Ollama** local models.
- `commitron explain` for a concise explanation of staged or unstaged tracked-file changes.
- `commitron config` for per-user provider/model/base URL settings.
- API keys can be read from environment variables or the optional OS credential manager; they are never written to config or profile files.
- HTTPS is required for remote custom endpoints; plain HTTP is accepted only for local endpoints.
- `files` and richer `diff` commands for reviewing staged or unstaged tracked-file changes.
- Secret-pattern checks before sending diffs to an AI provider.

## Requirements

- Python 3.11 or newer (CI targets 3.11–3.15)
- Git available on `PATH`
- An API key for Gemini or OpenAI, or a running local Ollama server

## Install

```bash
python -m pip install .
```

For development and tests:

```bash
python -m pip install -e ".[test]"
pytest
ruff check src tests
```

The legacy source-checkout command `python smart_commit.py` remains available as a compatibility shim and invokes the maintained `commitron` CLI. It no longer contains a separate implementation.

## Choose an AI provider

The default provider remains Gemini for compatibility:

```bash
commitron config set provider gemini
```

**Gemini** — set `GEMINI_API_KEY` in your environment. Default model: `gemini-2.5-flash`.

**OpenAI** — set `OPENAI_API_KEY` in your environment, then:

```bash
commitron config set provider openai
commitron config set model gpt-4.1-mini
```

**Ollama** — start Ollama locally, pull a model, then configure it:

```bash
ollama pull qwen2.5-coder:7b
commitron config set provider ollama
commitron config set model qwen2.5-coder:7b
```

View or interactively configure the effective settings:

```bash
commitron config show
commitron config wizard
```

Store API credentials in the operating-system credential manager (optional):

```bash
python -m pip install "commitron[secure-store]"
commitron auth set gemini
commitron auth set openai
commitron auth status
commitron auth delete openai
```

The optional keyring integration uses an available OS-backed credential backend and refuses known plaintext/fallback backends. Environment variables (`GEMINI_API_KEY`, `OPENAI_API_KEY`) take precedence. If a secure OS backend is unavailable, use environment variables instead. Credentials are never written to Commitron's JSON configuration or profile files.

Save and switch between named provider configurations (API keys are never included):

```bash
commitron config profile save work
commitron config profile save local
commitron config profile list
commitron config profile use local
commitron config profile delete work
```

Open the interactive terminal menu:

```bash
commitron menu
```

Settings are stored in a per-user `config.json` location: `%APPDATA%\\commitron` on Windows, `~/Library/Application Support/commitron` on macOS, or `$XDG_CONFIG_HOME/commitron` (default `~/.config/commitron`) on Linux. Environment variables override saved settings:

- `COMMITRON_PROVIDER`
- `COMMITRON_MODEL`
- `COMMITRON_BASE_URL`
- `GEMINI_API_KEY` / `OPENAI_API_KEY`

Provider-specific model overrides are also supported through `COMMITRON_GEMINI_MODEL`, `COMMITRON_OPENAI_MODEL`, and `COMMITRON_OLLAMA_MODEL`.

Set the relevant key in the current terminal session:

```powershell
# Windows PowerShell
$env:GEMINI_API_KEY = "your-key"
$env:OPENAI_API_KEY = "your-key"
```

```bat
:: Windows Command Prompt
set GEMINI_API_KEY=your-key
set OPENAI_API_KEY=your-key
```

```bash
# macOS / Linux
export GEMINI_API_KEY="your-key"
export OPENAI_API_KEY="your-key"
```

For OpenAI-compatible gateways, set `base_url` to the API root (for example `https://your-host.example/v1`). Do not put credentials in the URL. Remote HTTP endpoints are rejected to avoid sending API credentials over an unencrypted connection.

## Git workflows

Run commands inside a Git repository:

```bash
commitron status
commitron stage                 # interactively select exact paths to stage
commitron files                 # staged tracked files
commitron files --unstaged      # unstaged tracked files
commitron diff                  # staged diff
commitron diff --unstaged       # unstaged diff
commitron diff --stat           # staged summary
commitron history --limit 15
commitron history --analyze --limit 20
commitron branch
commitron branch create feature/my-change
commitron branch switch main
commitron branch suggest --description "Add OAuth login"
```

The AI branch suggestion sends the task description and current branch names to your configured AI provider after an explicit confirmation. Possible credential patterns trigger an additional warning. The suggested name is checked against Git's ref-format rules and existing branches; no branch is created automatically. Review the suggestion before creating it.

Suggest logical file-level commits from the current staged diff:

```bash
commitron split
commitron split --style gitmoji
```

`split` requires at least two staged tracked files. It groups whole files, not individual hunks within one file. Treat the output as a review aid: the grouping is AI-generated and may be wrong. Commitron does not change the Git index or create commits.

Set repository-specific commit-message guidance:

```bash
commitron convention set "Use feat(scope): summary; scopes are lowercase; include a ticket ID when one is present."
commitron convention show
commitron convention clear
```

This writes `.commitron.json` at the Git repository root. It contains guidance only, not API credentials. You can commit it to share conventions with teammates, or add it to `.gitignore` for local-only preferences. Keep the text focused on formatting rules; it is passed to the configured AI provider as prompt guidance.


Stage only the files you intend to include, then draft a commit message. You can use `commitron stage` to select exact changed paths interactively, or use Git directly:

```bash
git add path/to/file.py
commitron commit --dry-run
commitron commit
```

Other options:

```bash
commitron commit --style gitmoji --count 5
commitron commit --style plain
commitron commit --yes
```

`--yes` selects the first generated suggestion and skips the final commit confirmation. It does not skip the secret warning. `--dry-run` never creates a commit. Commitron never runs `git add .` automatically.

Explain a pasted Git error using the selected provider:

```bash
commitron git-help --error "fatal: not a git repository (or any of the parent directories): .git"
commitron git-help --error "fatal: refusing to merge unrelated histories" --context "running git pull"
```

Commitron asks before sending the error and optional context. It provides explanations and diagnostic suggestions only; it does not run suggested commands. Review AI advice before acting, especially if it involves changing repository state.

Analyze recent commit history:

```bash
commitron history --analyze --limit 20
```

This sends recent commit hashes, dates, subjects and bodies to the configured AI provider after confirmation. Commit messages can contain sensitive information; review your history and any heuristic secret warnings before approving. The analysis is a summary of commit metadata, not a code-level audit and not proof that a feature is correct or complete.

Explain changes using the selected provider:

```bash
commitron explain                 # staged changes
commitron explain --unstaged      # unstaged tracked-file changes
```

## Privacy and safety

- Commitron sends the selected diff to the configured AI provider when you run `commit`, `explain`, or `split`. `branch suggest` sends the task description and current branch names only after an explicit confirmation. Review all content first; code, project convention text, task details, and accidentally staged secrets may be disclosed to that provider.
- The local secret detector checks a small set of patterns only. It can miss secrets and produce false positives; it is not a complete secret scanner.
- API credentials are rejected if they contain control characters or exceed 4,096 characters before being stored or sent in provider headers. This is input hardening, not a substitute for keeping keys private.
- Large diffs are split into ordered chunks and summarized before final generation. All chunks are included; Commitron refuses diffs beyond its safe chunk limit rather than silently omitting content. Multi-chunk analysis uses multiple AI requests and may consume more quota.
- `--allow-secrets` disables the heuristic warning for diff and repository convention content in `commit` and `split`. Use it only after reviewing that content and deciding disclosure is acceptable.
- API keys can be read from environment variables or an optional OS credential manager; they are never stored in Commitron's config or profile files.
- Ollama runs locally by default, but a custom endpoint may send code elsewhere. Verify the endpoint you configure.
- `files` and `diff` list tracked changes; `commitron stage` includes untracked files in its interactive selection. The staging command selects whole files, not individual hunks.
- `history --analyze` sends recent commit metadata only after explicit confirmation. `git-help` sends the supplied error and context only after explicit confirmation. Neither command executes Git operations.
- Branch creation and switching are explicit commands. AI branch suggestions do not create branches.
- Logical commit grouping is file-level and advisory only; it cannot separate unrelated hunks inside one file and never changes the Git index.
- Repository-specific convention text in `.commitron.json` is included in AI prompts. Review it before sharing the repository or sending diffs to a provider.
- Commitron does not push, pull, reset, stash, or rewrite history.

## Troubleshooting

- **Not a Git repository:** change into your repository directory. `commitron config show` works outside a repository.
- **No staged changes:** run `git status`, then use `commitron stage` to select intended whole files, or stage a path directly with `git add <path>`.
- **Missing API key:** set the provider's environment variable in the same terminal session.
- **Ollama connection refused:** ensure the Ollama service is running and the configured model is available.
- **API error:** check key validity, network access, model availability, provider quota, and configured base URL.

## Development

```bash
python -m pip install -e ".[test]"
pytest
ruff check src tests
```

CI is configured to run the test suite on Windows, macOS, and Linux with Python 3.11, 3.12, 3.13, 3.14, and 3.15. Provider network calls are mocked/not required by the unit test suite; test a provider separately with your own key or local model.

## License

MIT. See [LICENSE](LICENSE).
