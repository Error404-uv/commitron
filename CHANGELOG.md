# Changelog

## 1.0.0rc3 — Credential input hardening and documentation corrections

- Reject API credentials containing control characters before keychain storage or provider use, preventing malformed header values and header-injection attempts.
- Bound credential length to 4,096 characters and validate values read from environment variables and the OS keychain.
- Added regression tests for newline/control-character, oversized, and non-text credentials.
- Corrected the documented CI Python matrix to match the workflow configuration.
- Test suite is now fully green on Windows: literal-pathspec tests that required a `:`-prefixed filename (uncreatable on NTFS) are skipif-guarded for POSIX and replaced with cross-platform glob/magic-shaped path coverage; the Windows config-path test no longer forces `PosixPath` on nt.
- Expanded CLI, provider, credential, and profile-validation coverage from 75% to 85% total lines (above the 80% CI gate), including cancellation, secret-warning, oversized-diff, HTTP-error, and malformed-response paths.


## 1.0.0rc2 — Safety and release-candidate fixes

- Replaced the legacy root `smart_commit.py` implementation (which could offer `git add .`) with a compatibility shim that delegates to the maintained CLI.
- Validate branch names with Git before create/switch operations, preventing option-like names from being interpreted as Git flags.
- Reject malformed custom API URLs containing query strings, fragments, invalid ports, whitespace, or control characters.
- Block HTTP redirects for provider requests so API credentials are not forwarded through unexpected redirect chains.
- Bound provider response bodies to 2 MB and handle non-text OpenAI content blocks safely.
- Reject non-object existing `.commitron.json` files before attempting to update them.
- Expanded regression tests for branch argument safety, endpoint validation, provider response limits, and legacy entry-point behavior.
- Added CI dependency-audit and package-metadata validation steps.

## 1.0.0rc1 — Release candidate and verification hardening

- Reproducible test configuration now includes coverage measurement and an 80% minimum line-coverage gate in CI.
- CI now runs linting, tests, coverage enforcement, and source/wheel builds on the configured Windows, Linux, and macOS Python matrix.
- Interactive terminal input now handles end-of-input cleanly and exits without continuing an operation.
- Versioned as a release candidate, not a stable 1.0 release: live provider and native keychain tests plus actual hosted CI runs are still required.

## 0.9.0 — Interactive staging and credential storage

- Added `commitron stage` to review changed paths and stage only explicitly selected files.
- Used NUL-delimited Git status output and literal Git pathspecs to handle spaces and pathspec-like filenames safely.
- Added optional OS credential-manager integration through the `secure-store` extra; environment variables retain precedence and credentials remain outside config/profile files.
- Added `auth set`, `auth status`, and `auth delete` commands without displaying secret values.
- Rejected known plaintext/fail/null keyring backends rather than silently storing credentials insecurely.
- Fixed root-level pytest discovery for the `src/` package layout.
- Added tests for selective staging, cancellation, unusual filenames, credential precedence, and keyring behavior.


## 0.8.0 — Interactive profile management

- Replaced the misleading profile-list menu shortcut with a complete interactive profile manager.
- Added menu workflows to list, save, apply, and delete profiles.
- Added an overwrite confirmation before replacing an existing profile from the interactive menu.
- Added tests for profile-menu CRUD flows, overwrite confirmation, empty-profile states, and malformed configuration handling.
- Configuration updates now reject malformed existing setting types instead of silently dropping them and potentially resetting user settings.


## 0.7.0 — Interactive terminal and configuration profiles

- Added `commitron menu`, a guided terminal menu for common Git workflows and settings.
- Added `commitron config wizard` for interactive provider/model/endpoint configuration.
- Added named AI configuration profiles: `config profile save|list|use|delete`.
- Profiles store provider, model, and base URL only; API credentials are supplied through environment variables or the optional OS keychain.
- Profile files are written atomically with restrictive POSIX permissions where supported.
- Added validation for profile names, provider values, and endpoint security.
- Menu actions delegate to existing CLI commands; they do not bypass existing confirmation and privacy gates.

## 0.6.0 — 2026-11-07

- Added `git-help` to explain user-supplied Git errors with safe, non-executing diagnostic guidance after explicit data-sharing confirmation.
- Added `history --analyze` to summarize recent commit metadata after explicit data-sharing confirmation.
- Added bounded structured history retrieval and validation for AI analysis inputs and outputs.
- Added tests for history metadata parsing, prompt-injection boundaries, input limits, CLI parsing, and confirmation gates.
- Documented the privacy implications and limitations of metadata-only history analysis.


## 0.5.0 — 2026-11-07

- Added AI branch-name suggestions with explicit data-sharing confirmation, strict lowercase prefix/name checks, Git-native branch-name validation, and duplicate-branch rejection; suggestions never create branches automatically.
- Added file-level logical commit grouping from staged changes with strict JSON validation and exact changed-file coverage. The command is advisory and never modifies the index or commits.
- Added repository-specific commit-message conventions stored in `.commitron.json`, with `show`, `set`, and `clear` commands. Symlinked project config files are rejected on read and write.
- Applied project conventions to AI-generated commit-message candidates.
- Added tests for branch suggestions, logical grouping validation, repository conventions, and non-mutating CLI behavior.
- Updated CI to current checkout/setup-python action majors and Python 3.11–3.15 across Windows, macOS, and Linux.
- Documented the limits of file-level grouping and the privacy implications of project convention text.


## 0.4.1 — 2026-11-07

- Validate AI commit-message format, uniqueness, 72-character subject length, and requested candidate count.
- Move Gemini, OpenAI, and Ollama into separate adapters behind a shared provider contract.
- Replace silent diff truncation with lossless chunk processing and an explicit maximum-size guard.
- Expand heuristic secret detection patterns.
- Render untrusted Git and AI text as literal Rich `Text` objects.
- Raise the supported Python baseline to 3.11 and update the CI matrix to Python 3.11–3.13.


## 0.4.0

- Added provider-neutral AI generation for Gemini, OpenAI Chat Completions, and Ollama.
- Added `commitron explain` for staged and unstaged tracked-file diffs.
- Added per-user configuration commands with environment-variable overrides.
- Kept API keys out of the config file and rejected remote non-HTTPS custom endpoints.
- Added tracked changed-file listing and staged/unstaged diff summaries.
- Expanded tests for configuration, provider response parsing, prompts, and CLI parsing.

## 0.3.0

- Reorganized the application into an installable `src/` package.
- Added `commitron` CLI and retained `smart-commit` plus the legacy script launcher.
- Added status, staged diff, history, and branch commands.
- Removed automatic `git add .`; commits now use only the existing index.
- Added staged-diff privacy warnings, bounded diff submission, API timeout, and clearer errors.
- Replaced the legacy Gemini SDK dependency with a standard-library REST adapter.
- Added pytest coverage and a Windows/macOS/Linux CI matrix.
